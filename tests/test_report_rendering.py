"""Tests for report rendering safety and formatting."""

from weekly_monitor.core.models import WeeklyReport
from weekly_monitor.core.report import render_html


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
