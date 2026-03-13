# Progress

## 2026-03-13 — Session 4: Typography Redesign + Tag Collapse + search.html Fix

### Typography redesign (all templates)
- **`base.html`**: Added `--serif` (Georgia), `--prose-size: 17px`, `--border-light`, `--border-faint`, `--dim` CSS variables
- **`report.html`**: Prose body switched from `var(--mono)` Courier 13px → `var(--serif)` Georgia 17px. Report H1/H2/H3 `text-transform: none` (uppercase was causing visual noise). Metadata split into two elements: `.report-byline` (date / source / wordcount) then `.report-tags-row` (tags). TOC sidebar lightened (#888 links, #f0f0f0 separators, #999 label). Blockquote padding widened, italic. Tag borders/colors lightened (`#aaa`/`#777`). `chart-title` and `figcaption` explicitly pinned to `var(--mono)` so they don't inherit serif from `#prose`. Code bumped to 13px (compensates for surrounding 17px). Table explicit mono.
- **`index.html`**: Tag filter bar border lightened to `--border-light`, buttons `#888` / `font-size: 10px`, active = bold black (was red). Month headings: 2px border, `color: var(--muted)`, 12px. Report rows: `--border-faint`, padding 12px. Row titles: `var(--condensed)`, 14px, `text-transform: none`. Tags lightened (`#ccc`/`#999`).
- **`search.html`**: Result titles 14px, `text-transform: none`. Inline JS tag style updated to `#ccc`/`#999`.

### Tag collapse toggles
- **Report pages**: Tags hidden by default. Replaced with `N TAGS ▾` button that toggles `.report-tags-row.open`. Arrow flips to ▴ when open.
- **Archive rows**: Tags hidden by default. `+N` count shown in right column. Click to expand full tag list inline. `tag-count` hides when open.

### Bug fix: search.html never rendered to output
- `search.html` existed only as a Jinja2 template — `build.py` never wrote it to `/opt/research/data/output/`. Added 2-line render call in `rebuild_index()` alongside `index.html`. Required image rebuild (build.py is baked into container, not bind-mounted).

### Deployment
- All template changes deployed via git push → `ssh vps2-docker git pull` (templates bind-mounted, no rebuild needed for those)
- `build.py` fix required `docker compose build research-pipeline && docker compose up -d`
- All 13 existing reports re-rendered through pipeline to pick up new templates
- **Linting**: All three output files (`index.html`, `bali-waterfalls-motorbike-guide.html`, `search.html`) pass HTML nesting check (0 errors) and all CSS/feature markers present

### Remaining
- [ ] Change Authelia password from `changeme`
- [ ] TOTP enrollment
- [ ] Set `UNSPLASH_ACCESS_KEY` in `~/tomb-data/.env` on vps2
- [ ] Figure out report delivery mechanism (currently: manual copy to inbox)
- [ ] Add `---research-visuals---` block to base Deep Research prompt template

## 2026-03-13 — Session 3: Phase 2 (Auth) Deployed + Live

All containers deployed to Shell VPS. Auth gate live and working.

### Deployed
- `research-authelia` — Authelia 4.38+, healthy, at `auth.shellnode.lol`
- `research-nginx` — static serving at `research.shellnode.lol`, behind Authelia
- `research-meili` — MeiliSearch v1.8, internal only
- `research-pipeline` — supercronic cron every 5min, processing inbox

### Verified
- `research.shellnode.lol` → 302 redirect to `auth.shellnode.lol` ✓
- `auth.shellnode.lol` → 200, Authelia portal ✓
- Login with `dev` / `changeme` → redirects back to archive ✓
- Pipeline processed test report end-to-end: inbox → HTML → MeiliSearch → Pagefind → archive ✓

### Bugs fixed during deploy
1. **nginx template mount** — `nginx.conf` needed to be mounted at `/etc/nginx/templates/default.conf.template` (not `conf.d/`) so envsubst processes `${MEILI_MASTER_KEY}`
2. **MeiliSearch key too short** — `changeme` (8 bytes) rejected in production mode; upgraded to 32-char hex
3. **Authelia 400 → nginx 500** — root cause: Authelia 4.38+ requires `session.cookies[].authelia_url` in `configuration.yml` to know where its own portal is. Without it, auth-request returns 400, nginx turns that into 500. Fixed by switching from deprecated `session.domain` to `session.cookies` format with `authelia_url: https://auth.shellnode.lol`
4. **SWAG upstream name** — SWAG's `authelia-server.conf` hardcodes upstream as `authelia`; fixed with Docker network alias on `research-authelia`
5. **Empty output → 403** — first visit after deploy showed 403 because output dir was empty (no reports processed yet); fixed by running `docker exec research-pipeline python /app/build.py --once` with a test report

### Config on vps2 (not in repo)
- `/opt/research/data/auth/configuration.yml` — Authelia config (session.cookies format)
- `/opt/research/data/auth/users_database.yml` — user `dev`, bcrypt hash of `changeme`
- `~/tomb-data/.env` — MEILI_MASTER_KEY, AUTHELIA_JWT_SECRET, AUTHELIA_SESSION_SECRET, AUTHELIA_STORAGE_ENCRYPTION_KEY
- SWAG `/config/nginx/authelia-server.conf` — manually edited, adds `X-Authelia-URL` header

### Remaining
- [ ] Change Authelia password from `changeme` — generate new bcrypt hash, update `users_database.yml`
- [ ] TOTP enrollment — visit `auth.shellnode.lol`, log in, enroll TOTP on first login
- [ ] Set `UNSPLASH_ACCESS_KEY` in `~/tomb-data/.env` on vps2 (register Unsplash app)
- [ ] Backfill existing reports — drop `.md` files into `/opt/research/data/reports/inbox/`
- [ ] Add `---research-visuals---` block to base Deep Research prompt template
- [ ] Figure out report delivery mechanism (currently: manual copy to inbox)

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
