"""Browser navigation tool."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser, get_page_title, get_page_url
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class Params(BaseModel):
    url: str = Field(description="The URL to navigate to.")
    wait_until: str = Field(
        default="networkidle",
        description="When to consider navigation complete. Options: load, domcontentloaded, networkidle, commit.",
    )
    timeout: int = Field(
        default=30000,
        description="Maximum navigation time in milliseconds.",
        ge=1000,
        le=120000,
    )


class BrowserNavigate(CallableTool2[Params]):
    name: str = "BrowserNavigate"
    description: str = load_desc(Path(__file__).parent / "navigate.md", {})
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserNavigate: navigating to {url}", url=params.url)
            _, _, page = await get_browser()
            await page.goto(
                params.url,
                wait_until=params.wait_until,  # type: ignore[arg-type]
                timeout=params.timeout,
            )
            title = await get_page_title()
            url = await get_page_url()
            logger.info("BrowserNavigate: loaded {title} at {url}", title=title, url=url)
            builder.write(f"Title: {title}\nURL: {url}")
            return builder.ok("Page loaded successfully.")
        except Exception as exc:
            logger.exception("BrowserNavigate failed for {url}", url=params.url)
            return builder.error(f"Failed to navigate: {exc}", brief="Navigation failed")
