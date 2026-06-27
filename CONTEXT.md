# Instagram Content Automation — Context

## Stack
Python 3.12 (venv pinned via `py -3.12`), Instaloader, pytesseract + Tesseract-OCR,
SQLite, PySide6 (Qt6) for the desktop GUI. CLI designed for n8n consumption.

## Project structure
- `config/` — `settings.py` (Settings dataclass, load/save config.json), `config.json` (gitignored, real values), `sessions/` (gitignored Instagram session files)
- `database/` — `schema.sql`, `db.py` (connection/init), `models.py` (dataclasses), `repository.py` (all SQL)
- `scraper/` — `instagram_client.py` (Instaloader wrapper + session persistence, carousel-aware), `monitor.py` (check-accounts orchestration)
- `ocr/extractor.py` — Tesseract wrapper
- `publisher/` — `caption_builder.py`, `queue_manager.py` (OCR + caption prep), `graph_api_client.py` (Instagram Graph API content-publishing wrapper), `auto_publisher.py` (publish orchestration: retry/backoff/daily cap)
- `ui/` — `app.py` (MainWindow/AppContext), `theme.py` (QSS), `workers.py` (QThread helper), `pages/`, `widgets/`
- `main.py` — CLI: `--check` `--prepare` `--publish` `--status` `--gui` `--daemon`

## Key files
`main.py`, `scraper/monitor.py`, `publisher/auto_publisher.py`, `publisher/graph_api_client.py`, `database/repository.py`, `config/settings.py`, `ui/app.py`

## Active work
Auto-publish pipeline added: `--daemon` (and the GitHub Actions workflow) now
runs check → prepare → **publish** every cycle, with no manual review step —
this is a deliberate change from the original design (see git history), made
because the monitored accounts (in `accounts.txt`) have authorized
republishing to the destination account. Carousels are fully supported
end-to-end (all image slides downloaded via `post_media` table, OCR'd cover
slide, republished as a real multi-image carousel via Graph API child +
parent containers). Video — both standalone posts and video slides inside a
carousel — is explicitly out of scope (consistent with the pre-existing
`download_videos=False` on the Instaloader instance); such posts are logged
and marked `error` rather than queued for partial/wrong reposting.

Publish retry state (`publish_attempts`, `next_publish_attempt_at`,
`last_publish_error`) lives on the `posts` row in SQLite, not in memory, so a
daemon restart or a fresh Actions run resumes backoff exactly where it left
off. Daily/per-cycle caps (`max_publish_per_day`=10, `max_publish_per_cycle`=1
by default) are enforced in `auto_publisher.publish_due_posts()`.

24/7 hosting: **GitHub Actions scheduled workflow** (`.github/workflows/scan.yml`,
hourly cron + manual `workflow_dispatch`). The workflow now does two
commit/push cycles per run — once after download (so media is live at
`MEDIA_PUBLIC_BASE_URL` before `--publish` references it; the Graph API fetches
images itself, it does not accept local files), then again after publish to
persist status. Secrets: `INSTAGRAM_USERNAME`/`INSTAGRAM_PASSWORD`,
`IG_DEST_ACCESS_TOKEN`/`IG_DEST_BUSINESS_ACCOUNT_ID`/`MEDIA_PUBLIC_BASE_URL`.

**Not yet tested against real Instagram or the real Graph API** — no live
scraper or publish run has happened yet. Destination-account Graph API
credentials are still being set up by the user as of this writing; until
`ig_dest_access_token`/`ig_dest_business_account_id` are configured,
`publish_due_posts()` is a no-op (logs and returns early) rather than erroring.
Also not yet pushed to an actual GitHub repo.

## Design tokens / conventions
Dark theme tokens and QSS in `ui/theme.py` (`COLORS` dict). Sidebar/card/table
styling follows a Linear/Notion-style flat dark UI — no custom fonts bundled,
uses Segoe UI.

## External services
- Instagram (via Instaloader) — anonymous works for public profiles; `instagram_username`/`instagram_password` in config.json enables login + session reuse.
- Tesseract OCR — local binary, path configurable (`tesseract_path` in config.json).
- Instagram Graph API (destination account auto-publish) — `ig_dest_access_token`/`ig_dest_business_account_id` in config.json; needs a Business/Creator destination account + Meta Developer App.
- n8n — calls `python main.py --check` / `--prepare` / `--publish` / `--status` via Execute Command, parses the JSON on stdout.

## Known constraints / gotchas
- `posts` table doubles as processed-posts + download-history (status/timestamp columns) instead of three separate tables — intentional simplification. `status='processed'` now specifically means "published to the destination account", set by `auto_publisher.publish_post()`, not just "manually reviewed" as originally written.
- Windows console (cp1252) can't print emoji directly; CLI JSON output uses `ensure_ascii=True` so this never surfaces as a bug — only matters if adding new `print()` debug statements.
- `--daemon` is a long-running loop for *local/VM* use; the chosen 24/7 path is GitHub Actions instead (see above), so `--daemon` is currently a fallback/manual option, not what's actually deployed.
- GUI and CLI/daemon share one SQLite file; SQLite serializes access fine for this single-user use case but don't run `--daemon` and the GUI's "Run Check Now" at the exact same moment as a habit.
- database/app.db and downloads/ are intentionally tracked in git (not ignored) because the GitHub Actions workflow commits them back as its persistence mechanism. Pull before reviewing locally; push right after marking things processed, to avoid binary merge conflicts on app.db.
- GitHub-hosted runners use datacenter IPs — expect more frequent Instagram rate-limiting than scraping from a residential IP. Check the errors table/Logs page if scans start failing.
- Carousel slides beyond the cover live in `post_media` (post_id, position, image_path); the cover slide stays on `posts.image_path` for backward compatibility with OCR/dashboard code that only ever read a single path.
- `auto_publisher.publish_due_posts()` is a deliberate no-op (not an error) when `ig_dest_access_token`/`ig_dest_business_account_id` are blank, so `--daemon`/the Actions workflow can run safely before those secrets are supplied.
- Retry backoff is exponential (`publish_retry_backoff_minutes * 2^attempts`, capped at 24h) and stored per-post in SQLite (`next_publish_attempt_at`), not in-process — this is what makes retries survive a daemon/Actions restart.
- `media_public_base_url` must be a URL the Graph API's own servers can fetch from the public internet — never a local path. If using GitHub raw content, the repo must be public.
