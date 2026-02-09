"""Tests for AI summary payload shaping and cleanup."""

from __future__ import annotations

import json
import types

from weekly_monitor.core.ai_report import (
    MAX_ITEMS_PER_SITE,
    _build_prompt_payload,
    _call_openai,
    _clean_summary_text,
)
from weekly_monitor.core.models import DiffItem, SiteDiff, SiteReport, WeeklyReport


def test_build_prompt_payload_returns_empty_when_no_changes() -> None:
    report = WeeklyReport(
        run_date="2026-02-09",
        sites=[
            SiteReport(
                site_key="nt",
                site_name="NT",
                listing_url="https://example.com/news",
                diff=SiteDiff(site_key="nt"),
                screenshots=[],
            )
        ],
    )
    assert _build_prompt_payload(report) == ""


def test_build_prompt_payload_limits_items_per_site() -> None:
    new_items = [
        DiffItem(url=f"https://example.com/new-{i}", title=f"New {i}", summary="summary")
        for i in range(MAX_ITEMS_PER_SITE + 2)
    ]
    updated_items = [
        DiffItem(
            url=f"https://example.com/upd-{i}",
            title=f"Upd {i}",
            summary="summary",
            changed_fields=["title"],
        )
        for i in range(MAX_ITEMS_PER_SITE + 3)
    ]

    report = WeeklyReport(
        run_date="2026-02-09",
        sites=[
            SiteReport(
                site_key="nt",
                site_name="NT",
                listing_url="https://example.com/news",
                diff=SiteDiff(site_key="nt", new_items=new_items, updated_items=updated_items),
                screenshots=[],
            )
        ],
    )

    payload = _build_prompt_payload(report)
    parsed = json.loads(payload)

    site = parsed["sites"][0]
    assert site["counts"]["new"] == MAX_ITEMS_PER_SITE + 2
    assert site["counts"]["updated"] == MAX_ITEMS_PER_SITE + 3
    assert len(site["new_highlights"]) == MAX_ITEMS_PER_SITE
    assert len(site["updated_highlights"]) == MAX_ITEMS_PER_SITE


def test_clean_summary_text_normalizes_whitespace() -> None:
    raw = "\n\n  Товч дүгнэлт:\n-   нэг мөр  \n\n- хоёр мөр\t\t\n\n"
    cleaned = _clean_summary_text(raw)
    assert cleaned == "Товч дүгнэлт:\n- нэг мөр\n\n- хоёр мөр"


def test_call_openai_uses_max_completion_tokens_for_gpt5(monkeypatch) -> None:
    captured: dict = {}

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            msg = types.SimpleNamespace(content="Тест хураангуй")
            choice = types.SimpleNamespace(message=msg)
            return types.SimpleNamespace(choices=[choice])

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, api_key: str):
            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(OpenAI=_Client)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.2")

    text = _call_openai("sk-test", '{"sites":[]}')
    assert text == "Тест хураангуй"
    assert "max_completion_tokens" in captured
    assert "max_tokens" not in captured
