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
weekly-monitor run
weekly-monitor run --sites nt,unitel --no-screenshots
weekly-monitor run --email-to "team@example.com"
```

### CLI Commands

| Command                      | Description                                          |
|------------------------------|------------------------------------------------------|
| `weekly-monitor interactive` | Interactive terminal UI with site selection + progress |
| `weekly-monitor run`         | Headless scrape (for cron/CI)                         |
| `weekly-monitor install`     | Download Playwright Chromium (one-time setup)          |

## Output

Reports are saved in two places:
- **Project folder:** `output/<date>/` (HTML, PDF, and `screenshots/` subfolder)
- **Downloads folder:** `~/Downloads/weekly_report_<date>/` — a folder containing `weekly_report.html`, `weekly_report.pdf`, and `screenshots/`. **Open the HTML file from inside this folder** so images load correctly.

## How change detection works

Each run saves a **snapshot**: every page URL found plus a short fingerprint of each page’s text. On the next run the program compares:

- **New** = a URL that wasn’t in the previous snapshot  
- **Updated** = same URL but the content fingerprint changed  

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

## Cron Setup (Weekly)

```cron
0 8 * * 1 cd /path/to/weekly-report && .venv/bin/weekly-monitor run
```

## Architecture

- **Fail-safe**: Each site runs independently. If one fails, others continue.
- **Live browser**: Chromium opens visibly during crawling so you can watch.
- **Auto-install**: Interactive mode detects missing Chromium and offers to install it.
- **Cross-platform**: Works on macOS, Linux, and Windows.
- **Modular adapters**: Add a new site by implementing `SiteAdapter`.

## License

Internal use.
