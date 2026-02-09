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

Reports are automatically saved to:
- `output/<date>/weekly_report.html`
- `output/<date>/weekly_report.pdf`
- `~/Downloads/weekly_report_<date>.html`
- `~/Downloads/weekly_report_<date>.pdf`

## Custom URLs

In interactive mode, select option **4 (custom)** to enter any URL you want to scan. The tool will:
1. Open Chromium and render the page
2. Extract all internal links and content
3. Track changes between runs
4. Generate a report with screenshots

## Email

In interactive mode, enter email addresses when prompted. The tool will ask for your SMTP credentials (not stored). For headless mode, set environment variables:

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=your-app-password
weekly-monitor run --email-to "alice@example.com"
```

> **Gmail:** Use an [App Password](https://myaccount.google.com/apppasswords), not your regular password.

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
