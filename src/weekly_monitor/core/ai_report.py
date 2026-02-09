"""AI-generated Mongolian summary for the weekly report using OpenAI."""

from __future__ import annotations

import json
import logging
import os
import re

from weekly_monitor.core.models import WeeklyReport

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_SITE = 5
MAX_FIELD_CHARS = 220


def generate_mongolian_summary(report: WeeklyReport) -> str:
    """Generate a Mongolian-language summary of new and updated items.

    Uses the OpenAI API (``OPENAI_API_KEY`` env var).  Returns an empty
    string when the key is missing or the API call fails so the report
    can still be generated without the AI section.
    """
    # Build a structured prompt from the report data
    prompt_payload = _build_prompt_payload(report)
    if not prompt_payload:
        return ""

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.info("OPENAI_API_KEY not set – skipping AI summary")
        return ""

    try:
        text = _call_openai(api_key, prompt_payload)
        return _clean_summary_text(text)
    except Exception:
        logger.exception("AI summary generation failed – skipping")
        return ""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt_payload(report: WeeklyReport) -> str:
    """Create a compact JSON payload of meaningful changes for the model."""
    sites: list[dict] = []
    for site in report.sites:
        new_items = site.diff.new_items[:MAX_ITEMS_PER_SITE]
        updated_items = site.diff.updated_items[:MAX_ITEMS_PER_SITE]
        if not new_items and not updated_items:
            continue

        sites.append(
            {
                "site_name": site.site_name,
                "counts": {
                    "new": len(site.diff.new_items),
                    "updated": len(site.diff.updated_items),
                },
                "new_highlights": [_item_payload(i) for i in new_items],
                "updated_highlights": [_updated_item_payload(i) for i in updated_items],
            }
        )

    if not sites:
        return ""

    payload = {
        "run_date": report.run_date,
        "totals": {
            "new": sum(s["counts"]["new"] for s in sites),
            "updated": sum(s["counts"]["updated"] for s in sites),
        },
        "sites": sites,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _item_payload(item) -> dict:
    return {
        "title": _short(item.title),
        "date": _short(item.date or ""),
        "summary": _short(item.summary),
    }


def _updated_item_payload(item) -> dict:
    changed = ", ".join(item.changed_fields) if item.changed_fields else "content"
    obj = _item_payload(item)
    obj["changed_fields"] = _short(changed)
    return obj


def _short(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_FIELD_CHARS]


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "Та долоо хоногийн вэб өөрчлөлтийн тайлан бичдэг туслах. "
    "Оролт нь JSON өгөгдөл байна. Зөвхөн Монгол хэл (кирилл) ашигла.\n\n"
    "Дараах яг энэ бүтэцтэй, цэвэр текст хариу өг:\n"
    "Товч дүгнэлт:\n"
    "- ...\n"
    "- ...\n\n"
    "Сайтаар:\n"
    "- <сайтын нэр>: шинэ <тоо>, шинэчлэгдсэн <тоо>\n"
    "  - Онцлох шинэ: ...\n"
    "  - Онцлох шинэчлэлт: ...\n\n"
    "Тайлбар:\n"
    "- Шинэ: анх удаа илэрсэн URL.\n"
    "- Шинэчлэгдсэн: өмнөхтэй ижил URL боловч агуулга өөрчлөгдсөн.\n\n"
    "Дүрэм:\n"
    "- Баримтад байхгүй мэдээлэл зохиохгүй.\n"
    "- 120-220 үгт багтаа.\n"
    "- URL, JSON талбарын нэрсийг хуулахгүй.\n"
    "- Мэргэжлийн, ойлгомжтой хэллэг хэрэглэ."
)


def _call_openai(api_key: str, user_content: str) -> str:
    """Call the OpenAI chat completions API and return the generated text."""
    import openai

    client = openai.OpenAI(api_key=api_key)
    model = os.environ.get("OPENAI_MODEL", "gpt-5.2")

    req: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }
    # GPT-5 family expects max_completion_tokens; legacy models use max_tokens.
    if model.startswith("gpt-5"):
        req["max_completion_tokens"] = 900
    else:
        req["max_tokens"] = 900

    response = client.chat.completions.create(**req)

    text = response.choices[0].message.content or ""
    return text.strip()


def _clean_summary_text(text: str) -> str:
    """Normalize whitespace and remove leading/trailing blank lines."""
    lines: list[str] = []
    for ln in text.splitlines():
        leading = len(ln) - len(ln.lstrip(" \t"))
        body = re.sub(r"[ \t]+", " ", ln.lstrip(" \t")).rstrip()
        if not body:
            lines.append("")
            continue
        if body.startswith("- "):
            lines.append(("  " if leading >= 2 else "") + body)
        else:
            lines.append(body)

    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)
