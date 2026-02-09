"""Send the weekly report via email with inline screenshot images."""

from __future__ import annotations

import logging
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

logger = logging.getLogger(__name__)


class SmtpAuthError(RuntimeError):
    """Raised when SMTP login fails (e.g. Gmail 535 bad credentials)."""


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
    *,
    smtp_user: str = "",
    smtp_password: str = "",
    smtp_host: str = "",
    smtp_port: int = 0,
    smtp_from: str = "",
) -> None:
    """Send an HTML email with CID-embedded inline images.

    SMTP credentials can be passed directly (from interactive prompts)
    or read from environment variables as a fallback.

    Parameters
    ----------
    subject:
        Email subject line.
    html_body:
        HTML string with ``cid:`` references in ``<img>`` tags.
    cid_map:
        Mapping of Content-ID to the absolute Path of the image on disk.
    recipients:
        List of email addresses to send to.
    smtp_user, smtp_password, smtp_host, smtp_port, smtp_from:
        Optional explicit SMTP credentials.  If not provided, falls back
        to environment variables (SMTP_USER, SMTP_PASSWORD, etc.).
    """
    env_cfg = _smtp_config()

    host = smtp_host or env_cfg["host"]
    port = smtp_port or env_cfg["port"]
    user = smtp_user or env_cfg["user"]
    password = smtp_password or env_cfg["password"]
    from_addr = smtp_from or user or env_cfg["from_addr"]

    if not user or not password:
        raise RuntimeError(
            "SMTP credentials not provided.  Either pass them interactively "
            "or set SMTP_USER and SMTP_PASSWORD environment variables."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
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
    logger.info("Sending email to %s via %s:%s", recipients, host, port)
    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise SmtpAuthError(str(exc)) from exc

    logger.info("Email sent successfully to %d recipient(s)", len(recipients))
