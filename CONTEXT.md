# Instagram Content Automation — Context

## Stack
Python 3.12 (venv pinned via `py -3.12`), Instaloader, pytesseract + Tesseract-OCR,
SQLite, PySide6 (Qt6) for the desktop GUI. CLI designed for n8n consumption.

## Project structure
- `config/` — `settings.py` (Settings dataclass, load/save config.json), `config.json` (gitignored, real values), `sessions/` (gitignored Instagram session files)
- `database/` — `schema.sql`, `db.py` (connection/init), `models.py` (dataclasses), `repository.py` (all SQL)
- `scraper/` — `instagram_client.py` (Instaloader wrapper + session persistence), `monitor.py` (check-accounts orchestration)
- `ocr/extractor.py` — Tesseract wrapper
- `publisher/` — `caption_builder.py`, `queue_manager.py` (OCR + caption prep on downloaded posts)
- `ui/` — `app.py` (MainWindow/AppContext), `theme.py` (QSS), `workers.py` (QThread helper), `pages/`, `widgets/`
- `main.py` — CLI: `--check` `--prepare` `--status` `--gui` `--daemon`

## Key files
`main.py`, `scraper/monitor.py`, `database/repository.py`, `config/settings.py`, `ui/app.py`

## Active work
Skeleton + all modules implemented and individually smoke-tested (config, db,
OCR, caption builder, CLI commands, GUI rendering verified via real screenshots).
24/7 hosting decision: **GitHub Actions scheduled workflow** (`.github/workflows/scan.yml`,
hourly cron + manual `workflow_dispatch`), not a local daemon — runs even when
the user's PC is off, $0 cost. State (database/app.db, downloads/) is persisted
by committing it back to the repo each run; secrets come from GitHub Actions
repo secrets (`INSTAGRAM_USERNAME`/`INSTAGRAM_PASSWORD`), injected via env vars
that `config/settings.py` overrides config.json with — never written to disk in CI.
Repost scope is intentionally staging-only (publisher/ prepares, doesn't post) —
no Graph API integration yet.
**Not yet tested against real Instagram** — no live scraper run has happened
(no accounts in `accounts.txt`, no credentials anywhere yet). Also not yet
pushed to an actual GitHub repo — that's the next step once the user has one.

## Design tokens / conventions
Dark theme tokens and QSS in `ui/theme.py` (`COLORS` dict). Sidebar/card/table
styling follows a Linear/Notion-style flat dark UI — no custom fonts bundled,
uses Segoe UI.

## External services
- Instagram (via Instaloader) — anonymous works for public profiles; `instagram_username`/`instagram_password` in config.json enables login + session reuse.
- Tesseract OCR — local binary, path configurable (`tesseract_path` in config.json).
- n8n — calls `python main.py --check` / `--prepare` / `--status` via Execute Command, parses the JSON on stdout.

## Known constraints / gotchas
- `posts` table doubles as processed-posts + download-history (status/timestamp columns) instead of three separate tables — intentional simplification.
- Windows console (cp1252) can't print emoji directly; CLI JSON output uses `ensure_ascii=True` so this never surfaces as a bug — only matters if adding new `print()` debug statements.
- `--daemon` is a long-running loop for *local/VM* use; the chosen 24/7 path is GitHub Actions instead (see above), so `--daemon` is currently a fallback/manual option, not what's actually deployed.
- GUI and CLI/daemon share one SQLite file; SQLite serializes access fine for this single-user use case but don't run `--daemon` and the GUI's "Run Check Now" at the exact same moment as a habit.
- database/app.db and downloads/ are intentionally tracked in git (not ignored) because the GitHub Actions workflow commits them back as its persistence mechanism. Pull before reviewing locally; push right after marking things processed, to avoid binary merge conflicts on app.db.
- GitHub-hosted runners use datacenter IPs — expect more frequent Instagram rate-limiting than scraping from a residential IP. Check the errors table/Logs page if scans start failing.
