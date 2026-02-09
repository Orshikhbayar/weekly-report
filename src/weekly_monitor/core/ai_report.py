"""AI-generated Mongolian summary for the weekly report using OpenAI."""

from __future__ import annotations

import logging
import os

from weekly_monitor.core.models import WeeklyReport

logger = logging.getLogger(__name__)


def generate_mongolian_summary(report: WeeklyReport) -> str:
    """Generate a Mongolian-language summary of new and updated items.

    Uses the OpenAI API (``OPENAI_API_KEY`` env var).  Returns an empty
    string when the key is missing or the API call fails so the report
    can still be generated without the AI section.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.info("OPENAI_API_KEY not set – skipping AI summary")
        return ""

    # Build a structured prompt from the report data
    prompt_lines = _build_prompt(report)
    if not prompt_lines:
        return ""

    try:
        return _call_openai(api_key, prompt_lines)
    except Exception:
        logger.exception("AI summary generation failed – skipping")
        return ""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(report: WeeklyReport) -> str:
    """Create a text block listing new/updated items per site."""
    lines: list[str] = []
    lines.append(f"Report date: {report.run_date}")
    lines.append("")

    has_content = False
    for site in report.sites:
        site_lines: list[str] = []
        site_lines.append(f"Site: {site.site_name}")

        if site.diff.new_items:
            has_content = True
            site_lines.append("  New items:")
            for item in site.diff.new_items:
                date_part = f" ({item.date})" if item.date else ""
                site_lines.append(f"    - {item.title}{date_part}")
                site_lines.append(f"      URL: {item.url}")
                if item.summary:
                    site_lines.append(f"      Summary: {item.summary[:300]}")

        if site.diff.updated_items:
            has_content = True
            site_lines.append("  Updated items:")
            for item in site.diff.updated_items:
                changed = ", ".join(item.changed_fields) if item.changed_fields else "content"
                site_lines.append(f"    - {item.title} — changed: {changed}")
                site_lines.append(f"      URL: {item.url}")
                if item.summary:
                    site_lines.append(f"      Summary: {item.summary[:300]}")

        if not site.diff.new_items and not site.diff.updated_items:
            site_lines.append("  No changes detected.")

        lines.extend(site_lines)
        lines.append("")

    if not has_content:
        return ""  # Nothing interesting to summarise

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a report assistant. Given the following list of new and updated "
    "web pages, write a short summary in Mongolian (Cyrillic script). "
    "Explain what is new, what is updated, and why an item is considered "
    "new (first time we see this URL) or updated (same URL but content "
    "changed — e.g. title, summary, or article body). "
    "Keep the tone professional and concise. "
    "Use bullet points for clarity. Do not include any English text in the summary."
)


def _call_openai(api_key: str, user_content: str) -> str:
    """Call the OpenAI chat completions API and return the generated text."""
    import openai

    client = openai.OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
        max_tokens=1024,
    )

    text = response.choices[0].message.content or ""
    return text.strip()
