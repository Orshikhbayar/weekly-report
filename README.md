# Weekly Website Change Monitor

Automated scraper that tracks weekly changes on telecom operator websites and produces a structured change report (Markdown + HTML) with optional screenshots.

## Monitored Sites

| Key      | Site                          | Strategy              |
|----------|-------------------------------|-----------------------|
| `nt`     | NT (National Telecom Thailand)| HTTP scraping (BS4)   |
| `unitel` | Unitel (Mongolia)             | JSON API + fallback   |
| `skytel` | Skytel (Mongolia)             | Playwright (JS)       |

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Install Playwright browsers (one-time)
python -m playwright install chromium
```

### 2. Interactive mode (recommended)

Launch the interactive terminal UI — select sites, watch live progress, view results:

```bash
python -m weekly_monitor interactive
```

This walks you through:
1. **Site selection** — pick which sites to scan (by number, key, or `all`)
2. **Options** — screenshots, email, Vercel deploy
3. **Live progress** — spinner + progress bars as each site is scraped
4. **Summary table** — new/updated items per site at a glance

### 3. Headless mode (cron / CI)

```bash
# Today's date (default)
python -m weekly_monitor run

# Specific date
python -m weekly_monitor run --date 2026-02-09

# Skip screenshots (faster)
python -m weekly_monitor run --no-screenshots

# Skip detail-page fetching (faster, less data)
python -m weekly_monitor run --no-details

# Run only specific sites
python -m weekly_monitor run --sites nt,unitel

# Verbose logging
python -m weekly_monitor run -v
```

### 4. Share the report

#### Option A — Deploy to Vercel (public URL, no account required)

```bash
python -m weekly_monitor run --deploy
```

After the scrape completes the report is packaged and deployed automatically.
The command prints a **Preview URL** anyone can open in a browser, plus a
**Claim URL** to transfer the deployment to your own Vercel account.

#### Option B — Send via email

```bash
# Set SMTP credentials (example: Gmail with an App Password)
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=your-app-password
export SMTP_FROM=you@gmail.com        # optional, defaults to SMTP_USER

# Run and email the report
python -m weekly_monitor run --email-to "alice@example.com,bob@example.com"
```

Screenshots are embedded inline in the email — recipients see them without
downloading attachments.

#### Option C — Both at once

```bash
python -m weekly_monitor run --deploy --email-to "team@example.com"
```

### 5. View the report locally

```
output/<date>/weekly_report.md
output/<date>/weekly_report.html    (also saved as index.html)
output/<date>/screenshots/<site_key>/*.png
```

## Project Structure

```
weekly-updates/
├── src/weekly_monitor/
│   ├── __init__.py
│   ├── __main__.py           # python -m weekly_monitor entrypoint
│   ├── cli.py                # Click CLI (run + interactive commands)
│   ├── interactive.py        # Rich interactive terminal UI
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py           # Abstract SiteAdapter class
│   │   ├── nt.py             # NT (ntplc.co.th) adapter
│   │   ├── unitel.py         # Unitel (unitel.mn) adapter
│   │   └── skytel.py         # Skytel (skytel.mn) adapter
│   └── core/
│       ├── __init__.py
│       ├── models.py         # Pydantic data models
│       ├── storage.py        # JSON snapshot persistence
│       ├── http.py           # HTTP client (httpx + retries)
│       ├── diff.py           # Diff engine (new/updated items)
│       ├── screenshots.py    # Playwright screenshot capture
│       ├── report.py         # Markdown + HTML report generation
│       └── email_sender.py   # SMTP email with inline images
├── scripts/
│   └── deploy.sh             # Vercel deploy (no account needed)
├── templates/
│   └── weekly_report.html    # Jinja2 HTML template
├── tests/
│   ├── fixtures/             # Saved HTML/JSON for offline tests
│   ├── test_diff.py          # Diff engine unit tests
│   └── test_adapters.py      # Adapter parsing tests
├── data/                     # Snapshot storage (auto-created)
├── output/                   # Reports + screenshots (auto-created)
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Data Model

Each run produces a JSON snapshot per site at `data/<site_key>/YYYY-MM-DD.json`:

```json
{
  "site_key": "nt",
  "run_timestamp": "2026-02-09T12:00:00",
  "listing_url": "https://www.ntplc.co.th/en/news",
  "api_url": "",
  "items": [
    {
      "url": "https://www.ntplc.co.th/en/news/some-article",
      "title": "Article Title",
      "date": "2026-02-01",
      "summary": "Short description...",
      "content_hash": "abc123...",
      "raw_excerpt": "Cleaned body text..."
    }
  ]
}
```

## Diff Logic

- **New items**: URLs not present in the previous snapshot.
- **Updated items**: URLs present in both snapshots but with different `content_hash`. Includes a `changed_fields` note (title / summary / content).

## Cron Setup (Weekly)

Run every Monday at 08:00 UTC:

```cron
0 8 * * 1 cd /path/to/weekly-updates && /path/to/.venv/bin/python -m weekly_monitor run >> /var/log/weekly-monitor.log 2>&1
```

## GitHub Actions

Create `.github/workflows/weekly-monitor.yml`:

```yaml
name: Weekly Website Monitor

on:
  schedule:
    - cron: '0 8 * * 1'  # Every Monday at 08:00 UTC
  workflow_dispatch:       # Manual trigger

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          python -m playwright install --with-deps chromium

      - name: Run monitor
        run: python -m weekly_monitor run

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: weekly-report-${{ github.run_id }}
          path: output/
          retention-days: 90

      - name: Commit snapshots
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ output/
          git diff --staged --quiet || git commit -m "chore: weekly monitor run $(date +%Y-%m-%d)"
          git push
```

## Running Tests

```bash
pip install -r requirements.txt
PYTHONPATH=src pytest tests/ -v
```

## Environment Variables (Email)

| Variable        | Default           | Description                          |
|-----------------|-------------------|--------------------------------------|
| `SMTP_HOST`     | `smtp.gmail.com`  | SMTP server hostname                 |
| `SMTP_PORT`     | `587`             | SMTP server port (TLS)               |
| `SMTP_USER`     | *(required)*      | SMTP login username                  |
| `SMTP_PASSWORD` | *(required)*      | SMTP login password / app password   |
| `SMTP_FROM`     | = `SMTP_USER`     | Sender "From" address                |

> **Gmail users:** Create an [App Password](https://myaccount.google.com/apppasswords)
> and use it as `SMTP_PASSWORD`. Regular passwords won't work with 2FA enabled.

## Architecture Notes

- **Fail-safe**: Each site runs independently. If one adapter fails, the others continue and the report still generates.
- **Retry with backoff**: HTTP requests retry 3 times with exponential backoff (2s -> 4s -> 8s).
- **Structured logging**: JSON-lines to stderr for easy parsing.
- **Modular adapters**: Add a new site by creating `adapters/newsite.py` implementing the `SiteAdapter` interface and registering it in `cli.py`.

## License

Internal use.
