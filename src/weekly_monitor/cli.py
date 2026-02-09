"""CLI entrypoint – ``python -m weekly_monitor run [--date YYYY-MM-DD]``."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

import click

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.adapters.nt import NTAdapter
from weekly_monitor.adapters.skytel import SkytelAdapter
from weekly_monitor.adapters.unitel import UnitelAdapter
from weekly_monitor.core.diff import diff_snapshots
from weekly_monitor.core.models import (
    ScreenshotRef,
    SiteDiff,
    SiteReport,
    SnapshotItem,
    WeeklyReport,
)
from weekly_monitor.core.report import render_html_for_email, write_reports
from weekly_monitor.core.screenshots import capture_screenshots
from weekly_monitor.core.storage import load_previous_snapshot, save_snapshot

ALL_ADAPTERS: list[type[SiteAdapter]] = [NTAdapter, UnitelAdapter, SkytelAdapter]

OUTPUT_ROOT = Path("output")

# Locate the bundled deploy.sh – check package data first, then project root
_PKG_DIR = Path(__file__).resolve().parent
_DEPLOY_SCRIPT_CANDIDATES = [
    _PKG_DIR / "data" / "scripts" / "deploy.sh",  # pip install
    _PKG_DIR.parent.parent / "scripts" / "deploy.sh",  # source checkout
]
_DEPLOY_SCRIPT = next((p for p in _DEPLOY_SCRIPT_CANDIDATES if p.exists()), _DEPLOY_SCRIPT_CANDIDATES[-1])


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
@click.option("--deploy", is_flag=True, help="Deploy HTML report to Vercel for a public URL.")
@click.option("--email-to", default=None, help="Send report via email. Comma-separated addresses.")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def run(
    run_date: str | None,
    no_screenshots: bool,
    no_details: bool,
    sites: str | None,
    deploy: bool,
    email_to: str | None,
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
            sr = _process_site(adapter, run_date, run_ts, no_screenshots, no_details, logger)
            site_reports.append(sr)
        except Exception:
            logger.exception("Site %s FAILED – continuing with remaining sites", adapter.site_key)

    # Build report
    report = WeeklyReport(run_date=run_date, sites=site_reports)
    out_dir = OUTPUT_ROOT / run_date
    md_path, html_path = write_reports(report, out_dir)

    click.echo(f"\nReport written to:\n  {md_path}\n  {html_path}")

    # ------------------------------------------------------------------
    # Optional: Deploy to Vercel
    # ------------------------------------------------------------------
    if deploy:
        _deploy_to_vercel(out_dir, logger)

    # ------------------------------------------------------------------
    # Optional: Send via email
    # ------------------------------------------------------------------
    if email_to:
        recipients = [addr.strip() for addr in email_to.split(",") if addr.strip()]
        _send_email(report, out_dir, recipients, run_date, logger)


def _deploy_to_vercel(out_dir: Path, logger: logging.Logger) -> None:
    """Deploy the output directory to Vercel using scripts/deploy.sh.

    To stay under Vercel's upload size limit, screenshots are resized to
    thumbnail quality before packaging (requires Pillow, falls back to
    excluding them if unavailable).
    """
    import tempfile

    if not _DEPLOY_SCRIPT.exists():
        logger.error("Deploy script not found at %s", _DEPLOY_SCRIPT)
        click.echo("Error: scripts/deploy.sh not found. Cannot deploy.", err=True)
        return

    click.echo("\nPreparing deploy package...")

    # Build a slim staging copy: HTML + lightweight screenshots
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "site"
        stage.mkdir()

        # Copy screenshots, compressing to JPEG thumbnails if possible
        ss_src = out_dir / "screenshots"
        used_jpg = False
        if ss_src.exists():
            used_jpg = _copy_screenshots_compressed(ss_src, stage / "screenshots", logger)

        # Copy HTML files, rewriting .png -> .jpg refs if we compressed
        for html in out_dir.glob("*.html"):
            content = html.read_text(encoding="utf-8")
            if used_jpg:
                import re as _re
                content = _re.sub(
                    r'(screenshots/[^"]+)\.png',
                    r'\1.jpg',
                    content,
                )
            (stage / html.name).write_text(content, encoding="utf-8")
        for md in out_dir.glob("*.md"):
            shutil.copy2(md, stage / md.name)

        click.echo("Deploying to Vercel...")
        try:
            result = subprocess.run(
                ["bash", str(_DEPLOY_SCRIPT), str(stage)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.stderr:
                click.echo(result.stderr, err=True)
            if result.returncode == 0 and result.stdout.strip():
                try:
                    deploy_data = json.loads(result.stdout.strip())
                    preview_url = deploy_data.get("previewUrl", "")
                    claim_url = deploy_data.get("claimUrl", "")
                    if preview_url:
                        click.echo(f"\nPublic report URL: {preview_url}")
                    if claim_url:
                        click.echo(f"Claim URL (transfer to your Vercel account): {claim_url}")
                except json.JSONDecodeError:
                    click.echo(result.stdout)
            elif result.returncode != 0:
                logger.error("Deploy failed (exit %d): %s", result.returncode, result.stderr)
                click.echo("Deploy failed. See logs above.", err=True)
        except subprocess.TimeoutExpired:
            logger.error("Deploy timed out after 120s")
            click.echo("Deploy timed out.", err=True)
        except Exception:
            logger.exception("Deploy failed unexpectedly")


def _copy_screenshots_compressed(
    src: Path, dest: Path, logger: logging.Logger
) -> bool:
    """Copy screenshots, converting PNGs to smaller JPEGs if Pillow is available.

    Returns True if JPEG conversion was used.
    """
    try:
        from PIL import Image

        _has_pillow = True
    except ImportError:
        _has_pillow = False
        logger.info("Pillow not installed – copying screenshots as-is (may be large)")

    for site_dir in src.iterdir():
        if not site_dir.is_dir():
            continue
        dest_site = dest / site_dir.name
        dest_site.mkdir(parents=True, exist_ok=True)

        for img_file in site_dir.iterdir():
            if not img_file.is_file():
                continue
            if _has_pillow and img_file.suffix.lower() == ".png":
                # Convert to JPEG at 60% quality, max 1200px wide
                try:
                    with Image.open(img_file) as im:
                        im = im.convert("RGB")
                        w, h = im.size
                        if w > 1200:
                            ratio = 1200 / w
                            im = im.resize((1200, int(h * ratio)), Image.LANCZOS)
                        jpg_name = img_file.stem + ".jpg"
                        im.save(dest_site / jpg_name, "JPEG", quality=60, optimize=True)
                    continue
                except Exception:
                    logger.warning("Failed to compress %s, copying original", img_file)
            shutil.copy2(img_file, dest_site / img_file.name)

    return _has_pillow


def _send_email(
    report: "WeeklyReport",
    out_dir: Path,
    recipients: list[str],
    run_date: str,
    logger: logging.Logger,
) -> None:
    """Send the HTML report with inline screenshots via email."""
    from weekly_monitor.core.email_sender import send_report

    click.echo(f"\nSending report to {', '.join(recipients)}...")
    try:
        html_body, cid_map = render_html_for_email(report, out_dir)
        subject = f"Weekly Website Change Report – {run_date}"
        send_report(subject, html_body, cid_map, recipients)
        click.echo("Email sent successfully.")
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
                    capture_screenshots(targets, ss_dir)
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
