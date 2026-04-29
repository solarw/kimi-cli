"""Browser interaction tools (click, type, scroll)."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class ClickParams(BaseModel):
    selector: str = Field(
        description="CSS selector or XPath of the element to click."
    )
    timeout: int = Field(
        default=10000,
        description="Maximum wait time for the element in milliseconds.",
        ge=1000,
        le=60000,
    )


class TypeParams(BaseModel):
    selector: str = Field(
        description="CSS selector or XPath of the input field."
    )
    text: str = Field(description="The text to type into the field.")
    clear_first: bool = Field(
        default=True,
        description="Whether to clear the field before typing.",
    )
    submit: bool = Field(
        default=False,
        description="Whether to press Enter after typing.",
    )
    timeout: int = Field(
        default=10000,
        description="Maximum wait time for the element in milliseconds.",
        ge=1000,
        le=60000,
    )


class ScrollParams(BaseModel):
    direction: str = Field(
        default="down",
        description="Direction to scroll: down, up, left, right.",
    )
    amount: int = Field(
        default=500,
        description="Pixels to scroll.",
        ge=1,
        le=10000,
    )


class BrowserClick(CallableTool2[ClickParams]):
    name: str = "BrowserClick"
    description: str = load_desc(Path(__file__).parent / "click.md", {})
    params: type[ClickParams] = ClickParams

    @override
    async def __call__(self, params: ClickParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserClick: clicking {selector}", selector=params.selector)
            _, _, page = await get_browser()
            element = await page.wait_for_selector(
                params.selector, timeout=params.timeout
            )
            if element is None:
                logger.warning("BrowserClick: element not found {selector}", selector=params.selector)
                return builder.error(
                    f"Element not found: {params.selector}",
                    brief="Element not found",
                )
            await element.click()
            logger.info("BrowserClick: clicked {selector}", selector=params.selector)
            return builder.ok(f"Clicked element: {params.selector}")
        except Exception as exc:
            logger.exception("BrowserClick failed for {selector}", selector=params.selector)
            return builder.error(f"Click failed: {exc}", brief="Click failed")


class BrowserType(CallableTool2[TypeParams]):
    name: str = "BrowserType"
    description: str = load_desc(Path(__file__).parent / "type.md", {})
    params: type[TypeParams] = TypeParams

    @override
    async def __call__(self, params: TypeParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserType: typing into {selector}", selector=params.selector)
            _, _, page = await get_browser()
            element = await page.wait_for_selector(
                params.selector, timeout=params.timeout
            )
            if element is None:
                logger.warning("BrowserType: element not found {selector}", selector=params.selector)
                return builder.error(
                    f"Element not found: {params.selector}",
                    brief="Element not found",
                )
            if params.clear_first:
                await element.fill("")
            await element.type(params.text)
            if params.submit:
                await element.press("Enter")
            logger.info("BrowserType: typed into {selector}", selector=params.selector)
            return builder.ok(f"Typed '{params.text}' into {params.selector}")
        except Exception as exc:
            logger.exception("BrowserType failed for {selector}", selector=params.selector)
            return builder.error(f"Type failed: {exc}", brief="Type failed")


class BrowserScroll(CallableTool2[ScrollParams]):
    name: str = "BrowserScroll"
    description: str = load_desc(Path(__file__).parent / "scroll.md", {})
    params: type[ScrollParams] = ScrollParams

    @override
    async def __call__(self, params: ScrollParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserScroll: scrolling {direction} by {amount}", direction=params.direction, amount=params.amount)
            _, _, page = await get_browser()
            direction_map = {
                "down": (0, params.amount),
                "up": (0, -params.amount),
                "left": (-params.amount, 0),
                "right": (params.amount, 0),
            }
            dx, dy = direction_map.get(params.direction, (0, params.amount))
            await page.evaluate(f"window.scrollBy({dx}, {dy})")
            logger.info("BrowserScroll: scrolled {direction} by {amount}", direction=params.direction, amount=params.amount)
            return builder.ok(f"Scrolled {params.direction} by {params.amount}px")
        except Exception as exc:
            logger.exception("BrowserScroll failed")
            return builder.error(f"Scroll failed: {exc}", brief="Scroll failed")
