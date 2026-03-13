
# Research Report Pipeline

Automated pipeline that transforms Claude Deep Research markdown reports into interactive, auth-gated HTML pages with charts, photos, and fuzzy search. Served from Shell VPS behind Authelia.

## Why

Deep Research output currently lives nowhere permanent. Volume is scaling to ~20 reports/day (~600/month). Each report is 2,000-8,000 words of structured findings that become unfindable the moment the conversation closes. Need: store, render, search, and optionally enrich with interactive charts and relevant photos. Fully self-hosted, no SaaS dependency.

## Key Design Decision: Upstream Directives

Chart data and photo queries are embedded in the research prompt itself, not extracted downstream by a second LLM. The research model already knows which data matters and where visuals belong. The build pipeline is therefore purely mechanical — parse, map, fetch, render. No LLM calls. No inference. No non-determinism (except Unsplash availability, which degrades gracefully).

Every research prompt includes a `---research-visuals---` block directive that specifies semantic chart types (comparison, trend, distribution, ranking, timeline) and contextual photo queries with placement positions.

## Architecture

```
Research Prompt (with visuals directive)
  → Markdown report + ---research-visuals--- block
  → Dropped into /opt/research/data/reports/inbox/

Python Build Pipeline (cron every 5min)
  → Parse markdown + frontmatter + visuals block
  → Chart type → Chart.js config (deterministic mapping)
  → Photo query → Unsplash API → local cache
  → Jinja2 template → static HTML
  → Push to MeiliSearch index
  → Run Pagefind on output dir
  → Archive source .md

Serving (Docker on Shell)
  → nginx (static HTML)
  → MeiliSearch (fuzzy search API)
  → Authelia (auth gate)
  → SWAG reverse proxy
```

## Build Steps

### Phase 1: Core Pipeline (~4 hours)

- [ ] Create `/opt/research/` directory structure on Shell
- [ ] Write `build.py` — frontmatter parse, visuals block extraction, markdown→HTML, Jinja2 render
- [ ] Write `chart_templates.py` — semantic type → Chart.js config mapping (5 types)
- [ ] Write `report.html` Jinja2 template — brutalist, monospace + condensed sans-serif, Chart.js embed, photo slots
- [ ] Write `index.html` template — archive listing page with date/tag grouping
- [ ] Test: one report in inbox → one rendered HTML page in output
- [ ] Set up cron job (every 5 minutes, process inbox)

### Phase 2: Search + Auth (~3 hours)

- [ ] Add MeiliSearch container to docker-compose
- [ ] Add document push to build.py (slug, title, content, date, tags)
- [ ] Install Pagefind, add post-build index step to build.py
- [ ] Write `search.html` template with Pagefind UI + MeiliSearch live search
- [ ] Add Authelia container to docker-compose
- [ ] Configure Authelia (single-user YAML, TOTP)
- [ ] Add SWAG proxy conf (research.subdomain.conf with authelia includes)
- [ ] Test: auth gate works, search returns results

### Phase 3: Photos (~2 hours)

- [ ] Write `photos.py` — Unsplash API fetch with query hash caching + fallback logic
- [ ] Register Unsplash API app (Demo tier: 50 req/hour)
- [ ] Integrate photo fetching into build.py pipeline
- [ ] Add photo slots + attribution to report.html template
- [ ] Apply for Unsplash Production tier (5,000 req/hour) if needed

### Phase 4: Polish (~2 hours)

- [ ] Backfill: run existing ~10 reports through pipeline (manually add visuals blocks or accept text-only)
- [ ] Add the research-visuals directive to base Deep Research prompt template
- [ ] Build `base.html` shared layout (nav, footer, consistent typography)
- [ ] Add tag filtering to archive index page
- [ ] Error handling: malformed visuals blocks, failed photo fetches, MeiliSearch downtime

## Stack

- **Python:** frontmatter, markdown, Jinja2, meilisearch-python, requests
- **Search:** Pagefind (client-side, post-build) + MeiliSearch (API, Docker)
- **Charts:** Chart.js (~60KB, embedded per-page)
- **Photos:** Unsplash API (free tier) with local caching
- **Auth:** Authelia (single container, YAML config, TOTP)
- **Serving:** nginx Alpine + SWAG reverse proxy (existing infrastructure)
- **Design:** Brutalist. Monospace + condensed sans-serif. Warm editorial tones. No purple. No rounded-card SaaS patterns.

## Open Questions

- **Report delivery mechanism** — How do Deep Research reports get from Claude into `/opt/research/data/reports/inbox/`? Manual copy-paste to .md file? Clipboard → script? API webhook? Solve after Phase 1 proves the pipeline works.
- **Backfill strategy** — The ~10 existing reports lack visuals blocks. Re-run through Claude with "generate visuals block only" prompt, or accept as text-only? Low priority — don't block Phase 1 on this.
- **Photo budget** — Unsplash free tier (50 req/hour) handles 20 reports/day at 2-3 photos each. If volume exceeds this, Production tier is free but requires approval. Pexels API is the fallback.

## Decision Log

| Date | Decision |
|------|----------|
| 2026-03-13 | Architecture decided: custom Python pipeline + Jinja2 + Pagefind + MeiliSearch + Authelia. Rejected Hugo (Go templates less natural for Python dev), knowledge bases (fight their UI, need DB), and Obsidian-only (no web serving, no charts, doesn't scale). |
| 2026-03-13 | Key design decision: upstream LLM directives over downstream extraction. Chart data and photo queries embedded in research prompt, not inferred by second LLM in build step. Eliminates ~$4-30/month API cost, removes non-determinism from pipeline, better data accuracy (research model has full context). |
| 2026-03-13 | Vault integration: separate system from Obsidian vault. No stubs, no hybrid index. Pipeline and vault don't touch each other unless cross-referencing need emerges from real usage. |
| 2026-03-13 | Search: dual approach. Pagefind for client-side browsing (zero infrastructure). MeiliSearch for API-driven fuzzy search with typo tolerance (single Docker container, ~1-2GB RAM at scale). |
