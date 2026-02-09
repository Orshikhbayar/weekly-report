"""CLI behavior tests."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from click.testing import CliRunner

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.core.models import SiteDiff, SiteReport, WeeklyReport


class _FakeAdapter(SiteAdapter):
    site_key = "fake"
    site_name = "Fake Site"
    listing_url = "https://example.com/news"

    def fetch_listing(self) -> str:
        return ""

    def parse_listing(self, raw: str):
        return []


@pytest.mark.parametrize(
    ("extra_args", "expected_headless"),
    [
        ([], True),
        (["--visible-browser"], False),
    ],
)
def test_run_sets_adapter_headless(monkeypatch, tmp_path: Path, extra_args, expected_headless) -> None:
    from weekly_monitor import cli

    seen: dict[str, bool] = {}

    def fake_process_site(
        adapter: SiteAdapter,
        run_date: str,
        run_ts: str,
        no_screenshots: bool,
        no_details: bool,
        headless: bool,
        logger: logging.Logger,
    ) -> SiteReport:
        seen["adapter_headless"] = adapter.headless
        seen["arg_headless"] = headless
        return SiteReport(
            site_key=adapter.site_key,
            site_name=adapter.site_name,
            listing_url=adapter.listing_url,
            diff=SiteDiff(site_key=adapter.site_key),
            screenshots=[],
        )

    monkeypatch.setattr(cli, "ALL_ADAPTERS", [_FakeAdapter])
    monkeypatch.setattr(cli, "_process_site", fake_process_site)
    monkeypatch.setattr(
        cli,
        "write_reports",
        lambda report, out_dir: (
            tmp_path / "weekly_report.md",
            tmp_path / "weekly_report.html",
            None,
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["run", "--sites", "fake", "--no-screenshots", "--no-details", *extra_args],
    )

    assert result.exit_code == 0, result.output
    assert seen["adapter_headless"] is expected_headless
    assert seen["arg_headless"] is expected_headless


def test_send_email_shows_gmail_app_password_guidance(monkeypatch, capsys, tmp_path: Path) -> None:
    from weekly_monitor import cli
    from weekly_monitor.core import email_sender

    report = WeeklyReport(run_date="2026-02-09", sites=[])

    monkeypatch.setattr(
        cli,
        "render_html_for_email",
        lambda report, out_dir, **kwargs: ("<html></html>", {}),
    )

    def raise_auth(*args, **kwargs):
        raise email_sender.SmtpAuthError("535-5.7.8 Username and Password not accepted")

    monkeypatch.setattr(email_sender, "send_report", raise_auth)

    cli._send_email(
        report=report,
        out_dir=tmp_path,
        recipients=["team@example.com"],
        run_date="2026-02-09",
        logger=logging.getLogger("test"),
    )

    captured = capsys.readouterr()
    assert "App Password" in captured.err
    assert "535" in captured.err


def test_send_email_includes_pdf_attachment_only(monkeypatch, tmp_path: Path) -> None:
    from weekly_monitor import cli
    from weekly_monitor.core import email_sender

    report = WeeklyReport(run_date="2026-02-09", sites=[])

    pdf_path = tmp_path / "weekly_report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    shot1 = tmp_path / "screenshots" / "nt" / "listing.png"
    shot1.parent.mkdir(parents=True, exist_ok=True)
    shot1.write_bytes(b"fakepng1")

    shot2 = tmp_path / "screenshots" / "nt" / "new_0.png"
    shot2.write_bytes(b"fakepng2")

    cid_map = {
        "img0@weekly-monitor": shot1,
        "img1@weekly-monitor": shot2,
    }
    monkeypatch.setattr(
        cli,
        "render_html_for_email",
        lambda report, out_dir, **kwargs: ("<html></html>", cid_map),
    )

    captured: dict[str, object] = {}

    def fake_send_report(*args, **kwargs):
        captured["attachments"] = kwargs.get("attachments")
        captured["cid_map"] = args[2]

    monkeypatch.setattr(email_sender, "send_report", fake_send_report)

    cli._send_email(
        report=report,
        out_dir=tmp_path,
        recipients=["team@example.com"],
        run_date="2026-02-09",
        logger=logging.getLogger("test"),
    )

    attachments = captured["attachments"]
    assert isinstance(attachments, list)
    assert pdf_path in attachments
    assert shot1 not in attachments
    assert shot2 not in attachments

    cid_map_sent = captured["cid_map"]
    assert len(cid_map_sent) <= cli.EMAIL_MAX_INLINE_IMAGES
