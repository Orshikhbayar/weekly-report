"""Adapter for NT (National Telecom Thailand) – ntplc.co.th/en/news."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.core.http import build_client, fetch_url
from weekly_monitor.core.models import SnapshotItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ntplc.co.th"
LISTING_URL = "https://www.ntplc.co.th/en/news"


class NTAdapter(SiteAdapter):
    site_key = "nt"
    site_name = "NT (National Telecom Thailand)"
    listing_url = LISTING_URL
    api_url = ""
    prefer_language = "en"

    def _english_client(self):
        """Return an HTTP client that requests English content."""
        return build_client(accept_language="en")

    def fetch_listing(self) -> str:
        """Fetch the news listing page HTML."""
        client = self._english_client()
        try:
            resp = fetch_url(LISTING_URL, client=client)
            return resp.text
        finally:
            client.close()

    def parse_listing(self, raw: str) -> list[SnapshotItem]:
        """Parse news cards from NT listing page.

        NT typically renders server-side. We look for common card/article
        patterns. The selectors below are best-effort and will be refined
        after the first live run.
        """
        soup = BeautifulSoup(raw, "lxml")
        items: list[SnapshotItem] = []

        # Strategy 1: Look for article/card blocks with links
        # NT news page often uses .card, .news-item, article elements, or
        # rows with <a> tags containing news titles.
        candidates = (
            soup.select("article a[href]")
            + soup.select(".card a[href]")
            + soup.select(".news-item a[href]")
            + soup.select(".news-list a[href]")
            + soup.select("[class*=news] a[href]")
            + soup.select("[class*=article] a[href]")
        )

        seen_urls: set[str] = set()
        for tag in candidates:
            href = tag.get("href", "")
            if not href or href == "#":
                continue
            url = _abs(href)
            if url in seen_urls:
                continue
            # Only keep links that look like news detail pages
            if "/news/" not in url and "/en/news" not in url:
                continue
            if url.rstrip("/") == LISTING_URL.rstrip("/"):
                continue
            seen_urls.add(url)

            title = _extract_title(tag)
            date_str = _extract_date_near(tag)
            summary = _extract_summary(tag)

            item = SnapshotItem(
                url=url,
                title=title,
                date=date_str,
                summary=summary,
            )
            item.compute_hash()
            items.append(item)

        # Strategy 2: Fallback – scan all <a> tags if nothing found
        if not items:
            logger.warning("NT: primary selectors yielded 0 items, falling back to broad scan")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                url = _abs(href)
                if url in seen_urls:
                    continue
                if "/news/" not in url and "/en/news" not in url:
                    continue
                if url.rstrip("/") == LISTING_URL.rstrip("/"):
                    continue
                seen_urls.add(url)
                title = a_tag.get_text(strip=True) or url
                item = SnapshotItem(url=url, title=title)
                item.compute_hash()
                items.append(item)

        logger.info("NT: parsed %d items from listing", len(items))
        return items

    def fetch_detail(self, item: SnapshotItem) -> str | None:
        """Fetch a single news detail page (requesting English)."""
        client = self._english_client()
        try:
            # Ensure the URL uses the /en/ path when available
            url = _ensure_english_path(item.url)
            resp = fetch_url(url, client=client)
            return resp.text
        except Exception:
            logger.exception("NT: failed to fetch detail %s", item.url)
            return None
        finally:
            client.close()

    def parse_detail(self, item: SnapshotItem, raw: Any) -> SnapshotItem:
        """Extract cleaned body text from a detail page."""
        if not raw:
            return item
        soup = BeautifulSoup(raw, "lxml")
        # Remove scripts/styles
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        body = soup.select_one("article") or soup.select_one(".content") or soup.select_one("main") or soup.body
        if body:
            text = body.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            item.raw_excerpt = text[:2000]

        item.compute_hash()
        return item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abs(href: str) -> str:
    """Make an href absolute."""
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def _extract_title(tag) -> str:
    """Pull text from heading inside or near the tag."""
    heading = tag.find(re.compile(r"^h[1-6]$"))
    if heading:
        return heading.get_text(strip=True)
    # Just use the link text
    return tag.get_text(strip=True)[:200]


def _extract_date_near(tag) -> str:
    """Try to find a date string near the tag."""
    parent = tag.parent
    if parent:
        date_el = parent.find(class_=re.compile(r"date|time|publish", re.I))
        if date_el:
            return date_el.get_text(strip=True)
        time_el = parent.find("time")
        if time_el:
            return time_el.get("datetime", time_el.get_text(strip=True))
    return ""


def _extract_summary(tag) -> str:
    """Extract summary/description from siblings or children."""
    parent = tag.parent
    if parent:
        p_tag = parent.find("p")
        if p_tag:
            return p_tag.get_text(strip=True)[:500]
    return ""


def _ensure_english_path(url: str) -> str:
    """Rewrite an NT URL to the ``/en/`` path if it isn't already."""
    if "/en/" in url:
        return url
    # E.g. https://www.ntplc.co.th/news/123 -> https://www.ntplc.co.th/en/news/123
    if url.startswith(BASE_URL):
        path = url[len(BASE_URL):]
        if path.startswith("/"):
            return BASE_URL + "/en" + path
    return url
