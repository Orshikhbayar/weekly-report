"""CLI entrypoint – ``python -m weekly_monitor run [--date YYYY-MM-DD]``."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import click

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.adapters.nt import NTAdapter
from weekly_monitor.adapters.skytel import SkytelAdapter
from weekly_monitor.adapters.unitel import UnitelAdapter
from weekly_monitor.core.diff import diff_snapshots
from weekly_monitor.core.models import (
    ScreenshotRef,
    SiteReport,
    SnapshotItem,
    WeeklyReport,
)
from weekly_monitor.core.report import render_html_for_email, write_reports
from weekly_monitor.core.screenshots import capture_screenshots
from weekly_monitor.core.storage import load_previous_snapshot, save_snapshot

ALL_ADAPTERS: list[type[SiteAdapter]] = [NTAdapter, UnitelAdapter, SkytelAdapter]

OUTPUT_ROOT = Path("output")


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "ts": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj)


def _setup_logging(verbose: bool = False) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def main():
    """Weekly website change monitor."""


@main.command()
def install():
    """Install required browsers (Chromium) for Playwright."""
    from weekly_monitor.core.screenshots import chromium_installed, install_chromium

    if chromium_installed():
        click.echo("Chromium is already installed. Nothing to do.")
        return

    click.echo("Installing Playwright Chromium browser...")
    if install_chromium():
        click.echo("Chromium installed successfully.")
    else:
        click.echo("Chromium installation failed. Try manually: python -m playwright install chromium", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--date", "run_date", default=None, help="Run date (YYYY-MM-DD). Defaults to today.")
@click.option("--no-screenshots", is_flag=True, help="Skip screenshot capture.")
@click.option("--no-details", is_flag=True, help="Skip detail-page fetching.")
@click.option("--sites", default=None, help="Comma-separated site keys to run (e.g. nt,unitel).")
@click.option("--email-to", default=None, help="Send report via email. Comma-separated addresses.")
@click.option(
    "--headless/--visible-browser",
    default=True,
    help="Run Playwright browsers in headless mode (recommended for cron/CI).",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def run(
    run_date: str | None,
    no_screenshots: bool,
    no_details: bool,
    sites: str | None,
    email_to: str | None,
    headless: bool,
    verbose: bool,
):
    """Execute a weekly scrape run."""
    _setup_logging(verbose)
    logger = logging.getLogger("weekly_monitor.cli")

    if run_date is None:
        run_date = date.today().isoformat()

    run_ts = f"{run_date}T{datetime.utcnow().strftime('%H:%M:%S')}"
    logger.info("Starting run for date=%s", run_date)

    # Filter adapters
    selected_keys: set[str] | None = None
    if sites:
        selected_keys = {s.strip().lower() for s in sites.split(",")}

    adapters: list[SiteAdapter] = []
    for cls in ALL_ADAPTERS:
        a = cls()
        if selected_keys and a.site_key not in selected_keys:
            continue
        adapters.append(a)

    if not adapters:
        logger.error("No adapters selected – nothing to do.")
        raise SystemExit(1)

    # Adapters that use Playwright (Skytel/custom) honor this runtime flag.
    for adapter in adapters:
        setattr(adapter, "headless", headless)

    # Check if Chromium is needed and available
    from weekly_monitor.core.screenshots import chromium_installed
    needs_playwright = (not no_screenshots) or any(a.site_key == "skytel" for a in adapters)
    if needs_playwright and not chromium_installed():
        logger.warning(
            "Playwright Chromium is not installed. "
            "Screenshots and Skytel will fail. "
            "Run: weekly-monitor install"
        )
        click.echo(
            "Warning: Chromium not installed. Run 'weekly-monitor install' first.",
            err=True,
        )

    site_reports: list[SiteReport] = []

    for adapter in adapters:
        logger.info("=== Processing site: %s ===", adapter.site_key)
        try:
            sr = _process_site(adapter, run_date, run_ts, no_screenshots, no_details, headless, logger)
            site_reports.append(sr)
        except Exception:
            logger.exception("Site %s FAILED – continuing with remaining sites", adapter.site_key)

    # Build report
    report = WeeklyReport(run_date=run_date, sites=site_reports)

    # AI-generated Mongolian summary (requires OPENAI_API_KEY)
    from weekly_monitor.core.ai_report import generate_mongolian_summary
    ai_text = generate_mongolian_summary(report)
    if ai_text:
        report.ai_summary_mn = ai_text
        click.echo("AI summary generated (Mongolian).")

    out_dir = OUTPUT_ROOT / run_date
    md_path, html_path, pdf_path = write_reports(report, out_dir)

    click.echo(f"\nReport written to:\n  {md_path}\n  {html_path}")
    if pdf_path:
        click.echo(f"  {pdf_path}")

    # ------------------------------------------------------------------
    # Optional: Send via email
    # ------------------------------------------------------------------
    if email_to:
        recipients = [addr.strip() for addr in email_to.split(",") if addr.strip()]
        _send_email(report, out_dir, recipients, run_date, logger)


def _send_email(
    report: "WeeklyReport",
    out_dir: Path,
    recipients: list[str],
    run_date: str,
    logger: logging.Logger,
) -> None:
    """Send the HTML report with inline screenshots via email."""
    from weekly_monitor.core.email_sender import SmtpAuthError, send_report

    click.echo(f"\nSending report to {', '.join(recipients)}...")
    try:
        html_body, cid_map = render_html_for_email(report, out_dir)
        subject = f"Weekly Website Change Report – {run_date}"
        send_report(subject, html_body, cid_map, recipients)
        click.echo("Email sent successfully.")
    except SmtpAuthError as exc:
        logger.error("Email authentication failed: %s", exc)
        click.echo(
            "\nGmail rejected your credentials (535).\n"
            "You must use an App Password, not your normal Google password.\n"
            "  1. Enable 2-Step Verification on your Google account.\n"
            "  2. Create an App Password: https://myaccount.google.com/apppasswords\n"
            "  3. Use that 16-character App Password.\n"
            "More info: https://support.google.com/mail/?p=BadCredentials",
            err=True,
        )
    except RuntimeError as exc:
        # Missing SMTP config
        click.echo(f"Email error: {exc}", err=True)
        logger.error("Email not sent: %s", exc)
    except Exception:
        logger.exception("Email sending failed")
        click.echo("Email sending failed. See logs.", err=True)


def _process_site(
    adapter: SiteAdapter,
    run_date: str,
    run_ts: str,
    no_screenshots: bool,
    no_details: bool,
    headless: bool,
    logger: logging.Logger,
) -> SiteReport:
    """Scrape one site, diff, screenshot, return SiteReport."""
    # 1. Fetch & parse listing
    raw = adapter.fetch_listing()
    items = adapter.parse_listing(raw)
    logger.info("%s: %d items from listing", adapter.site_key, len(items))

    # 2. Optionally fetch details for each item
    if not no_details:
        for item in items:
            detail_raw = adapter.fetch_detail(item)
            if detail_raw:
                adapter.parse_detail(item, detail_raw)

    # 3. Build & save snapshot
    snapshot = adapter.build_snapshot(items, run_ts)
    save_snapshot(snapshot)
    logger.info("%s: snapshot saved", adapter.site_key)

    # 4. Diff against previous
    prev = load_previous_snapshot(adapter.site_key, run_date)
    diff = diff_snapshots(snapshot, prev)
    logger.info(
        "%s: diff => %d new, %d updated",
        adapter.site_key,
        len(diff.new_items),
        len(diff.updated_items),
    )

    # 5. Screenshots
    screenshots: list[ScreenshotRef] = []
    report_dir = OUTPUT_ROOT / run_date  # where the HTML report lives
    if not no_screenshots:
        targets = adapter.screenshot_targets(
            [SnapshotItem(url=d.url, title=d.title, date=d.date, summary=d.summary)
             for d in diff.new_items]
        )
        if targets:
            ss_dir = report_dir / "screenshots" / adapter.site_key
            try:
                loop = asyncio.new_event_loop()
                screenshots = loop.run_until_complete(
                    capture_screenshots(
                        targets, ss_dir,
                        prefer_language=getattr(adapter, "prefer_language", ""),
                        headless=headless,
                    )
                )
                loop.close()
                # Make file_path relative to the report directory so that
                # <img src="..."> works when the HTML is opened in a browser.
                for ref in screenshots:
                    try:
                        ref.file_path = str(
                            Path(ref.file_path).relative_to(report_dir)
                        )
                    except ValueError:
                        pass  # keep absolute if it can't be made relative
            except Exception:
                logger.exception("%s: screenshot capture failed", adapter.site_key)

    return SiteReport(
        site_key=adapter.site_key,
        site_name=adapter.site_name,
        listing_url=adapter.listing_url,
        api_url=adapter.api_url,
        diff=diff,
        screenshots=screenshots,
    )


@main.command(name="interactive")
def interactive_cmd():
    """Launch interactive mode – select sites, watch live progress, get reports."""
    from weekly_monitor.interactive import run_interactive
    run_interactive()


if __name__ == "__main__":
    main()
