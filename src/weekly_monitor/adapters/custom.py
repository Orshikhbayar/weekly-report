"""Generic adapter for any user-provided URL.

Uses Playwright to render the page (works with JS-heavy sites) and
extracts links + text content for change tracking.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.core.models import SnapshotItem

logger = logging.getLogger(__name__)


class CustomAdapter(SiteAdapter):
    """Adapter that scrapes any URL provided at runtime."""

    site_key: str = "custom"
    site_name: str = "Custom URL"
    listing_url: str = ""
    api_url: str = ""

    def __init__(self, url: str, name: str = "") -> None:
        self.listing_url = url
        parsed = urlparse(url)
        self._base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.site_key = re.sub(r"[^a-z0-9]", "_", parsed.netloc.lower())
        self.site_name = name or parsed.netloc

    def fetch_listing(self) -> str:
        """Render the page with Playwright and return HTML."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._fetch_async(self.listing_url))
        finally:
            loop.close()

    async def _fetch_async(self, url: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception:
                logger.warning("Custom: page load failed for %s", url)
                html = ""
            await browser.close()
            return html or ""

    def parse_listing(self, raw: str) -> list[SnapshotItem]:
        """Extract links and text from the rendered page."""
        if not raw:
            return []

        soup = BeautifulSoup(raw, "lxml")
        items: list[SnapshotItem] = []
        seen: set[str] = set()

        # Remove scripts/styles
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        # Find all internal links with meaningful text
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            url = self._abs(href)
            if url in seen:
                continue

            # Keep links from the same domain
            if not url.startswith(self._base_url):
                continue

            # Skip the listing URL itself
            if url.rstrip("/") == self.listing_url.rstrip("/"):
                continue

            seen.add(url)
            title = a_tag.get_text(strip=True)[:200]
            if not title or len(title) < 3:
                continue

            # Try to find summary text near the link
            summary = self._extract_summary(a_tag)

            item = SnapshotItem(url=url, title=title, summary=summary)
            item.compute_hash()
            items.append(item)

        logger.info("Custom (%s): parsed %d items", self.site_name, len(items))
        return items

    def fetch_detail(self, item: SnapshotItem) -> str | None:
        """Fetch detail page via Playwright."""
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._fetch_async(item.url))
            loop.close()
            return result
        except Exception:
            logger.exception("Custom: failed to fetch detail %s", item.url)
            return None

    def parse_detail(self, item: SnapshotItem, raw: Any) -> SnapshotItem:
        if not raw:
            return item
        soup = BeautifulSoup(raw, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        body = (
            soup.select_one("article")
            or soup.select_one(".content")
            or soup.select_one("main")
            or soup.body
        )
        if body:
            text = body.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            item.raw_excerpt = text[:2000]
        item.compute_hash()
        return item

    def screenshot_targets(self, new_items: list[SnapshotItem]) -> list[dict]:
        targets = [
            {
                "url": self.listing_url,
                "filename": "listing.png",
                "label": f"{self.site_name} — main page",
            }
        ]
        for idx, item in enumerate(new_items[:8]):
            targets.append({
                "url": item.url,
                "filename": f"new_{idx}.png",
                "label": item.title or item.url,
            })
        return targets

    def _abs(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return urljoin(self._base_url, href)

    def _extract_summary(self, a_tag) -> str:
        parent = a_tag.parent
        if parent:
            p_tag = parent.find("p")
            if p_tag:
                return p_tag.get_text(strip=True)[:500]
        return ""
