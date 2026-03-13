#!/usr/bin/env python3
"""
Research Report Pipeline — build.py
Processes .md files from inbox, renders HTML, indexes to MeiliSearch, runs Pagefind.
Usage: python build.py --once [--inbox PATH] [--output PATH]
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

import chart_templates
import photos as photos_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Defaults ---
BASE_DIR = Path(__file__).parent
DEFAULT_INBOX = Path("/opt/research/data/reports/inbox")
DEFAULT_OUTPUT = Path("/opt/research/data/output")
DEFAULT_ARCHIVE = Path("/opt/research/data/reports/archive")
DEFAULT_PHOTO_CACHE = Path("/opt/research/data/photo-cache")
MEILI_URL = os.environ.get("MEILI_URL", "http://research-meili:7700")
MEILI_KEY = os.environ.get("MEILI_MASTER_KEY", "")
MEILI_INDEX = "reports"
VISUALS_SEPARATOR = "---research-visuals---"

MD_EXTENSIONS = ["tables", "fenced_code", "toc", "nl2br"]


# --- Jinja2 env ---
def make_jinja_env(templates_dir: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )
    return env


# --- Markdown rendering ---
def render_markdown(body: str) -> tuple[str, list]:
    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    html = md.convert(body)
    toc_items = []
    if hasattr(md, "toc_tokens"):
        for item in md.toc_tokens:
            toc_items.append({"id": item["id"], "text": item["name"]})
    return html, toc_items


# --- Visual marker injection ---
POSITION_RE = re.compile(r"after-section-(\d+)")


def inject_visual_markers(html: str, charts: list, photos: list) -> str:
    """
    Insert <!-- VISUAL:{id} --> at position targets within rendered HTML.
    Positions: after-intro (after first <p> anywhere), after-section-N (after Nth h2 block),
    before-conclusion (before last <h2>).
    """
    all_items = [(c["position"], c["id"]) for c in charts if "position" in c and "id" in c]
    all_items += [(p["position"], p.get("query", "")) for p in photos if "position" in p and p.get("query")]

    if not all_items:
        return html

    for position, item_id in all_items:
        marker = f"<!-- VISUAL:{item_id} -->"
        if position == "after-intro":
            # After first </p> anywhere in the document
            m = re.search(r"</p>", html, re.IGNORECASE)
            if m:
                html = html[: m.end()] + "\n" + marker + "\n" + html[m.end():]
        elif position == "before-conclusion":
            # Before last <h2>
            m_list = list(re.finditer(r"<h2[^>]*>", html, re.IGNORECASE))
            if m_list:
                last = m_list[-1]
                html = html[: last.start()] + marker + "\n" + html[last.start():]
        else:
            pm = POSITION_RE.match(position)
            if pm:
                n = int(pm.group(1))
                # Find end of content after Nth h2 block (i.e., just before N+1th h2, or end)
                h2_matches = list(re.finditer(r"<h2[^>]*>", html, re.IGNORECASE))
                if n <= len(h2_matches):
                    target_h2_start = h2_matches[n - 1].start()
                    # Find end of this h2 block's content = start of next h2 (or end of doc)
                    if n < len(h2_matches):
                        next_h2_start = h2_matches[n].start()
                        insert_at = next_h2_start
                    else:
                        insert_at = len(html)
                    html = html[:insert_at] + "\n" + marker + "\n" + html[insert_at:]

    return html


def replace_visual_markers(html: str, charts: list, photos_data: dict, charts_json: dict) -> tuple[str, dict]:
    """
    Replace <!-- VISUAL:{id} --> markers with chart canvas or photo figure elements.
    Returns modified html + charts_json dict for the template.
    """
    charts_by_id = {c["id"]: c for c in charts if "id" in c}
    all_chart_configs = {}

    def replace_marker(m):
        item_id = m.group(1)
        if item_id in charts_by_id:
            chart = charts_by_id[item_id]
            config = chart_templates.build_config(chart)
            all_chart_configs[item_id] = config
            title = chart.get("title", "")
            title_html = f'<div class="chart-title">{title}</div>' if title else ""
            return (
                f'<div class="chart-block">'
                f"{title_html}"
                f'<div class="chart-wrap">'
                f'<canvas id="chart-{item_id}"></canvas>'
                f"</div></div>"
            )
        # Check if it's a photo position marker
        if item_id in photos_data:
            p = photos_data[item_id]
            return (
                f'<figure class="photo-block">'
                f'<img src="{p["url"]}" alt="{p.get("alt","")}" loading="lazy">'
                f'<figcaption>{p.get("attribution","")}</figcaption>'
                f"</figure>"
            )
        return ""

    result = re.sub(r"<!-- VISUAL:([^>]+) -->", replace_marker, html)
    return result, all_chart_configs


# --- Slug generation ---
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


# --- MeiliSearch push ---
def push_to_meili(doc: dict) -> None:
    try:
        import meilisearch
        client = meilisearch.Client(MEILI_URL, MEILI_KEY)
        index = client.index(MEILI_INDEX)
        # Ensure index exists with correct primary key
        try:
            client.create_index(MEILI_INDEX, {"primaryKey": "id"})
        except Exception:
            pass
        # Configure searchable/filterable attributes
        try:
            index.update_searchable_attributes(["title", "content_text", "summary", "tags"])
            index.update_filterable_attributes(["tags", "date"])
            index.update_displayed_attributes(["id", "title", "slug", "date", "tags", "summary", "content_text"])
            index.update_ranking_rules(["typo", "words", "proximity", "attribute", "sort", "exactness"])
        except Exception:
            pass
        index.add_documents([doc])
        logger.info("Pushed to MeiliSearch: %s", doc["id"])
    except Exception as e:
        logger.warning("MeiliSearch push failed for %s: %s", doc.get("id"), e)


# --- Pagefind ---
def run_pagefind(output_dir: Path) -> None:
    binary = shutil.which("pagefind")
    if not binary:
        logger.warning("pagefind binary not found in PATH, skipping index")
        return
    result = subprocess.run(
        [binary, "--site", str(output_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("pagefind exited %d: %s", result.returncode, result.stderr[:500])
    else:
        logger.info("Pagefind index updated")


# --- Manifest / index regeneration ---
MANIFEST_FILE = "manifest.json"


def load_manifest(output_dir: Path) -> list:
    mf = output_dir / MANIFEST_FILE
    if mf.exists():
        try:
            return json.loads(mf.read_text())
        except Exception:
            return []
    return []


def save_manifest(output_dir: Path, manifest: list) -> None:
    mf = output_dir / MANIFEST_FILE
    mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def build_index(env: Environment, output_dir: Path, manifest: list) -> None:
    if not manifest:
        manifest = load_manifest(output_dir)

    # Sort by date descending
    manifest_sorted = sorted(manifest, key=lambda r: r.get("date", ""), reverse=True)

    # Group by year-month
    from collections import defaultdict, OrderedDict
    groups = defaultdict(list)
    for r in manifest_sorted:
        date_str = r.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str)
            ym = dt.strftime("%Y-%m")
            date_short = dt.strftime("%d %b")
        except Exception:
            dt = None
            ym = date_str[:7] if date_str else "Unknown"
            date_short = ""
        r["date_short"] = date_short
        groups[ym].append(r)

    grouped = list(groups.items())

    # Tag counts
    from collections import Counter
    tag_counter = Counter()
    for r in manifest_sorted:
        for t in r.get("tags", []):
            tag_counter[t.upper()] += 1
    all_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)

    tmpl = env.get_template("index.html")
    html = tmpl.render(
        grouped_reports=grouped,
        total_count=len(manifest_sorted),
        all_tags=all_tags,
    )
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    logger.info("Rebuilt index.html (%d reports)", len(manifest_sorted))

    search_tmpl = env.get_template("search.html")
    (output_dir / "search.html").write_text(search_tmpl.render(total_count=len(manifest_sorted)), encoding="utf-8")
    logger.info("Rebuilt search.html")

    error_tmpl = env.get_template("404.html")
    (output_dir / "404.html").write_text(error_tmpl.render(), encoding="utf-8")
    logger.info("Rebuilt 404.html")


# --- Word count ---
def word_count(text: str) -> int:
    return len(text.split())


# --- Core: process one file ---
def process_file(
    md_file: Path,
    output_dir: Path,
    archive_dir: Path,
    photo_cache_dir: Path,
    env: Environment,
    manifest: list,
) -> bool:
    logger.info("Processing: %s", md_file.name)

    raw = md_file.read_text(encoding="utf-8")

    # Split on visuals separator
    if VISUALS_SEPARATOR in raw:
        parts = raw.split(VISUALS_SEPARATOR, 1)
        report_raw = parts[0].strip()
        visuals_raw = parts[1].strip()
    else:
        report_raw = raw.strip()
        visuals_raw = ""

    # Parse frontmatter
    try:
        post = frontmatter.loads(report_raw)
        meta = dict(post.metadata)
        body = post.content
    except Exception as e:
        logger.error("Frontmatter parse failed for %s: %s", md_file.name, e)
        _move_to_failed(md_file, archive_dir)
        return False

    # Parse visuals block (errors are non-fatal)
    charts = []
    photo_list = []
    if visuals_raw:
        try:
            visuals = yaml.safe_load(visuals_raw) or {}
            charts = visuals.get("charts", []) or []
            photo_list = visuals.get("photos", []) or []
        except Exception as e:
            logger.warning("Visuals block parse failed for %s: %s — rendering without visuals", md_file.name, e)

    # Derive slug and metadata
    title = meta.get("title", md_file.stem)
    date_val = meta.get("date", "")
    if isinstance(date_val, datetime):
        date_iso = date_val.isoformat()
        date_display = date_val.strftime("%Y-%m-%d")
    else:
        date_iso = str(date_val)
        date_display = str(date_val)

    slug = meta.get("slug", slugify(title))
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags = [str(t).upper() for t in tags]
    summary = meta.get("summary", meta.get("description", ""))
    source = meta.get("source", "")

    # Markdown → HTML
    body_html, toc_items = render_markdown(body)
    wc = word_count(body)

    # Inject visual markers into HTML
    body_html = inject_visual_markers(body_html, charts, photo_list)

    # Fetch photos
    photos_data = {}
    if photo_list:
        try:
            photos_data = photos_module.fetch_photos(photo_list, photo_cache_dir)
        except Exception as e:
            logger.warning("Photo fetch failed: %s", e)

    # Replace markers with actual elements, collect chart configs
    body_html, chart_configs = replace_visual_markers(body_html, charts, photos_data, {})

    # Render report HTML
    tmpl = env.get_template("report.html")
    html = tmpl.render(
        title=title,
        date=date_display,
        slug=slug,
        tags=tags,
        source=source,
        summary=summary,
        word_count=wc,
        body_html=body_html,
        toc=toc_items,
        charts_json=json.dumps(chart_configs, ensure_ascii=False),
        photos=photos_data,
    )

    output_file = output_dir / f"{slug}.html"
    output_file.write_text(html, encoding="utf-8")
    logger.info("Wrote: %s", output_file)

    # MeiliSearch
    content_text = re.sub(r"<[^>]+>", " ", body_html)
    content_text = re.sub(r"\s+", " ", content_text).strip()
    doc = {
        "id": slug,
        "title": title,
        "slug": slug,
        "date": date_iso,
        "tags": tags,
        "summary": summary or content_text[:300],
        "content_text": content_text[:5000],
    }
    push_to_meili(doc)

    # Update manifest
    manifest_entry = {
        "slug": slug,
        "title": title,
        "date": date_iso,
        "tags": tags,
        "summary": summary or content_text[:200],
    }
    manifest[:] = [r for r in manifest if r.get("slug") != slug]
    manifest.append(manifest_entry)

    # Archive source file
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = archive_dir / f"{slug}_{ts}.md"
    shutil.move(str(md_file), str(dest))
    logger.info("Archived: %s → %s", md_file.name, dest.name)

    return True


def _move_to_failed(md_file: Path, archive_dir: Path) -> None:
    failed_dir = archive_dir / "failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = failed_dir / f"{md_file.stem}_{ts}.md"
    shutil.move(str(md_file), str(dest))
    logger.error("Moved to failed: %s → %s", md_file.name, dest.name)


# --- Entry point ---
def main():
    parser = argparse.ArgumentParser(description="Research Report Pipeline")
    parser.add_argument("--once", action="store_true", help="Process inbox and exit (for cron)")
    parser.add_argument("--inbox", default=str(DEFAULT_INBOX))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--photo-cache", default=str(DEFAULT_PHOTO_CACHE))
    parser.add_argument("--templates", default=str(BASE_DIR / "templates"))
    args = parser.parse_args()

    inbox_dir = Path(args.inbox)
    output_dir = Path(args.output)
    archive_dir = Path(args.archive)
    photo_cache_dir = Path(args.photo_cache)

    for d in [inbox_dir, output_dir, archive_dir, archive_dir / "failed", photo_cache_dir]:
        d.mkdir(parents=True, exist_ok=True)

    env = make_jinja_env(Path(args.templates))
    manifest = load_manifest(output_dir)

    md_files = sorted(inbox_dir.glob("*.md"))
    if not md_files:
        logger.info("Inbox empty, nothing to do")
        sys.exit(0)

    logger.info("Found %d file(s) in inbox", len(md_files))
    processed = 0
    for md_file in md_files:
        ok = process_file(md_file, output_dir, archive_dir, photo_cache_dir, env, manifest)
        if ok:
            processed += 1

    if processed > 0:
        save_manifest(output_dir, manifest)
        build_index(env, output_dir, manifest)
        run_pagefind(output_dir)
        logger.info("Done: %d/%d processed", processed, len(md_files))
    else:
        logger.warning("No files successfully processed")


if __name__ == "__main__":
    main()
