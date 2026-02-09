"""Report generation – Markdown and HTML from Jinja2 templates."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from weekly_monitor.core.models import WeeklyReport

logger = logging.getLogger(__name__)

# Locate templates: check bundled package data first, then project root, then CWD.
_TEMPLATES_SEARCH = [
    Path(__file__).resolve().parent.parent / "data" / "templates",  # pip install
    Path(__file__).resolve().parent.parent.parent.parent / "templates",  # source checkout
    Path("templates"),  # CWD fallback
]


def _env() -> Environment:
    """Build Jinja2 environment searching known template paths."""
    dirs = [str(d) for d in _TEMPLATES_SEARCH if d.is_dir()]
    return Environment(
        loader=FileSystemLoader(dirs),
        autoescape=select_autoescape(
            enabled_extensions=("html", "htm", "xml"),
            default_for_string=True,
        ),
    )


def render_markdown(report: WeeklyReport) -> str:
    """Produce a Markdown report string."""
    lines: list[str] = []
    lines.append(f"# Weekly Website Change Report – {report.run_date}")
    lines.append(f"Generated at: {report.generated_at}\n")

    if report.ai_summary_mn:
        lines.append("## AI Тайлбар\n")
        lines.append(report.ai_summary_mn)
        lines.append("\n---\n")

    for site in report.sites:
        diff = site.diff
        new_count = len(diff.new_items)
        updated_count = len(diff.updated_items)

        lines.append(f"## {site.site_name}")
        lines.append(f"**New items:** {new_count} | **Updated items:** {updated_count}\n")

        # Source pages
        lines.append("### Source pages")
        lines.append(f"- Listing URL: {site.listing_url}")
        if site.api_url:
            lines.append(f"- API endpoint: {site.api_url}")
        lines.append("")

        if diff.new_items:
            lines.append("### New items")
            for item in diff.new_items:
                date_part = f" ({item.date})" if item.date else ""
                lines.append(f"- **{item.title}**{date_part}")
                lines.append(f"  {item.url}")
                if item.summary:
                    lines.append(f"  > {item.summary[:300]}")
            lines.append("")

        if diff.updated_items:
            lines.append("### Updated items")
            for item in diff.updated_items:
                changed = ", ".join(item.changed_fields) if item.changed_fields else "content"
                lines.append(f"- **{item.title}** — changed: {changed}")
                lines.append(f"  {item.url}")
                if item.summary:
                    lines.append(f"  > {item.summary[:300]}")
            lines.append("")

        if not diff.new_items and not diff.updated_items:
            lines.append("_No changes detected since last run._\n")

        # Screenshots
        if site.screenshots:
            lines.append("### Screenshots")
            for ss in site.screenshots:
                rel = ss.file_path
                lines.append(f"- [{ss.label}]({rel})")
                lines.append(f"  Page URL: {ss.page_url}")
                lines.append(f"  ![{ss.label}]({rel})")
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)


def render_html(report: WeeklyReport) -> str:
    """Render HTML report using Jinja2 template."""
    env = _env()
    try:
        tmpl = env.get_template("weekly_report.html")
    except Exception:
        logger.warning("Jinja2 template not found; generating minimal HTML")
        return _fallback_html(report)

    return tmpl.render(report=report)


def render_html_for_email(
    report: WeeklyReport,
    output_dir: Path,
    *,
    max_inline_images: int | None = None,
) -> tuple[str, dict[str, Path]]:
    """Render HTML with ``cid:`` image references for email embedding.

    Returns ``(html_string, cid_map)`` where *cid_map* maps each
    Content-ID (without angle brackets) to the absolute file path of
    the image on disk.
    """
    html = render_html(report)

    # Build a mapping: relative_path -> cid  (and collect files)
    cid_map: dict[str, Path] = {}
    counter = 0

    def _replace_src(match: re.Match) -> str:
        nonlocal counter
        if max_inline_images is not None and counter >= max_inline_images:
            return match.group(0)
        rel_path = match.group(1)
        abs_path = output_dir / rel_path
        if not abs_path.exists():
            return match.group(0)  # leave unchanged
        cid = f"img{counter}@weekly-monitor"
        counter += 1
        cid_map[cid] = abs_path
        return f'src="cid:{cid}"'

    html = re.sub(r'src="(screenshots/[^"]+)"', _replace_src, html)
    return html, cid_map


def _get_downloads_dir() -> Path:
    """Return the user's Downloads folder (cross-platform)."""
    import sys
    if sys.platform == "win32":
        # Windows: use USERPROFILE/Downloads or KNOWNFOLDERID
        downloads = Path.home() / "Downloads"
    elif sys.platform == "darwin":
        downloads = Path.home() / "Downloads"
    else:
        # Linux: try XDG, fall back to ~/Downloads
        import subprocess
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DOWNLOAD"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                downloads = Path(result.stdout.strip())
            else:
                downloads = Path.home() / "Downloads"
        except Exception:
            downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads


