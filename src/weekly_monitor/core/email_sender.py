"""Send the weekly report via email with inline screenshot images."""

from __future__ import annotations

import logging
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

logger = logging.getLogger(__name__)


def _smtp_config() -> dict:
    """Read SMTP configuration from environment variables."""
    user = os.environ.get("SMTP_USER", "")
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": user,
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM", user),
    }


def send_report(
    subject: str,
    html_body: str,
    cid_map: dict[str, Path],
    recipients: list[str],
) -> None:
    """Send an HTML email with CID-embedded inline images.

    Parameters
    ----------
    subject:
        Email subject line.
    html_body:
        HTML string with ``cid:`` references in ``<img>`` tags.
    cid_map:
        Mapping of Content-ID (e.g. ``img0@weekly-monitor``) to the
        absolute ``Path`` of the image file on disk.
    recipients:
        List of email addresses to send to.
    """
    cfg = _smtp_config()
    if not cfg["user"] or not cfg["password"]:
        raise RuntimeError(
            "SMTP_USER and SMTP_PASSWORD environment variables must be set "
            "to send email.  See README for details."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = ", ".join(recipients)

    # Set HTML as the email body
    msg.set_content("Your email client does not support HTML. Please view the attached report.")
    msg.add_alternative(html_body, subtype="html")

    # Attach inline images referenced by cid: in the HTML
    html_part = msg.get_payload()[-1]  # the multipart/alternative -> html part
    for cid, img_path in cid_map.items():
        if not img_path.exists():
            logger.warning("Image not found, skipping CID %s: %s", cid, img_path)
            continue
        mime_type, _ = mimetypes.guess_type(str(img_path))
        if mime_type is None:
            mime_type = "application/octet-stream"
        maintype, subtype = mime_type.split("/", 1)
        img_data = img_path.read_bytes()
        html_part.add_related(
            img_data,
            maintype=maintype,
            subtype=subtype,
            cid=f"<{cid}>",
            filename=img_path.name,
        )

    # Send
    logger.info("Sending email to %s via %s:%s", recipients, cfg["host"], cfg["port"])
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(cfg["user"], cfg["password"])
        smtp.send_message(msg)

    logger.info("Email sent successfully to %d recipient(s)", len(recipients))
