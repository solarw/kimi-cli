"""Browser wait and key press tools."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class WaitParams(BaseModel):
    selector: str = Field(description="CSS selector to wait for.")
    state: str = Field(
        default="visible",
        description="State to wait for: visible, hidden, attached, detached.",
    )
    timeout: int = Field(
        default=10000,
        description="Maximum wait time in milliseconds.",
        ge=1000,
        le=60000,
    )


class PressKeyParams(BaseModel):
    key: str = Field(
        description="Key to press. Examples: Enter, Escape, Tab, ArrowDown, Control+a, F5, etc."
    )
    selector: str | None = Field(
        default=None,
        description="Optional selector of element to focus before pressing key.",
    )


class HoverParams(BaseModel):
    selector: str = Field(description="CSS selector of element to hover over.")
    timeout: int = Field(
        default=10000,
        description="Maximum wait time for the element.",
        ge=1000,
        le=60000,
    )


class BrowserWaitForSelector(CallableTool2[WaitParams]):
    name: str = "BrowserWaitForSelector"
    description: str = load_desc(Path(__file__).parent / "wait.md", {})
    params: type[WaitParams] = WaitParams

    @override
    async def __call__(self, params: WaitParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserWaitForSelector: waiting for {selector} ({state})", selector=params.selector, state=params.state)
            _, _, page = await get_browser()
            await page.wait_for_selector(
                params.selector,
                state=params.state,  # type: ignore[arg-type]
                timeout=params.timeout,
            )
            logger.info("BrowserWaitForSelector: {selector} is {state}", selector=params.selector, state=params.state)
            return builder.ok(f"Element '{params.selector}' is {params.state}.")
        except Exception as exc:
            logger.exception("BrowserWaitForSelector failed")
            return builder.error(
                f"Timeout waiting for '{params.selector}': {exc}",
                brief="Wait timeout",
            )


class BrowserPressKey(CallableTool2[PressKeyParams]):
    name: str = "BrowserPressKey"
    description: str = load_desc(Path(__file__).parent / "press_key.md", {})
    params: type[PressKeyParams] = PressKeyParams

    @override
    async def __call__(self, params: PressKeyParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserPressKey: pressing {key}", key=params.key)
            _, _, page = await get_browser()

            if params.selector:
                element = await page.wait_for_selector(params.selector)
                if element is None:
                    return builder.error(
                        f"Element not found: {params.selector}",
                        brief="Element not found",
                    )
                await element.press(params.key)
            else:
                await page.keyboard.press(params.key)

            logger.info("BrowserPressKey: pressed {key}", key=params.key)
            return builder.ok(f"Pressed '{params.key}'.")
        except Exception as exc:
            logger.exception("BrowserPressKey failed")
            return builder.error(f"Failed to press key: {exc}", brief="Press key failed")


class BrowserHover(CallableTool2[HoverParams]):
    name: str = "BrowserHover"
    description: str = load_desc(Path(__file__).parent / "hover.md", {})
    params: type[HoverParams] = HoverParams

    @override
    async def __call__(self, params: HoverParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserHover: hovering over {selector}", selector=params.selector)
            _, _, page = await get_browser()
            element = await page.wait_for_selector(
                params.selector, timeout=params.timeout
            )
            if element is None:
                return builder.error(
                    f"Element not found: {params.selector}",
                    brief="Element not found",
                )
            await element.hover()
            logger.info("BrowserHover: hovered over {selector}", selector=params.selector)
            return builder.ok(f"Hovered over '{params.selector}'.")
        except Exception as exc:
            logger.exception("BrowserHover failed")
            return builder.error(f"Hover failed: {exc}", brief="Hover failed")
