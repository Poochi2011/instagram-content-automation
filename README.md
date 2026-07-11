# Instagram Content Automation

Monitors a list of Instagram accounts, downloads new posts (including full
carousels), runs OCR on the image, builds a repost caption, and **automatically
publishes** it to a destination Instagram account via the Graph API — no manual
review step. Has a desktop GUI, a JSON-emitting CLI for n8n, and a `--daemon`
mode for unattended 24/7 operation.

**This auto-publishes without a human checking each post first.** That was a
deliberate choice for this deployment (the source accounts have authorized
republishing), but it does mean a bad OCR read, wrong caption, or scraper edge
case goes out publicly with nothing catching it before it does. The queue page
in the GUI still shows everything that was published/failed after the fact.

## Setup

```powershell
py -3.12 -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

Tesseract OCR must be installed separately (default path:
`C:\Program Files\Tesseract-OCR\tesseract.exe` — configurable in Settings).

## Configure

1. List the Instagram usernames to monitor in `accounts.txt`, one per line.
2. Edit `config/config.json` (created automatically on first run from
   `config/config.example.json`) — or use the Settings page in the GUI.
3. **Authenticated scraping (strongly recommended).** Anonymous Instagram
   access gets rate-limited/blocked hard and fast, especially from datacenter
   IPs (GitHub Actions runners included) — logged-in requests get a much
   higher limit. Use a dedicated/throwaway account, not your main one.
   - Set `instagram_username` / `instagram_password` in `config/config.json`
     and run `python main.py --check` once **locally**, on your own
     (residential) connection. If Instagram doesn't challenge the login, the
     app saves a session file to `config/sessions/<username>.session`
     automatically — it never re-sends the password or re-prompts after that.
   - If Instagram *does* challenge the login (common for a brand-new
     account's first automated-looking login — a verification code, "was
     this you?", etc.): open that challenge in the real Instagram app/site
     yourself first, then run:
     `.\venv\Scripts\instaloader --login=<username> --sessionfile=config/sessions/<username>.session`
     This handles the password/2FA prompt interactively in your own terminal
     and saves the session straight to the path the app expects.
   - For the GitHub Actions deployment, the session file also needs to reach
     the cloud runner. Add `INSTAGRAM_USERNAME`/`INSTAGRAM_PASSWORD` as repo
     secrets, **and** base64-encode the local session file and add it as
     `INSTAGRAM_SESSION_B64`:
     `[Convert]::ToBase64String([IO.File]::ReadAllBytes("config\sessions\<username>.session"))`
     (PowerShell). This seeds the very first cloud run with an
     already-authenticated session — created from your residential IP, not
     GitHub's — so it isn't the one place a fresh, challenge-prone login gets
     attempted from a datacenter IP. After the first successful run, the
     workflow's own session cache (`actions/cache@v4`) takes over and the
     secret is only used again if that cache is ever lost.
4. To enable auto-publishing, set in `config/config.json` (or the Settings page):
   - `ig_dest_access_token` — a long-lived Graph API access token for the
     **destination** account (the one that will post). Requires that account
     to be an Instagram Business/Creator account linked to a Facebook Page,
     and a Meta Developer App with the `instagram_content_publish` permission.
   - `ig_dest_business_account_id` — that destination account's IG Business
     Account ID (from the Graph API, not the username).
   - `media_public_base_url` — a public URL prefix the Graph API can fetch
     downloaded images from. **Graph API fetches the image itself; a local
     file path will never work**, even with `--daemon` on your own PC. Set
     this to your repo **root** (not `/downloads` — the app already appends
     the `downloads/<account>/<file>.jpg` part), e.g.
     `https://raw.githubusercontent.com/<you>/<repo>/main` — but that only
     works if the repo is **public** (Graph API can't authenticate to fetch
     from a private repo). If you want to keep the repo private, point this
     at your own CDN/object storage instead.
   - `max_publish_per_day` (default 16), `max_publish_per_cycle` (default 2),
     `publish_retry_max_attempts` (default 5), `publish_retry_backoff_minutes`
     (default 15, doubles each retry).

## Run