def generate_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Convert an HTML report to PDF using Playwright.

    Returns True on success.
    """
    import asyncio

    async def _to_pdf() -> None:
        from playwright.async_api import async_playwright
        # Use file URL so relative paths (screenshots/*) resolve from HTML's directory
        file_url = f"file://{html_path.resolve()}"
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(file_url, wait_until="networkidle", timeout=15_000)
            # Give images time to decode so they appear in PDF
            await page.wait_for_timeout(1500)
            await page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
            )
            await browser.close()

    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_to_pdf())
        loop.close()
        logger.info("PDF report written to %s", pdf_path)
        return True
    except Exception:
        logger.exception("PDF generation failed")
        return False


def write_reports(report: WeeklyReport, output_dir: Path) -> tuple[Path, Path, Path | None]:
    """Write Markdown + HTML + PDF reports and return their paths.

    Reports are written to the project output dir AND copied to the
    user's Downloads folder.  Returns ``(md_path, html_path, pdf_path)``.
    """
    import shutil

    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "weekly_report.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    logger.info("Markdown report written to %s", md_path)

    html_content = render_html(report)

    html_path = output_dir / "weekly_report.html"
    html_path.write_text(html_content, encoding="utf-8")
    logger.info("HTML report written to %s", html_path)

    # Generate PDF
    pdf_path = output_dir / "weekly_report.pdf"
    pdf_ok = generate_pdf(html_path, pdf_path)
    if not pdf_ok:
        pdf_path = None

    # Copy full report folder to Downloads so HTML can load screenshots
    try:
        downloads = _get_downloads_dir()
        dl_folder_name = f"weekly_report_{report.run_date}"
        dl_folder = downloads / dl_folder_name
        if dl_folder.exists():
            shutil.rmtree(dl_folder)
        dl_folder.mkdir(parents=True)

        # Copy HTML and PDF
        shutil.copy2(html_path, dl_folder / "weekly_report.html")
        if pdf_path and pdf_path.exists():
            shutil.copy2(pdf_path, dl_folder / "weekly_report.pdf")
        # Copy screenshots folder so <img src="screenshots/..."> works
        ss_src = output_dir / "screenshots"
        if ss_src.exists():
            shutil.copytree(ss_src, dl_folder / "screenshots")
        logger.info("Report folder copied to Downloads: %s", dl_folder)
    except Exception:
        logger.exception("Failed to copy reports to Downloads folder")

    return md_path, html_path, pdf_path


# ---------------------------------------------------------------------------
# Minimal fallback HTML (in case template is missing)
# ---------------------------------------------------------------------------

def _fallback_html(report: WeeklyReport) -> str:
    md = render_markdown(report)
    escaped = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Weekly Report – {report.run_date}</title></head>"
        f"<body><pre>{escaped}</pre></body></html>"
    )
