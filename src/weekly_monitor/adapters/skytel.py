"""Adapter for Skytel (Mongolia) – skytel.mn.

Skytel's site is JS-rendered, so we use Playwright for both listing and
detail extraction.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.core.models import SnapshotItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.skytel.mn"
LISTING_URL = "https://www.skytel.mn/skytel"
NEWS_ARCHIVE_URL = "https://www.skytel.mn/news/archiveNew"


class SkytelAdapter(SiteAdapter):
    site_key = "skytel"
    site_name = "Skytel (Mongolia)"
    listing_url = LISTING_URL
    api_url = ""

    def fetch_listing(self) -> str:
        """Use Playwright to render the Skytel page and return HTML."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._fetch_listing_async())
        finally:
            loop.close()

    async def _fetch_listing_async(self) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=getattr(self, "headless", False))
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            # Try archive page first; fall back to main site
            for url in [NEWS_ARCHIVE_URL, LISTING_URL]:
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30_000)
                    await page.wait_for_timeout(2000)
                    html = await page.content()
                    if html and len(html) > 500:
                        await browser.close()
                        return html
                except Exception:
                    logger.warning("Skytel: %s failed, trying next URL", url)

            html = await page.content()
            await browser.close()
            return html or ""

    def parse_listing(self, raw: str) -> list[SnapshotItem]:
        """Parse news/promo items from JS-rendered HTML."""
        soup = BeautifulSoup(raw, "lxml")
        items: list[SnapshotItem] = []
        seen: set[str] = set()

        # Broad selectors suitable for Skytel
        link_tags = (
            soup.select("a[href*='/news/']")
            + soup.select("a[href*='/skytel/']")
            + soup.select("[class*=news] a[href]")
            + soup.select("[class*=promo] a[href]")
            + soup.select(".card a[href]")
            + soup.select("article a[href]")
            + soup.select("[class*=post] a[href]")
            + soup.select("[class*=article] a[href]")
        )

        for a_tag in link_tags:
            href = a_tag.get("href", "")
            if not href or href == "#":
                continue
            url = _abs(href)
            if url in seen:
                continue
            # Skip if it's just the listing URL itself
            if url.rstrip("/") in (LISTING_URL.rstrip("/"), NEWS_ARCHIVE_URL.rstrip("/")):
                continue
            seen.add(url)

            title = _extract_title(a_tag)
            date_str = _extract_date_near(a_tag)
            summary = _extract_summary(a_tag)

            item = SnapshotItem(
                url=url,
                title=title,
                date=date_str,
                summary=summary,
            )
            item.compute_hash()
            items.append(item)

        # Fallback: If no results, try all internal links
        if not items:
            logger.warning("Skytel: primary selectors yielded 0 items, broad scan")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                url = _abs(href)
                if url in seen or not url.startswith(BASE_URL):
                    continue
                if url.rstrip("/") in (LISTING_URL.rstrip("/"), NEWS_ARCHIVE_URL.rstrip("/")):
                    continue
                seen.add(url)
                title = a_tag.get_text(strip=True)[:200] or url
                if not title or len(title) < 3:
                    continue
                item = SnapshotItem(url=url, title=title)
                item.compute_hash()
                items.append(item)

        logger.info("Skytel: parsed %d items from listing", len(items))
        return items

    def fetch_detail(self, item: SnapshotItem) -> str | None:
        """Fetch detail page via Playwright (JS-rendered)."""
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._fetch_detail_async(item.url))
            loop.close()
            return result
        except Exception:
            logger.exception("Skytel: failed to fetch detail %s", item.url)
            return None

    async def _fetch_detail_async(self, url: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=getattr(self, "headless", False))
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            await page.wait_for_timeout(1500)
            html = await page.content()
            await browser.close()
            return html

    def parse_detail(self, item: SnapshotItem, raw: Any) -> SnapshotItem:
        if not raw:
            return item
        soup = BeautifulSoup(raw, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        body = (
            soup.select_one("article")
            or soup.select_one(".content")
            or soup.select_one("[class*=detail]")
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
        """Skytel: also include archive page as a screenshot."""
        targets = [
            {
                "url": NEWS_ARCHIVE_URL,
                "filename": "archive.png",
                "label": "Skytel – news archive page",
            },
            {
                "url": LISTING_URL,
                "filename": "listing.png",
                "label": "Skytel – main page",
            },
        ]
        for idx, item in enumerate(new_items[:8]):
            targets.append(
                {
                    "url": item.url,
                    "filename": f"new_{idx}.png",
                    "label": item.title or item.url,
                }
            )
        return targets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abs(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def _extract_title(tag) -> str:
    heading = tag.find(re.compile(r"^h[1-6]$"))
    if heading:
        return heading.get_text(strip=True)
    return tag.get_text(strip=True)[:200]


def _extract_date_near(tag) -> str:
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
    parent = tag.parent
    if parent:
        p_tag = parent.find("p")
        if p_tag:
            return p_tag.get_text(strip=True)[:500]
    return ""
