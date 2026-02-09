"""Tests for report rendering safety and formatting."""

from pathlib import Path

from weekly_monitor.core.models import ScreenshotRef, SiteDiff, SiteReport, WeeklyReport
from weekly_monitor.core.report import render_html, render_html_for_email


def test_render_html_escapes_ai_summary_content() -> None:
    report = WeeklyReport(
        run_date="2026-02-09",
        ai_summary_mn="<script>alert(1)</script>\nМэдээлэл",
        sites=[],
    )

    html = render_html(report)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "ai-summary-body" in html


def test_render_html_for_email_caps_inline_images(tmp_path: Path) -> None:
    ss_rel = [
        "screenshots/nt/a.png",
        "screenshots/nt/b.png",
        "screenshots/nt/c.png",
        "screenshots/nt/d.png",
    ]
    for rel in ss_rel:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fakepng")

    report = WeeklyReport(
        run_date="2026-02-09",
        sites=[
            SiteReport(
                site_key="nt",
                site_name="NT",
                listing_url="https://example.com/news",
                diff=SiteDiff(site_key="nt"),
                screenshots=[
                    ScreenshotRef(page_url="https://example.com/a", file_path=ss_rel[0], label="a"),
                    ScreenshotRef(page_url="https://example.com/b", file_path=ss_rel[1], label="b"),
                    ScreenshotRef(page_url="https://example.com/c", file_path=ss_rel[2], label="c"),
                    ScreenshotRef(page_url="https://example.com/d", file_path=ss_rel[3], label="d"),
                ],
            )
        ],
    )

    html, cid_map = render_html_for_email(report, tmp_path, max_inline_images=2)

    assert len(cid_map) == 2
    assert html.count('src="cid:') == 2
