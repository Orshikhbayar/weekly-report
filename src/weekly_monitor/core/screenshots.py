"""Playwright-based screenshot capture."""

from __future__ import annotations

import logging
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
    try:
        from playwright._impl._driver import compute_driver_executable
        driver_exec = compute_driver_executable()
        result = subprocess.run(
            [str(driver_exec), "install", "--dry-run", "chromium"],
            capture_output=True, text=True, timeout=10,
        )
        # --dry-run is not a real flag; fall back to checking the binary path
    except Exception:
        pass

    # More reliable: try to resolve the executable path directly
    try:
        from playwright._impl._driver import compute_driver_executable
        import json as _json

        driver = str(compute_driver_executable())
        result = subprocess.run(
            [driver, "print-api-json"],
            capture_output=True, text=True, timeout=10,
        )
        # If we get here, the driver works. Check if chromium path exists.
        # The simplest reliable check: try to import and see if launch works
        # But that's slow. Instead, look for the browser registry.
    except Exception:
        pass

    # Simplest reliable check: look for the chromium executable in the
    # playwright browsers directory.
    try:
        import playwright._impl._driver as _drv
        browsers_path = Path(_drv.compute_driver_executable()).parent / ".local-browsers"
        if not browsers_path.exists():
            # Try the standard location
            browsers_path = Path.home() / ".cache" / "ms-playwright"
            if sys.platform == "darwin":
                browsers_path = Path.home() / "Library" / "Caches" / "ms-playwright"
        if browsers_path.exists():
            chromium_dirs = list(browsers_path.glob("chromium*"))
            return len(chromium_dirs) > 0
    except Exception:
        pass

    return False


def install_chromium() -> bool:
    """Install Playwright Chromium browser. Returns True on success."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=False,
            timeout=300,
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
