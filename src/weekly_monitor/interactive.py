"""Interactive terminal UI using Rich – select sites, watch live progress, get reports."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich import box

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

ALL_ADAPTERS: list[tuple[str, str, type[SiteAdapter]]] = [
    ("nt", "NT (National Telecom Thailand)", NTAdapter),
    ("unitel", "Unitel (Mongolia)", UnitelAdapter),
    ("skytel", "Skytel (Mongolia)", SkytelAdapter),
]

OUTPUT_ROOT = Path("output")

console = Console()


def run_interactive() -> None:
    """Main interactive entry point."""
    _print_banner()

    # --- Step 1: Select sites ---
    selected = _select_sites()
    if not selected:
        console.print("\n[yellow]No sites selected. Exiting.[/yellow]")
        return

    # --- Step 2: Options ---
    take_screenshots = Confirm.ask(
        "\n[bold]Take screenshots?[/bold]",
        default=True,
        console=console,
    )

    email_to = Prompt.ask(
        "[bold]Email report to[/bold] [dim](comma-separated, or press Enter to skip)[/dim]",
        default="",
        console=console,
    ).strip()

    # --- Step 2.5: Ensure Chromium is available ---
    needs_playwright = take_screenshots or any(
        a.site_key == "skytel" for a in selected
    )
    if needs_playwright:
        _ensure_chromium_interactive()

    # --- Step 3: Run with live progress ---
    console.print()
    run_date = date.today().isoformat()
    run_ts = f"{run_date}T{datetime.utcnow().strftime('%H:%M:%S')}"

    site_reports = _run_with_progress(selected, run_date, run_ts, take_screenshots)

    # --- Step 4: Generate report ---
    console.print()
    console.print("[bold blue]Generating report...[/bold blue]")
    report = WeeklyReport(run_date=run_date, sites=site_reports)
    out_dir = OUTPUT_ROOT / run_date
    md_path, html_path, pdf_path = write_reports(report, out_dir)

    _print_summary(report, html_path, md_path, pdf_path)

    # --- Step 5: Email ---
    if email_to:
        _handle_email(report, out_dir, email_to, run_date)

    # Show output paths
    from weekly_monitor.core.report import _get_downloads_dir
    downloads = _get_downloads_dir()
    dl_name = f"weekly_report_{run_date}"

    console.print(f"\n[bold green]All done![/bold green]\n")
    console.print("[bold]Reports saved to:[/bold]")
    console.print(f"  HTML: [link=file://{html_path.resolve()}]{html_path}[/link]")
    if pdf_path:
        console.print(f"  PDF:  [link=file://{pdf_path.resolve()}]{pdf_path}[/link]")
    console.print(f"\n[bold]Also in your Downloads folder:[/bold]")
    console.print(f"  {downloads / (dl_name + '.html')}")
    if pdf_path:
        console.print(f"  {downloads / (dl_name + '.pdf')}")
    console.print()


# ---------------------------------------------------------------------------
# Chromium auto-install
# ---------------------------------------------------------------------------

def _ensure_chromium_interactive() -> None:
    """Check for Chromium and offer to install it interactively."""
    from weekly_monitor.core.screenshots import chromium_installed, install_chromium

    if chromium_installed():
        return

    console.print("\n[yellow]Playwright Chromium browser is not installed.[/yellow]")
    console.print("[dim]Chromium is needed for screenshots and Skytel scraping.[/dim]\n")

    do_install = Confirm.ask(
        "[bold]Install Chromium now?[/bold] [dim](~150 MB download)[/dim]",
        default=True,
        console=console,
    )

    if not do_install:
        console.print("[yellow]Skipping Chromium install. Screenshots and Skytel will be unavailable.[/yellow]")
        return

    console.print("[bold blue]Downloading and installing Chromium...[/bold blue]\n")
    success = install_chromium(quiet=False)

    if success:
        console.print("[green]Chromium installed successfully.[/green]")
    else:
        console.print("[red]Chromium installation failed.[/red]")
        console.print("[dim]Try manually: python -m playwright install chromium[/dim]")


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    banner = Text()
    banner.append("Weekly Report", style="bold white")
    banner.append("  |  ", style="dim")
    banner.append("Website Change Monitor", style="dim")

    console.print()
    console.print(Panel(
        banner,
        border_style="blue",
        padding=(0, 2),
    ))


# ---------------------------------------------------------------------------
# Site selection
# ---------------------------------------------------------------------------

def _select_sites() -> list[SiteAdapter]:
    from weekly_monitor.adapters.custom import CustomAdapter

    console.print("\n[bold]Select sites to scan:[/bold]\n")

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Key", width=8)
    table.add_column("Site")
    table.add_column("URL", style="dim")

    for i, (key, name, cls) in enumerate(ALL_ADAPTERS, 1):
        a = cls()
        table.add_row(str(i), key, name, a.listing_url)

    table.add_row(
        str(len(ALL_ADAPTERS) + 1),
        "[cyan]custom[/cyan]",
        "[cyan]Enter your own URL[/cyan]",
        "",
    )

    console.print(table)

    choice = Prompt.ask(
        "\nEnter site numbers, keys, or 'custom' [dim](e.g. 1,2,3 or nt,unitel or 'all')[/dim]",
        default="all",
        console=console,
    ).strip().lower()

    if choice in ("all", "*", ""):
        return [cls() for _, _, cls in ALL_ADAPTERS]

    selected: list[SiteAdapter] = []
    tokens = [t.strip() for t in choice.split(",")]

    for token in tokens:
        matched = False

        # Check for 'custom' keyword or the custom number
        if token == "custom" or token == str(len(ALL_ADAPTERS) + 1):
            custom_adapters = _prompt_custom_urls()
            selected.extend(custom_adapters)
            matched = True
            continue

        # Try as number
        try:
            idx = int(token) - 1
            if 0 <= idx < len(ALL_ADAPTERS):
                selected.append(ALL_ADAPTERS[idx][2]())
                matched = True
        except ValueError:
            pass
        # Try as key
        if not matched:
            for key, _, cls in ALL_ADAPTERS:
                if token == key:
                    selected.append(cls())
                    matched = True
                    break
        if not matched:
            console.print(f"  [yellow]Unknown: {token}[/yellow]")

    if selected:
        names = ", ".join(a.site_name for a in selected)
        console.print(f"\n  Selected: [bold]{names}[/bold]")

    return selected


def _prompt_custom_urls() -> list[SiteAdapter]:
    """Prompt the user for one or more custom URLs to scan."""
    from weekly_monitor.adapters.custom import CustomAdapter

    adapters: list[SiteAdapter] = []
    console.print("\n[bold]Enter URLs to scan[/bold] [dim](one per line, empty line to finish)[/dim]\n")

    while True:
        url = Prompt.ask(
            "  URL",
            default="",
            console=console,
        ).strip()

        if not url:
            break

        # Basic validation
        if not url.startswith("http"):
            url = "https://" + url

        name = Prompt.ask(
            "  Name [dim](optional)[/dim]",
            default="",
            console=console,
        ).strip()

        adapters.append(CustomAdapter(url=url, name=name))
        console.print(f"  [green]Added: {url}[/green]\n")

    return adapters


# ---------------------------------------------------------------------------
# Live progress
# ---------------------------------------------------------------------------

def _run_with_progress(
    adapters: list[SiteAdapter],
    run_date: str,
    run_ts: str,
    take_screenshots: bool,
) -> list[SiteReport]:
    """Process all sites with a rich live progress display."""
    site_reports: list[SiteReport] = []
    logger = logging.getLogger("weekly_monitor.interactive")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        for adapter in adapters:
            task = progress.add_task(f"{adapter.site_name}", total=100)

            try:
                sr = _process_site_rich(
                    adapter, run_date, run_ts, take_screenshots, progress, task
                )
                site_reports.append(sr)
                progress.update(task, completed=100, description=f"[green]{adapter.site_name} [bold]done[/bold]")
            except Exception as exc:
                progress.update(task, completed=100, description=f"[red]{adapter.site_name} [bold]FAILED[/bold]")
                console.print(f"  [red]Error: {exc}[/red]")

    return site_reports


def _process_site_rich(
    adapter: SiteAdapter,
    run_date: str,
    run_ts: str,
    take_screenshots: bool,
    progress: Progress,
    task_id,
) -> SiteReport:
    """Process one site, updating progress bar at each step."""

    # Step 1: Fetch listing (0-20%)
    progress.update(task_id, completed=5, description=f"{adapter.site_name}: fetching listing...")
    raw = adapter.fetch_listing()

    # Step 2: Parse listing (20-35%)
    progress.update(task_id, completed=20, description=f"{adapter.site_name}: parsing...")
    items = adapter.parse_listing(raw)
    progress.update(task_id, completed=35, description=f"{adapter.site_name}: [cyan]{len(items)} items[/cyan]")

    # Step 3: Compute hashes (35-40%)
    for item in items:
        if not item.content_hash:
            item.compute_hash()
    progress.update(task_id, completed=40)

    # Step 4: Save snapshot (40-50%)
    progress.update(task_id, completed=45, description=f"{adapter.site_name}: saving snapshot...")
    snapshot = adapter.build_snapshot(items, run_ts)
    save_snapshot(snapshot)
    progress.update(task_id, completed=50)

    # Step 5: Diff (50-60%)
    progress.update(task_id, completed=55, description=f"{adapter.site_name}: computing diff...")
    prev = load_previous_snapshot(adapter.site_key, run_date)
    diff = diff_snapshots(snapshot, prev)
    new_count = len(diff.new_items)
    upd_count = len(diff.updated_items)
    progress.update(
        task_id, completed=60,
        description=f"{adapter.site_name}: [green]{new_count} new[/green], [yellow]{upd_count} updated[/yellow]",
    )

    # Step 6: Screenshots (60-95%)
    screenshots: list[ScreenshotRef] = []
    report_dir = OUTPUT_ROOT / run_date

    if take_screenshots:
        targets = adapter.screenshot_targets(
            [SnapshotItem(url=d.url, title=d.title, date=d.date, summary=d.summary)
             for d in diff.new_items]
        )
        if targets:
            progress.update(task_id, completed=65, description=f"{adapter.site_name}: taking {len(targets)} screenshots...")
            ss_dir = report_dir / "screenshots" / adapter.site_key
            try:
                loop = asyncio.new_event_loop()
                screenshots = loop.run_until_complete(
                    capture_screenshots(targets, ss_dir)
                )
                loop.close()
                for ref in screenshots:
                    try:
                        ref.file_path = str(Path(ref.file_path).relative_to(report_dir))
                    except ValueError:
                        pass
                progress.update(task_id, completed=95, description=f"{adapter.site_name}: {len(screenshots)} screenshots")
            except Exception:
                progress.update(task_id, completed=95, description=f"{adapter.site_name}: screenshots failed")
    else:
        progress.update(task_id, completed=95)

    return SiteReport(
        site_key=adapter.site_key,
        site_name=adapter.site_name,
        listing_url=adapter.listing_url,
        api_url=adapter.api_url,
        diff=diff,
        screenshots=screenshots,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(report: WeeklyReport, html_path: Path, md_path: Path, pdf_path: Path | None = None) -> None:
    """Print a results summary table."""
    console.print()

    table = Table(
        title=f"Report Summary — {report.run_date}",
        box=box.ROUNDED,
        title_style="bold white",
        header_style="bold cyan",
    )
    table.add_column("Site")
    table.add_column("New", justify="right", style="green")
    table.add_column("Updated", justify="right", style="yellow")
    table.add_column("Screenshots", justify="right", style="dim")

    for site in report.sites:
        table.add_row(
            site.site_name,
            str(len(site.diff.new_items)),
            str(len(site.diff.updated_items)),
            str(len(site.screenshots)),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _handle_email(report: WeeklyReport, out_dir: Path, email_to: str, run_date: str) -> None:
    import os

    recipients = [a.strip() for a in email_to.split(",") if a.strip()]
    if not recipients:
        return

    console.print()

    # Check if SMTP credentials are already in environment
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not smtp_user or not smtp_password:
        console.print("[bold]Email setup[/bold] [dim](credentials are not saved)[/dim]\n")

        smtp_host = Prompt.ask(
            "  SMTP host",
            default="smtp.gmail.com",
            console=console,
        ).strip()

        smtp_port = int(Prompt.ask(
            "  SMTP port",
            default="587",
            console=console,
        ).strip())

        smtp_user = Prompt.ask(
            "  Email address (login)",
            console=console,
        ).strip()

        smtp_password = Prompt.ask(
            "  Password / App password",
            password=True,
            console=console,
        ).strip()

        if not smtp_user or not smtp_password:
            console.print("[red]Email credentials required. Skipping email.[/red]")
            return

        console.print()
        console.print("[dim]Tip for Gmail: use an App Password from https://myaccount.google.com/apppasswords[/dim]")

    console.print()
    with console.status(f"[bold blue]Sending email to {', '.join(recipients)}...[/bold blue]"):
        try:
            html_body, cid_map = render_html_for_email(report, out_dir)
            subject = f"Weekly Website Change Report — {run_date}"
            from weekly_monitor.core.email_sender import send_report
            send_report(
                subject, html_body, cid_map, recipients,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
            )
            console.print(f"\n[green]Email sent to {', '.join(recipients)}[/green]")
        except Exception as exc:
            console.print(f"\n[red]Email failed: {exc}[/red]")
