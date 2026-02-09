"""Playwright-based screenshot capture."""

from __future__ import annotations

import logging
from pathlib import Path

from weekly_monitor.core.models import ScreenshotRef

logger = logging.getLogger(__name__)

MAX_SCREENSHOTS_PER_SITE = 10


async def capture_screenshots(
    targets: list[dict],  # [{url, filename, label}]
    output_dir: Path,
    *,
    timeout_ms: int = 30_000,
    viewport: dict | None = None,
) -> list[ScreenshotRef]:
    """Take screenshots for a list of target URLs.

    Each target dict must have at least ``url`` and ``filename`` keys.
    Optional ``label`` for the report.  Returns list of ScreenshotRef.
    """
    from playwright.async_api import async_playwright

    if not targets:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    vp = viewport or {"width": 1280, "height": 900}
    refs: list[ScreenshotRef] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=vp,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        for idx, target in enumerate(targets[:MAX_SCREENSHOTS_PER_SITE]):
            url = target["url"]
            fname = target.get("filename", f"shot_{idx}.png")
            label = target.get("label", url)
            dest = output_dir / fname

            try:
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                await page.wait_for_timeout(1500)  # settle animations
                await page.screenshot(path=str(dest), full_page=True)
                await page.close()

                refs.append(ScreenshotRef(page_url=url, file_path=str(dest), label=label))
                logger.info("Screenshot saved: %s -> %s", url, dest)
            except Exception:
                logger.exception("Screenshot failed for %s", url)

        await browser.close()

    return refs