```powershell
python main.py --gui        # desktop app
python main.py --check      # one scan, JSON to stdout (for n8n)
python main.py --prepare    # OCR + caption prep on the queue, JSON to stdout
python main.py --publish    # publish due 'ready' posts to the destination account
python main.py --status     # dashboard-style JSON summary
python main.py --daemon     # run check+prepare+publish forever on the configured interval
```

### Carousels and video — what's actually supported

- **Multi-image carousels are fully supported**: every image slide is
  downloaded, OCR'd (cover slide only), and republished as a real Instagram
  carousel (not flattened to one image).
- **Video is out of scope** — both standalone video/Reels posts and video
  slides *within* a carousel. The scraper is configured with
  `download_videos=False` project-wide; a post with image slides "loses" any
  video slides (logged, not silently dropped), and a post that's video-only
  is marked `error` with a logged reason rather than queued.

`--check` / `--prepare` / `--status` print one JSON object to stdout and nothing
else — safe to pipe into n8n's Execute Command node. All logs go to
`logs/app.log` and stderr.

## Running 24/7 unattended (even when your PC is off)

This runs as a GitHub Actions scheduled workflow (`.github/workflows/scan.yml`),
not as a local process — free, no server to manage, runs on GitHub's
infrastructure on a cron schedule (hourly by default).

**One-time setup:**

1. Push this project to a GitHub repo. **Auto-publish needs `media_public_base_url`
   to be a publicly fetchable URL** — if you use the default
   `raw.githubusercontent.com` option, that means **this repo must be public**
   (it'll contain downloaded images). If you'd rather keep it private, host
   the `downloads/` folder on your own CDN/object storage and point
   `MEDIA_PUBLIC_BASE_URL` there instead.
2. In the repo: **Settings → Secrets and variables → Actions → New repository
   secret**. Add `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`, and for
   auto-publish: `IG_DEST_ACCESS_TOKEN`, `IG_DEST_BUSINESS_ACCOUNT_ID`,
   `MEDIA_PUBLIC_BASE_URL`.
3. Push to the default branch — the workflow runs automatically on its cron
   schedule, or trigger it immediately from the **Actions** tab → "Instagram
   scan" → **Run workflow**.
4. Each run downloads new posts, commits/pushes the media (so it's live at
   `MEDIA_PUBLIC_BASE_URL` before publishing references it), runs `--publish`,
   then commits the resulting publish status. `git pull` locally to review the
   queue in the GUI.

**Known tradeoffs of this approach** (you chose it for cost/setup simplicity —
worth knowing going in):
- The SQLite database is now version-controlled state. Don't run the local
  `--daemon` or click "Run Check Now" in the GUI and let the cloud job run at
  the same moment without pulling first — binary DB merge conflicts are
  possible. Safest pattern: `git pull` before reviewing locally, mark things
  processed, `git push` right after.
- GitHub Actions runners use datacenter IPs, which Instagram rate-limits/blocks
  more aggressively than a residential IP. Logging in (vs. anonymous) and a
  conservative polling interval (hourly, not every few minutes) reduce this
  but don't eliminate it — check the Logs page / `errors` table if scans start
  failing.
- The repo will grow over time as downloaded images accumulate; prune old
  files under `downloads/` periodically if that becomes a problem.
- To change how often it runs, edit the `cron:` line in
  `.github/workflows/scan.yml` (this controls cloud frequency — the
  `polling_interval_minutes` setting only affects local `--daemon` runs).
- Auto-publish is capped at `max_publish_per_day` (default 16) and
  `max_publish_per_cycle` (default 2, i.e. up to two new posts go out per run) —
  raise these in Settings/config.json if that's still too slow to drain
  a backlog. Keep `max_publish_per_day` comfortably under Instagram's own
  Graph API content-publishing limit (25 posts/24h per account).
- Scraping via Instaloader and posting via the Graph API are still two
  separate risk surfaces: scraping is against Instagram's unofficial web
  interface regardless of any agreement with the source accounts, and the
  destination account doing frequent automated carousel posts is exactly the
  pattern Instagram's spam/automation detection watches for. Keep an eye on
  the `errors` table / Logs page for sudden spikes, which usually means a
  rate limit or a flag, not a code bug.

For local manual use, `--daemon` still works the same way (loops forever,
isolates failures per cycle) if you ever want to run it on your own machine
instead.

## Architecture

See `CONTEXT.md` for the module map and current project state.
