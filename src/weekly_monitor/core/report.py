"""Report generation – Markdown and HTML from Jinja2 templates."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

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
    return Environment(loader=FileSystemLoader(dirs), autoescape=False)


def render_markdown(report: WeeklyReport) -> str:
    """Produce a Markdown report string."""
    lines: list[str] = []
    lines.append(f"# Weekly Website Change Report – {report.run_date}")
    lines.append(f"Generated at: {report.generated_at}\n")

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


def render_html_for_email(report: WeeklyReport, output_dir: Path) -> tuple[str, dict[str, Path]]:
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


def write_reports(report: WeeklyReport, output_dir: Path) -> tuple[Path, Path]:
    """Write Markdown + HTML reports and return their paths.

    The HTML is also written as ``index.html`` (for static-site deploy)
    in addition to ``weekly_report.html``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "weekly_report.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    logger.info("Markdown report written to %s", md_path)

    html_content = render_html(report)

    html_path = output_dir / "weekly_report.html"
    html_path.write_text(html_content, encoding="utf-8")
    logger.info("HTML report written to %s", html_path)

    # Also write index.html so Vercel / any static host serves it at "/"
    index_path = output_dir / "index.html"
    index_path.write_text(html_content, encoding="utf-8")

    return md_path, html_path


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
