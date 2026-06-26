# Instagram Content Automation

Monitors a list of Instagram accounts, downloads new posts, runs OCR on the image,
and prepares a repost caption — with a desktop GUI, a JSON-emitting CLI for n8n,
and a `--daemon` mode for unattended 24/7 operation.

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
3. If you want authenticated scraping (private profiles, higher rate limits),
   set `instagram_username` / `instagram_password`. The app logs in once and
   saves a session file under `config/sessions/` so it never has to re-send
   the password (or hit a 2FA prompt) on every scheduled check.

## Run

```powershell
python main.py --gui        # desktop app
python main.py --check      # one scan, JSON to stdout (for n8n)
python main.py --prepare    # OCR + caption prep on the queue, JSON to stdout
python main.py --status     # dashboard-style JSON summary
python main.py --daemon     # run check+prepare forever on the configured interval
```

`--check` / `--prepare` / `--status` print one JSON object to stdout and nothing
else — safe to pipe into n8n's Execute Command node. All logs go to
`logs/app.log` and stderr.

## Running 24/7 unattended (even when your PC is off)

This runs as a GitHub Actions scheduled workflow (`.github/workflows/scan.yml`),
not as a local process — free, no server to manage, runs on GitHub's
infrastructure on a cron schedule (hourly by default).

**One-time setup:**

1. Push this project to a GitHub repo (private recommended — it'll contain
   downloaded images).
2. In the repo: **Settings → Secrets and variables → Actions → New repository
   secret**. Add `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD`.
3. Push to the default branch — the workflow runs automatically on its cron
   schedule, or trigger it immediately from the **Actions** tab → "Instagram
   scan" → **Run workflow**.
4. Each run commits the updated `database/app.db` and any new files under
   `downloads/` back to the repo. `git pull` locally to review the queue in
   the GUI.

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

For local manual use, `--daemon` still works the same way (loops forever,
isolates failures per cycle) if you ever want to run it on your own machine
instead.

## Architecture

See `CONTEXT.md` for the module map and current project state.
