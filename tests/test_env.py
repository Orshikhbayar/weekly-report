"""Tests for runtime .env loading."""

from __future__ import annotations

import os
from pathlib import Path

from weekly_monitor.core.env import _parse_env_line, load_runtime_env


def test_parse_env_line_supports_export_quotes_and_comments() -> None:
    assert _parse_env_line("export OPENAI_API_KEY='sk-test'") == ("OPENAI_API_KEY", "sk-test")
    assert _parse_env_line('SMTP_HOST="smtp.gmail.com"') == ("SMTP_HOST", "smtp.gmail.com")
    assert _parse_env_line("SMTP_PORT=587 # default tls port") == ("SMTP_PORT", "587")
    assert _parse_env_line("# comment") is None
    assert _parse_env_line("NOT_A_VALID_LINE") is None


def test_load_runtime_env_reads_file(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=sk-123\n"
        "SMTP_HOST=smtp.gmail.com\n"
        "SMTP_PORT=587\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)

    loaded = load_runtime_env([env_path])

    assert loaded == [env_path]
    assert os.environ["OPENAI_API_KEY"] == "sk-123"
    assert os.environ["SMTP_HOST"] == "smtp.gmail.com"
    assert os.environ["SMTP_PORT"] == "587"


def test_load_runtime_env_does_not_override_existing(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("SMTP_HOST=smtp.gmail.com\n", encoding="utf-8")

    monkeypatch.setenv("SMTP_HOST", "smtp.office365.com")
    load_runtime_env([env_path])

    assert os.environ["SMTP_HOST"] == "smtp.office365.com"
