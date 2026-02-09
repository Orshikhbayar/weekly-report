"""Playwright-based screenshot capture."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from weekly_monitor.core.models import ScreenshotRef

logger = logging.getLogger(__name__)

MAX_SCREENSHOTS_PER_SITE = 10


# ---------------------------------------------------------------------------
# Chromium detection / auto-install
# ---------------------------------------------------------------------------

def chromium_installed() -> bool:
    """Return True if Playwright's Chromium browser binary is available."""
    # Check standard Playwright browser cache locations per platform.
    search_paths: list[Path] = []

    # Playwright stores browsers alongside its driver in some setups
    try:
        import playwright._impl._driver as _drv
        driver_dir = Path(_drv.compute_driver_executable()).parent
        search_paths.append(driver_dir / ".local-browsers")
    except Exception:
        pass

    # Standard per-platform cache directories
    if sys.platform == "win32":
        # Windows: %LOCALAPPDATA%\ms-playwright
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        search_paths.append(local / "ms-playwright")
    elif sys.platform == "darwin":
        search_paths.append(Path.home() / "Library" / "Caches" / "ms-playwright")
    else:
        search_paths.append(Path.home() / ".cache" / "ms-playwright")

    for browsers_path in search_paths:
        if browsers_path.exists():
            chromium_dirs = list(browsers_path.glob("chromium*"))
            if chromium_dirs:
                return True

    return False


def install_chromium(quiet: bool = False) -> bool:
    """Install Playwright Chromium browser. Returns True on success.

    When *quiet* is False (default), installation progress is streamed
    live to the terminal so the user can see download progress.
    """
    try:
        kwargs: dict = {"timeout": 300}
        if quiet:
            kwargs["capture_output"] = True
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            **kwargs,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.error("Failed to install Chromium: %s", exc)
        return False


def ensure_chromium_or_raise() -> None:
    """Raise RuntimeError if Chromium is not installed (for headless mode)."""
    if not chromium_installed():
        raise RuntimeError(
            "Playwright Chromium is not installed. "
            "Run: weekly-monitor install"
        )


async def capture_screenshots(
    targets: list[dict],  # [{url, filename, label}]
    output_dir: Path,
    *,
    timeout_ms: int = 30_000,
    viewport: dict | None = None,
    headless: bool = False,
) -> list[ScreenshotRef]:
    """Take screenshots for a list of target URLs.

    Each target dict must have at least ``url`` and ``filename`` keys.
    Optional ``label`` for the report.  Returns list of ScreenshotRef.

    When *headless* is False (default), the browser window is visible so
    the user can watch the crawling process in real time.
    """
    from playwright.async_api import async_playwright

    if not targets:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    vp = viewport or {"width": 1280, "height": 900}
    refs: list[ScreenshotRef] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
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
