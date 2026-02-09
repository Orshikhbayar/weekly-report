"""Pydantic data models used across the system."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SnapshotItem(BaseModel):
    """A single item discovered on a target site."""

    url: str
    title: str
    date: Optional[str] = None
    summary: str = ""
    content_hash: str = ""
    raw_excerpt: str = ""

    def compute_hash(self) -> str:
        """SHA-256 over normalised title + summary + raw_excerpt."""
        blob = _normalise(self.title) + _normalise(self.summary) + _normalise(self.raw_excerpt)
        self.content_hash = hashlib.sha256(blob.encode()).hexdigest()
        return self.content_hash


class Snapshot(BaseModel):
    """One scrape-run for a single site."""

    site_key: str
    run_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    listing_url: str = ""
    api_url: str = ""
    items: list[SnapshotItem] = []


class DiffItem(BaseModel):
    """A new or updated item found during diff."""

    url: str
    title: str
    date: Optional[str] = None
    summary: str = ""
    changed_fields: list[str] = []


class SiteDiff(BaseModel):
    """Diff result for a single site."""

    site_key: str
    listing_url: str = ""
    api_url: str = ""
    new_items: list[DiffItem] = []
    updated_items: list[DiffItem] = []


class ScreenshotRef(BaseModel):
    """Reference to a saved screenshot file."""

    page_url: str
    file_path: str
    label: str = ""


class SiteReport(BaseModel):
    """Per-site section in the weekly report."""

    site_key: str
    site_name: str
    listing_url: str = ""
    api_url: str = ""
    diff: SiteDiff
    screenshots: list[ScreenshotRef] = []


class WeeklyReport(BaseModel):
    """Full weekly report across all sites."""

    run_date: str
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    sites: list[SiteReport] = []
    ai_summary_mn: str = ""  # AI-generated Mongolian summary (optional)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    """Strip tags, collapse whitespace, lowercase."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = _WS_RE.sub(" ", text).strip().lower()
    return text
