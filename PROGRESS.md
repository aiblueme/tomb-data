# Progress

## 2026-03-13 — Session 2: Phases 1–3 Implemented

Full pipeline code written and locally verified. All files in `/home/dev/projects/tomb-data/`.

### Files created
- `build.py` — pipeline orchestrator (`--once` for cron, `--inbox`/`--output` for local testing)
- `chart_templates.py` — 5 chart types → Chart.js config (comparison, trend, distribution, ranking, timeline)
- `photos.py` — Unsplash + Pexels fallback, query-hash caching, 7-day TTL, graceful degradation
- `Dockerfile` — python:3.12-slim + pagefind + supercronic, cron every 5min
- `docker-compose.yml` — research-nginx, research-meili (internal), research-pipeline
- `nginx.conf` — static serving + `/api/search` proxy to MeiliSearch with server-side key
- `templates/base.html` — masthead, nav, footer
- `templates/report.html` — TOC sidebar + 65ch prose, Chart.js injection, photo slots
- `templates/index.html` — month-grouped archive, tag filter bar (JS, no reload)
- `templates/search.html` — Pagefind UI (left) + MeiliSearch live search (right)
- `requirements.txt`

### Verified
- 5 chart types render at correct positions (`after-intro`, `after-section-N`, `before-conclusion`)
- No visuals block → clean render
- Malformed visuals YAML → warning logged, body renders without charts
- MeiliSearch down → warning, pipeline continues
- Pagefind missing → warning, pipeline continues

## 2026-03-13 — Session 1: Architecture + Planning

Architecture finalized. Key decisions:
- Custom Python pipeline (not Hugo/knowledge base/Obsidian-only)
- Upstream LLM directives (no second LLM in build step)
- Dual search: Pagefind (client-side) + MeiliSearch (API fuzzy)
- Vault stays separate from pipeline
