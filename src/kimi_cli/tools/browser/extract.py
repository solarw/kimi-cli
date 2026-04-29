"""Browser extraction tools (screenshot, text extract, close)."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import (
    close_browser,
    get_page_content,
    get_page_title,
    get_page_url,
    take_screenshot,
)
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class ScreenshotParams(BaseModel):
    filename: str | None = Field(
        default=None,
        description="Optional filename for the screenshot. Auto-generated if not provided.",
    )
    full_page: bool = Field(
        default=False,
        description="Whether to capture the full page or just the viewport.",
    )


class ExtractParams(BaseModel):
    max_length: int = Field(
        default=5000,
        description="Maximum characters to return.",
        ge=100,
        le=20000,
    )


class BrowserScreenshot(CallableTool2[ScreenshotParams]):
    name: str = "BrowserScreenshot"
    description: str = load_desc(Path(__file__).parent / "screenshot.md", {})
    params: type[ScreenshotParams] = ScreenshotParams

    @override
    async def __call__(self, params: ScreenshotParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserScreenshot: taking screenshot")
            path = await take_screenshot(params.filename)
            logger.info("BrowserScreenshot: saved to {path}", path=path)
            return builder.ok(
                f"Screenshot saved. View with ReadMediaFile(path='{path}')",
                brief=f"Screenshot: {path.name}",
            )
        except Exception as exc:
            logger.exception("BrowserScreenshot failed")
            return builder.error(
                f"Screenshot failed: {exc}", brief="Screenshot failed"
            )


class BrowserExtract(CallableTool2[ExtractParams]):
    name: str = "BrowserExtract"
    description: str = load_desc(Path(__file__).parent / "extract.md", {})
    params: type[ExtractParams] = ExtractParams

    @override
    async def __call__(self, params: ExtractParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserExtract: extracting content")
            content = await get_page_content()
            title = await get_page_title()
            url = await get_page_url()
            logger.info("BrowserExtract: extracted {len} chars from {url}", len=len(content), url=url)
            builder.write(f"Title: {title}\nURL: {url}\n\n")
            if len(content) > params.max_length:
                builder.write(content[:params.max_length])
                builder.write(
                    f"\n\n[Content truncated: {len(content)} chars total. "
                    f"Use max_length parameter or scroll to get more.]"
                )
            else:
                builder.write(content)
            return builder.ok()
        except Exception as exc:
            logger.exception("BrowserExtract failed")
            return builder.error(
                f"Extraction failed: {exc}", brief="Extraction failed"
            )


class BrowserClose(BaseModel):
    pass


class BrowserCloseTool(CallableTool2[BrowserClose]):
    name: str = "BrowserClose"
    description: str = load_desc(Path(__file__).parent / "close.md", {})
    params: type[BrowserClose] = BrowserClose

    @override
    async def __call__(self, params: BrowserClose) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserClose: closing browser")
            await close_browser()
            logger.info("BrowserClose: browser closed")
            return builder.ok("Browser closed.")
        except Exception as exc:
            logger.exception("BrowserClose failed")
            return builder.error(
                f"Failed to close browser: {exc}", brief="Close failed"
            )
