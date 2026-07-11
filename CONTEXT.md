# Instagram Content Automation — Context

## Stack
Python 3.12 (venv pinned via `py -3.12`), Camoufox (anti-detect Firefox,
github.com/daijro/camoufox) as the default scraper, Instaloader kept but
unused (see below), pytesseract + Tesseract-OCR, SQLite, PySide6 (Qt6) for
the desktop GUI. CLI designed for n8n consumption.

## Project structure
- `config/` — `settings.py` (Settings dataclass, load/save config.json), `config.json` (gitignored, real values), `sessions/` (gitignored Instagram session files)
- `database/` — `schema.sql`, `db.py` (connection/init), `models.py` (dataclasses), `repository.py` (all SQL)
- `scraper/` — `camoufox_client.py` (default scraper: `CamoufoxInstagramClient`, anonymous browser-rendered scraping, single-image-only), `browser.py` (Camoufox launcher, proxy+geoip aware), `instagram_client.py` (Instaloader wrapper, carousel-aware — kept but no longer used by `monitor.py`, see Active work), `monitor.py` (check-accounts orchestration)
- `ocr/extractor.py` — Tesseract wrapper
- `publisher/` — `caption_builder.py`, `queue_manager.py` (OCR + caption prep), `graph_api_client.py` (Instagram Graph API content-publishing wrapper), `auto_publisher.py` (publish orchestration: retry/backoff/daily cap)
- `ui/` — `app.py` (MainWindow/AppContext), `theme.py` (QSS), `workers.py` (QThread helper), `pages/`, `widgets/`
- `main.py` — CLI: `--check` `--prepare` `--publish` `--status` `--gui` `--daemon`

## Key files
`main.py`, `scraper/monitor.py`, `publisher/auto_publisher.py`, `publisher/graph_api_client.py`, `database/repository.py`, `config/settings.py`, `ui/app.py`

## Active work

**Camoufox is the default scraper (wired 2026-07-10), but is CURRENTLY BLOCKED
as of 2026-07-11 — read this before assuming it works.** Anonymous Camoufox
scraping was proven working repeatedly on 2026-07-10 (real posts/images/
captions fetched and one real post published to `@activate.you`, media id
`18328443421282776`). Every GitHub Actions run since has hit a login wall or
timeout on all 11 accounts, including naturally-spaced hourly runs across
~10 hours (not a burst/pacing issue — added a 3-7s inter-account stagger,
didn't help). Re-tested locally on 2026-07-11 (same machine, same code, that
worked hours earlier) and it **also now times out** — this rules out a
Linux-CI-specific fingerprint problem; the block is proxy/IP-pool-wide, not
environment-specific. Most likely explanation: cumulative heavy request
volume through the same DataImpulse sticky-proxy identity over one day
(extensive manual testing 2026-07-10 + ~10 hours of hourly CI runs) got that
IP pool broadly flagged by Instagram. Unresolved as of this writing — next
steps to try: wait longer and re-test, request a fresh session/pool from
DataImpulse, or evaluate a different residential proxy provider if this
doesn't clear.

Instaloader's anonymous access is separately blocked outright (private-API
calls get a 403), proxy or not — confirmed by testing, corroborated by
Instaloader's own docs and a live 2026 upstream issue, unrelated to the
Camoufox proxy-pool issue above. The login-based fallback (account
`voidvessel85`) also hit a soft "please wait a few minutes" lock on first
live login attempt and didn't clear after a retry, so it's not currently
usable either. `scraper/camoufox_client.py`'s `CamoufoxInstagramClient`
mirrors `InstagramClient`'s interface and is what `scraper/monitor.py` uses.
**Known regression vs. the old Instaloader path: carousels are captured as a
single representative image only** — multi-slide extraction from the embed
page's DOM wasn't solved, so `is_carousel` is always `False` on posts from
this client. `instagram_client.py` (Instaloader) is kept in the codebase,
unused, in case the login path recovers
later.

**Proxy setup (DataImpulse residential):** `scraper_proxy_url` MUST use a
**sticky** port (10000-20000), not the rotating default (823/824) — rotating
hands a fresh exit IP every request, which both looks like a bot and breaks
Camoufox's geoip-matched fingerprint. MUST also pin a country with
`__cr.<code>` appended to the username (e.g. `login__cr.in:pass@gw.dataimpulse.com:10000`)
— an exit country that jumps randomly between sessions (observed: India →
Spain → Congo) is itself a bot signal. Pinned to `in` to match this project's
actual origin. This exact value must be set as **both** the local
`config.json` value AND the GitHub Actions repo secret `SCRAPER_PROXY_URL` —
they are independent; a value in one does not imply the other has it.

