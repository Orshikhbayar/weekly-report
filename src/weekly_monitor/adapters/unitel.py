"""Adapter for Unitel (Mongolia) – unitel.mn.

Unitel exposes a JSON API at /api.php/main/get_news/promo which we try first.
Falls back to HTML scraping if the API is unavailable.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.core.http import build_client, fetch_json, fetch_url
from weekly_monitor.core.models import SnapshotItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.unitel.mn"
LISTING_URL = "https://www.unitel.mn/unitel/"
API_URL = "https://www.unitel.mn/api.php/main/get_news/promo"


class UnitelAdapter(SiteAdapter):
    site_key = "unitel"
    site_name = "Unitel (Mongolia)"
    listing_url = LISTING_URL
    api_url = API_URL

    def fetch_listing(self) -> Any:
        """Try API first, fall back to HTML."""
        try:
            data = fetch_json(API_URL)
            logger.info("Unitel: API returned data (type=%s)", type(data).__name__)
            return {"source": "api", "data": data}
        except Exception:
            logger.warning("Unitel: API unavailable, falling back to HTML scraping")
            resp = fetch_url(LISTING_URL)
            return {"source": "html", "data": resp.text}

    def parse_listing(self, raw: Any) -> list[SnapshotItem]:
        """Parse items from API JSON or HTML fallback."""
        source = raw.get("source", "html")
        data = raw["data"]

        if source == "api":
            return self._parse_api(data)
        return self._parse_html(data)

    def _parse_api(self, data: Any) -> list[SnapshotItem]:
        """Parse JSON response from the promo API."""
        items: list[SnapshotItem] = []

        # The API may return a dict with a data/items key or a bare list
        records: list[dict] = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            for key in ("data", "items", "result", "news", "list"):
                if key in data and isinstance(data[key], list):
                    records = data[key]
                    break
            if not records:
                # Maybe top-level dict is a single item? Unlikely but safe.
                records = [data]

        seen: set[str] = set()
        for rec in records:
            url = self._item_url(rec)
            if not url or url in seen:
                continue
            seen.add(url)

            title = (
                rec.get("title")
                or rec.get("name")
                or rec.get("heading")
                or ""
            )
            date_str = (
                rec.get("date")
                or rec.get("created_at")
                or rec.get("published_at")
                or rec.get("publish_date")
                or ""
            )
            summary = (
                rec.get("summary")
                or rec.get("description")
                or rec.get("short_description")
                or rec.get("excerpt")
                or ""
            )
            # Strip any HTML from summary
            if "<" in summary:
                summary = BeautifulSoup(summary, "lxml").get_text(separator=" ", strip=True)

            raw_excerpt = (
                rec.get("content")
                or rec.get("body")
                or rec.get("text")
                or ""
            )
            if "<" in raw_excerpt:
                raw_excerpt = BeautifulSoup(raw_excerpt, "lxml").get_text(separator=" ", strip=True)
            raw_excerpt = raw_excerpt[:2000]

            item = SnapshotItem(
                url=url,
                title=str(title),
                date=str(date_str),
                summary=str(summary)[:500],
                raw_excerpt=raw_excerpt,
            )
            item.compute_hash()
            items.append(item)

        logger.info("Unitel API: parsed %d items", len(items))
        return items

    def _parse_html(self, html: str) -> list[SnapshotItem]:
        """Fallback HTML parser for the Unitel site."""
        soup = BeautifulSoup(html, "lxml")
        items: list[SnapshotItem] = []
        seen: set[str] = set()

        # Generic card/news selectors
        link_tags = (
            soup.select("a[href*='/news/']")
            + soup.select("a[href*='/promo/']")
            + soup.select("[class*=news] a[href]")
            + soup.select("[class*=promo] a[href]")
            + soup.select(".card a[href]")
            + soup.select("article a[href]")
        )

        for a_tag in link_tags:
            href = a_tag.get("href", "")
            if not href or href == "#":
                continue
            url = _abs(href)
            if url in seen:
                continue
            seen.add(url)

            title = a_tag.get_text(strip=True)[:200] or url
            item = SnapshotItem(url=url, title=title)
            item.compute_hash()
            items.append(item)

        logger.info("Unitel HTML: parsed %d items", len(items))
        return items

    def _item_url(self, rec: dict) -> str:
        """Build absolute URL from an API record."""
        for key in ("url", "link", "href", "slug", "id"):
            val = rec.get(key)
            if val is not None:
                val = str(val)
                if val.startswith("http"):
                    return val
                if val.startswith("/"):
                    return urljoin(BASE_URL, val)
                # Might be a slug or id
                if key in ("slug", "id"):
                    return f"{BASE_URL}/unitel/news/{val}"
                return urljoin(BASE_URL, val)
        return ""

    def fetch_detail(self, item: SnapshotItem) -> str | None:
        try:
            resp = fetch_url(item.url)
            return resp.text
        except Exception:
            logger.exception("Unitel: failed to fetch detail %s", item.url)
            return None

    def parse_detail(self, item: SnapshotItem, raw: Any) -> SnapshotItem:
        if not raw:
            return item
        soup = BeautifulSoup(raw, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        body = soup.select_one("article") or soup.select_one(".content") or soup.select_one("main") or soup.body
        if body:
            text = body.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            item.raw_excerpt = text[:2000]
        item.compute_hash()
        return item


def _abs(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)
