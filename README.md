# Weekly Website Change Monitor

Automated scraper that tracks weekly changes on telecom operator websites and produces a structured change report (HTML + PDF) with screenshots.

## Monitored Sites

| Key      | Site                          | Strategy              |
|----------|-------------------------------|-----------------------|
| `nt`     | NT (National Telecom Thailand)| HTTP scraping (BS4)   |
| `unitel` | Unitel (Mongolia)             | JSON API + fallback   |
| `skytel` | Skytel (Mongolia)             | Playwright (JS)       |
| `custom` | Any URL you enter             | Playwright (JS)       |

## Installation

### macOS / Linux

```bash
curl -sSL https://raw.githubusercontent.com/Orshikhbayar/weekly-report/main/install.sh | bash
```

This automatically installs Python (if needed), all dependencies, and Chromium.

### Windows

Download and double-click `install.bat`, or run in Command Prompt:

```cmd
git clone https://github.com/Orshikhbayar/weekly-report.git
cd weekly-report
install.bat
```

### Manual install (any platform)

```bash
pip install git+https://github.com/Orshikhbayar/weekly-report.git
weekly-monitor install   # downloads Chromium (~150 MB, one-time)
```

## Usage

### Interactive mode (recommended)

```bash
weekly-monitor interactive
```

This walks you through:
1. **Site selection** -- pick preset sites by number/key, or enter any custom URL
2. **Options** -- screenshots, email delivery
3. **Live crawling** -- Chromium browser opens visibly so you can watch it work
4. **Summary table** -- new/updated items per site at a glance
5. **Reports** -- HTML + PDF saved to your Downloads folder

### Headless mode (cron / CI)

```bash
weekly-monitor run                            # runs all 3 preset sites: nt, unitel, skytel
weekly-monitor run --sites nt,unitel --no-screenshots
weekly-monitor run --email-to "team@example.com"
weekly-monitor run --visible-browser         # optional local debug mode
```

### Local config (`.env` auto-load)

The app now auto-loads environment variables from these files (first found values win, existing shell vars are never overridden):

1. `./.env` (current working directory)
2. `~/.config/weekly-monitor/env`
3. `~/.config/weekly-monitor/.env`

Create one of those files with your local secrets:

```env
OPENAI_API_KEY=sk-...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_16_char_gmail_app_password
SMTP_FROM=you@gmail.com
```

`.env` is already gitignored, so your secrets stay local.

### CLI Commands

| Command                      | Description                                          |
|------------------------------|------------------------------------------------------|
| `weekly-monitor interactive` | Interactive terminal UI with site selection + progress |
| `weekly-monitor run`         | Headless scrape (for cron/CI)                         |
| `weekly-monitor install`     | Download Playwright Chromium (one-time setup)          |

## Output

Reports are saved in two places:
- **Project folder:** `/Users/ddam-m0089/Desktop/weekly-updates/output/<date>/` (HTML, PDF, and `screenshots/` subfolder)
- **Downloads folder:** `~/Downloads/weekly_report_<date>/` — a folder containing `weekly_report.html`, `weekly_report.pdf`, and `screenshots/`. **Open the HTML file from inside this folder** so images load correctly.

Snapshots used for diffing are stored in:
- `/Users/ddam-m0089/Desktop/weekly-updates/data/<site_key>/`

If you ever want a different base folder, set:
- `WEEKLY_MONITOR_HOME=/your/custom/folder`

## How change detection works

Each run saves a **snapshot**: every page URL found plus a short fingerprint of each page’s text. On the next run the program compares:

- **New** = a URL that wasn’t in the previous snapshot (first time we see this page)  
- **Updated** = the same URL was seen before but its content (title, summary, or body) changed. The link is the same — only the text on the page is different.  

So “latest updates” are whatever is new or changed compared to the last time you ran the scan. Everything is stored in a `data/` folder on your computer; no account or server is required.

## Custom URLs

In interactive mode, select option **4 (custom)** to enter any URL you want to scan. The tool will:
1. Open Chromium and render the page
2. Extract all internal links and content
3. Track changes between runs
4. Generate a report with screenshots

## Email — what to enter

When the program asks to send the report by email, it will prompt:

| Prompt | What to enter |
|--------|----------------|
| **Email server** | Your provider’s SMTP server. Examples: `smtp.gmail.com` (Gmail), `smtp.office365.com` (Outlook). Press Enter to keep the default. |
| **Port** | Usually `587`. Press Enter for default. |
| **Your email address** | The address you send from (e.g. `you@gmail.com`). |
| **Password** | Your email password. **Gmail:** use an [App Password](https://myaccount.google.com/apppasswords), not your normal password (required if 2-step verification is on). |

Credentials are used only for that send and are not stored. If sending fails, check: correct server and port, and for Gmail that you’re using an App Password.

Email delivery includes:
- Inline screenshots preview in the HTML body (limited for email size safety)
- Attached file: `weekly_report.pdf` (contains screenshots as rendered in the report)
- Optional: set `SMTP_TIMEOUT` (seconds) in `.env` if your SMTP upload is slow (default: `120`)

## Cron Setup (Weekly)

```cron
0 8 * * 1 cd /path/to/weekly-report && .venv/bin/weekly-monitor run
```

If you store secrets in one of the auto-loaded env files above, cron does not need `source ...` commands.

## Architecture

- **Fail-safe**: Each site runs independently. If one fails, others continue.
- **Live browser**: Chromium opens visibly during crawling so you can watch.
- **Auto-install**: Interactive mode detects missing Chromium and offers to install it.
- **Cross-platform**: Works on macOS, Linux, and Windows.
- **Modular adapters**: Add a new site by implementing `SiteAdapter`.

## License

Internal use.
