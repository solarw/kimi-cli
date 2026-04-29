"""Browser session manager for Playwright-based browser tools."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from kimi_cli.utils.logging import logger

_playwright: Any = None
_browser: Any = None
_page: Any = None
_lock = asyncio.Lock()


def _find_chromium_executable() -> str | None:
    """Find a system chromium executable for Playwright on unsupported platforms."""
    candidates = [
        "/snap/bin/chromium",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for candidate in candidates:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    return None


async def get_browser() -> tuple[Any, Any, Any]:
    """Return (playwright, browser, page) singleton trio."""
    global _playwright, _browser, _page

    async with _lock:
        if _page is not None and not _page.is_closed():
            try:
                await _page.evaluate("1")
                return _playwright, _browser, _page
            except Exception:
                logger.warning("Browser page is unresponsive, restarting...")
                await _close_all()

        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright is not None:
            try:
                await _playwright.stop()
            except Exception:
                pass
            _playwright = None

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. "
                "Run: poetry add playwright"
            ) from exc

        _playwright = await async_playwright().start()

        launch_kwargs: dict[str, Any] = {"headless": False}
        system_chromium = _find_chromium_executable()
        if system_chromium:
            launch_kwargs["executable_path"] = system_chromium
            logger.info("Using system chromium: {path}", path=system_chromium)

        try:
            _browser = await _playwright.chromium.launch(**launch_kwargs)
        except Exception as exc:
            logger.warning("Failed to launch chromium: {error}", error=exc)
            if system_chromium:
                logger.info("Retrying without executable_path...")
                _browser = await _playwright.chromium.launch(headless=True)
            else:
                raise

        _page = await _browser.new_page(viewport={"width": 1280, "height": 800})
        logger.info("Browser launched")
        return _playwright, _browser, _page


async def _close_all() -> None:
    global _playwright, _browser, _page
    if _page is not None:
        try:
            await _page.close()
        except Exception:
            pass
        _page = None
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright is not None:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None


async def close_browser() -> None:
    async with _lock:
        await _close_all()
        logger.info("Browser closed")


def _get_screenshots_dir() -> Path:
    """Return a directory for storing browser screenshots."""
    from kimi_cli.share import get_share_dir

    screenshots_dir = get_share_dir() / "browser_screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


async def take_screenshot(name: str | None = None) -> Path:
    """Take a screenshot and save it to the share directory."""
    _, _, page = await get_browser()
    screenshots_dir = _get_screenshots_dir()
    if name is None:
        import time

        name = f"screenshot_{int(time.time())}.png"
    elif not name.endswith(".png"):
        name = f"{name}.png"
    path = screenshots_dir / name
    await page.screenshot(path=str(path), full_page=False)
    logger.info("Screenshot saved to {path}", path=path)
    return path


async def get_page_content() -> str:
    """Return the current page text content."""
    _, _, page = await get_browser()
    return await page.inner_text("body")


async def get_page_url() -> str:
    """Return the current page URL."""
    _, _, page = await get_browser()
    return page.url


async def get_page_title() -> str:
    """Return the current page title."""
    _, _, page = await get_browser()
    return await page.title()
