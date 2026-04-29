"""Browser HTML extraction tool."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class Params(BaseModel):
    selector: str | None = Field(
        default=None,
        description="Optional CSS selector to extract HTML of a specific element. If omitted, returns full page HTML.",
    )
    max_length: int = Field(
        default=10000,
        description="Maximum characters of HTML to return.",
        ge=100,
        le=50000,
    )


class BrowserGetHTML(CallableTool2[Params]):
    name: str = "BrowserGetHTML"
    description: str = load_desc(Path(__file__).parent / "html.md", {})
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserGetHTML: extracting HTML")
            _, _, page = await get_browser()

            if params.selector:
                element = await page.query_selector(params.selector)
                if element is None:
                    return builder.error(
                        f"Element not found: {params.selector}",
                        brief="Element not found",
                    )
                html = await element.evaluate("el => el.outerHTML")
            else:
                html = await page.content()

            logger.info("BrowserGetHTML: extracted {len} chars", len=len(html) if html else 0)

            if html is None:
                html = ""

            if len(html) > params.max_length:
                builder.write(html[:params.max_length])
                builder.write(
                    f"\n\n[HTML truncated: {len(html)} chars total. Use selector or BrowserEvaluate to get specific parts.]"
                )
            else:
                builder.write(html)

            return builder.ok("HTML extracted.")
        except Exception as exc:
            logger.exception("BrowserGetHTML failed")
            return builder.error(f"Failed to get HTML: {exc}", brief="GetHTML failed")