**Auto-publish pipeline:** the GitHub Actions workflow runs check → prepare →
publish every cycle, no manual review step — deliberate, since the monitored
accounts (`accounts.txt`) have authorized republishing. `max_publish_per_day`=10,
`max_publish_per_cycle`=1 — with the hourly cron this naturally drips
publishes across the day rather than bursting. Retry state
(`publish_attempts`, `next_publish_attempt_at`, `last_publish_error`) lives on
the `posts` row in SQLite, not in memory, so a restart resumes backoff where
it left off. **Verified live end-to-end 2026-07-10**: scraped, downloaded,
OCR'd, captioned (with `📌 Reposted from @username` attribution), and
published a real post to `@activate.you` (media id `18328443421282776`).

**Comment auto-reply pipeline (`--reply`) is written but deliberately NOT
shipped yet.** It exists only as uncommitted local changes (`config/settings.py`
reply fields, `database/models.py`/`repository.py` Comment*/CommentRepository,
`database/schema.sql` comments table, `publisher/graph_api_client.py` comment
methods, `main.py --reply`, plus untracked `publisher/comment_responder.py`,
`publisher/reply_drafter.py`, `ui/pages/comments.py`) — none of this is in the
repo. It was mixed into the same working tree as the scraper work above and
had to be deliberately excluded, file-by-file, to keep the Camoufox fix
scoped (see git log around 2026-07-10 for the untangling). Do not assume
`--reply` works in CI until it's committed AND live-tested there — the known
bug (comment `username` field returns `None`, blocking self-comment/
already-replied detection; blocked on a Meta account security lock as of
2026-07-04) still applies whenever this does ship.

24/7 hosting: **GitHub Actions scheduled workflow** (`.github/workflows/scan.yml`,
hourly cron + manual `workflow_dispatch`). Installs Firefox system deps
(`playwright install-deps firefox`) and caches the ~530MB Camoufox binary
(`~/.cache/camoufox`, keyed on `requirements.txt`'s hash) so it's not
re-downloaded every run. Does two commit/push cycles per run — once after
download (media must be live at `MEDIA_PUBLIC_BASE_URL` before `--publish`
references it), again after publish to persist status. Secrets:
`SCRAPER_PROXY_URL`, `IG_DEST_ACCESS_TOKEN`, `IG_DEST_BUSINESS_ACCOUNT_ID`,
`MEDIA_PUBLIC_BASE_URL`. (`INSTAGRAM_USERNAME`/`PASSWORD`/`SESSION_B64`
secrets still exist from the old Instaloader-login CI path but are no longer
read by anything — harmless leftovers, not cleaned up.)

## Design tokens / conventions
Dark theme tokens and QSS in `ui/theme.py` (`COLORS` dict). Sidebar/card/table
styling follows a Linear/Notion-style flat dark UI — no custom fonts bundled,
uses Segoe UI.

## External services
- Instagram — scraped anonymously via Camoufox (see Active work); Instaloader kept but unused. `instagram_username`/`instagram_password` in config.json still exist for a possible future login-based path but nothing currently reads them for scraping.
- Camoufox anti-detect browser — installed via `pip install camoufox[geoip]`; the ~530MB Firefox binary is downloaded once per machine with `python -m camoufox fetch` (lives in the OS per-user cache, NOT in the repo/venv, so CI must run `camoufox fetch` in its setup step, cached across runs). Wrapped by `scraper/browser.py::stealth_browser()`, used by `scraper/camoufox_client.py`. Playwright is pinned to `1.49.0` in requirements.txt — >=1.61 sends a CDP param the Camoufox 135 Firefox build's Juggler protocol rejects (`Browser.new_page` fails).
- DataImpulse residential proxy (`scraper_proxy_url`) — MUST use a **sticky** port (10000-20000), not the rotating default (823/824): rotating hands a fresh exit IP every request, which both looks like a bot and breaks Camoufox's geoip-matched fingerprint. MUST also pin a country with `__cr.<2-letter-code>` appended to the username (e.g. `login__cr.in:pass@gw.dataimpulse.com:10000`) — letting the exit country jump randomly between logins (observed: India → Spain → Congo across three sticky sessions) triggers Instagram's suspicious-login/"please wait a few minutes" soft-block on an account that's logging in from a wildly different geography than its history. Pinned to `in` (India) here to match this project's/account's actual origin. Set in **both** local `config.json` and the GitHub Actions secret `SCRAPER_PROXY_URL` — independent values, check both when debugging.
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
- **Check `git status` against the actual repo before trusting local behavior generalizes to CI.** A large chunk of a prior session's work (the whole comment-reply pipeline, plus `scraper_proxy_url` itself) sat as uncommitted local changes for days — everything worked locally (it's the same filesystem) while CI ran the older committed code and had no idea any of it existed. Cost several failed CI runs on 2026-07-10 to untangle (missing `scraper/browser.py`, missing `scraper_proxy_url` field, a workflow step for a CLI flag that didn't exist yet). `git status`/`git diff --stat` at the start of any CI-touching work would have caught this immediately.
- Also runs hourly on its own — expect `origin/master` to have moved (usually just an `app.db` update) since you last pulled. `database/app.db` is binary and can't auto-merge; on a push rejection, don't force-push — `git reset --soft origin/master && git checkout HEAD -- database/app.db`, then redo whatever local DB changes on top of the fresh copy.
