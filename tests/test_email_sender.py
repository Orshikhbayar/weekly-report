"""Email sender tests."""

from __future__ import annotations

from pathlib import Path


def test_send_report_attaches_pdf_and_files(monkeypatch, tmp_path: Path) -> None:
    from weekly_monitor.core import email_sender

    screenshot_path = tmp_path / "shot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    pdf_path = tmp_path / "weekly_report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    sent: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, user, password):
            sent["user"] = user
            sent["password"] = password

        def send_message(self, msg):
            sent["msg"] = msg

    monkeypatch.setattr(email_sender.smtplib, "SMTP", FakeSMTP)

    email_sender.send_report(
        subject="Weekly report",
        html_body="<html><body><img src='cid:img0@weekly-monitor'></body></html>",
        cid_map={"img0@weekly-monitor": screenshot_path},
        recipients=["team@example.com"],
        attachments=[pdf_path, screenshot_path],
        smtp_user="user@example.com",
        smtp_password="app-password",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
    )

    msg = sent["msg"]
    attachment_names = {part.get_filename() for part in msg.iter_attachments()}

    assert "weekly_report.pdf" in attachment_names
    assert "shot.png" in attachment_names
