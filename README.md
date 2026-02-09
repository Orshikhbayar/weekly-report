# Weekly Website Change Monitor

Automated scraper that tracks weekly changes on telecom operator websites and produces a structured change report (Markdown + HTML) with optional screenshots.

## Monitored Sites

| Key      | Site                          | Strategy              |
|----------|-------------------------------|-----------------------|
| `nt`     | NT (National Telecom Thailand)| HTTP scraping (BS4)   |
| `unitel` | Unitel (Mongolia)             | JSON API + fallback   |
| `skytel` | Skytel (Mongolia)             | Playwright (JS)       |

## Installation

### Option A — One-liner (easiest)

```bash
curl -sSL https://raw.githubusercontent.com/Orshikhbayar/weekly-report/main/install.sh | bash
```

This clones the repo, creates a virtualenv, installs all Python dependencies, and downloads Chromium automatically.

### Option B — pip install from GitHub

```bash
pip install git+https://github.com/Orshikhbayar/weekly-report.git
weekly-monitor install   # downloads Chromium (~150 MB, one-time)
```

### Option C — Clone and install

```bash
git clone https://github.com/Orshikhbayar/weekly-report.git
cd weekly-report
pip install .
weekly-monitor install   # downloads Chromium (~150 MB, one-time)
```

> **Note:** Requires Python 3.11+. The `weekly-monitor install` step downloads the
> Chromium browser needed for screenshots and Skytel scraping. You only need to run
> it once.

## Usage

### Interactive mode (recommended)

```bash
weekly-monitor interactive
```

This walks you through:
1. **Site selection** -- pick which sites to scan (by number, key, or `all`)
2. **Options** -- screenshots, email, Vercel deploy
3. **Live progress** -- spinner + progress bars as each site is scraped
4. **Summary table** -- new/updated items per site at a glance

If Chromium is not installed, interactive mode will offer to install it for you automatically.

### Headless mode (cron / CI)

```bash
# Today's date (default)
weekly-monitor run

# Specific date
weekly-monitor run --date 2026-02-09

# Skip screenshots (faster)
weekly-monitor run --no-screenshots

# Run only specific sites
weekly-monitor run --sites nt,unitel

# Verbose logging
weekly-monitor run -v
```

### Share the report

#### Deploy to Vercel (public URL, no account required)

```bash
weekly-monitor run --deploy
```

#### Send via email

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=your-app-password

weekly-monitor run --email-to "alice@example.com,bob@example.com"
```

#### Both at once

```bash
weekly-monitor run --deploy --email-to "team@example.com"
```

### View the report locally

```
output/<date>/weekly_report.md
output/<date>/weekly_report.html
output/<date>/screenshots/<site_key>/*.png
```

## CLI Commands

| Command                      | Description                                          |
|------------------------------|------------------------------------------------------|
| `weekly-monitor interactive` | Interactive terminal UI with site selection + progress |
| `weekly-monitor run`         | Headless scrape (for cron/CI)                         |
| `weekly-monitor install`     | Download Playwright Chromium browser (one-time setup)  |

## Project Structure

```
weekly-report/
├── src/weekly_monitor/
│   ├── __init__.py
│   ├── __main__.py           # python -m weekly_monitor entrypoint
│   ├── cli.py                # Click CLI (install, run, interactive)
│   ├── interactive.py        # Rich interactive terminal UI
│   ├── adapters/
│   │   ├── base.py           # Abstract SiteAdapter class
│   │   ├── nt.py             # NT (ntplc.co.th) adapter
│   │   ├── unitel.py         # Unitel (unitel.mn) adapter
│   │   └── skytel.py         # Skytel (skytel.mn) adapter
│   └── core/
│       ├── models.py         # Pydantic data models
│       ├── storage.py        # JSON snapshot persistence
│       ├── http.py           # HTTP client (httpx + retries)
│       ├── diff.py           # Diff engine (new/updated items)
│       ├── screenshots.py    # Playwright screenshot capture + Chromium check
│       ├── report.py         # Markdown + HTML report generation
│       └── email_sender.py   # SMTP email with inline images
├── templates/
│   └── weekly_report.html    # Jinja2 HTML template
├── install.sh                # One-command installer
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
  "items": [
    {
      "url": "https://www.ntplc.co.th/en/news/some-article",
      "title": "Article Title",
      "date": "2026-02-01",
      "summary": "Short description...",
      "content_hash": "abc123..."
    }
  ]
}
```

## Diff Logic

- **New items**: URLs not present in the previous snapshot.
- **Updated items**: URLs present in both but with different `content_hash`. Includes `changed_fields` (title / summary / content).

## Cron Setup (Weekly)

```cron
0 8 * * 1 cd /path/to/weekly-report && .venv/bin/weekly-monitor run >> /var/log/weekly-monitor.log 2>&1
```

## GitHub Actions

```yaml
name: Weekly Website Monitor

on:
  schedule:
    - cron: '0 8 * * 1'
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install . && weekly-monitor install
      - run: weekly-monitor run
      - uses: actions/upload-artifact@v4
        with:
          name: weekly-report-${{ github.run_id }}
          path: output/
          retention-days: 90
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
> and use it as `SMTP_PASSWORD`.

## Architecture Notes

- **Fail-safe**: Each site runs independently. If one fails, others continue.
- **Retry with backoff**: HTTP requests retry 3x with exponential backoff.
- **Auto-install**: Interactive mode detects missing Chromium and offers to install it.
- **Modular adapters**: Add a new site by implementing `SiteAdapter` and registering in `cli.py`.

## License

Internal use.
