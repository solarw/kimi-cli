"""Browser tab management tools."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class GetTabsParams(BaseModel):
    pass


class SwitchTabParams(BaseModel):
    index: int | None = Field(
        default=None,
        description="Zero-based index of tab to switch to.",
    )
    url_contains: str | None = Field(
        default=None,
        description="Switch to tab whose URL contains this string.",
    )


class NewTabParams(BaseModel):
    url: str | None = Field(
        default=None,
        description="Optional URL to open in new tab.",
    )


class BrowserGetTabs(CallableTool2[GetTabsParams]):
    name: str = "BrowserGetTabs"
    description: str = load_desc(Path(__file__).parent / "tabs_get.md", {})
    params: type[GetTabsParams] = GetTabsParams

    @override
    async def __call__(self, params: GetTabsParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserGetTabs: listing tabs")
            _, browser, page = await get_browser()
            contexts = browser.contexts
            if not contexts:
                builder.write("No contexts found.")
                return builder.ok()

            tabs = []
            for ctx in contexts:
                for i, p in enumerate(ctx.pages):
                    tabs.append({
                        "index": i,
                        "url": p.url,
                        "title": await p.title(),
                        "active": p == page,
                    })

            for t in tabs:
                marker = " [ACTIVE]" if t["active"] else ""
                builder.write(f"{t['index']}: {t['title']}{marker}\n   URL: {t['url']}\n")

            return builder.ok(f"Total tabs: {len(tabs)}")
        except Exception as exc:
            logger.exception("BrowserGetTabs failed")
            return builder.error(f"Failed to get tabs: {exc}", brief="Get tabs failed")


class BrowserSwitchTab(CallableTool2[SwitchTabParams]):
    name: str = "BrowserSwitchTab"
    description: str = load_desc(Path(__file__).parent / "tabs_switch.md", {})
    params: type[SwitchTabParams] = SwitchTabParams

    @override
    async def __call__(self, params: SwitchTabParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserSwitchTab: switching tab")
            _, browser, _ = await get_browser()
            contexts = browser.contexts
            if not contexts:
                return builder.error("No browser contexts.", brief="No contexts")

            pages = contexts[0].pages
            target = None

            if params.index is not None:
                if 0 <= params.index < len(pages):
                    target = pages[params.index]
                else:
                    return builder.error(
                        f"Tab index {params.index} out of range (0-{len(pages)-1})",
                        brief="Invalid tab index",
                    )
            elif params.url_contains:
                for p in pages:
                    if params.url_contains in p.url:
                        target = p
                        break
                if target is None:
                    return builder.error(
                        f"No tab with URL containing '{params.url_contains}'",
                        brief="Tab not found",
                    )
            else:
                return builder.error(
                    "Specify index or url_contains.", brief="No criteria"
                )

            await target.bring_to_front()
            logger.info("BrowserSwitchTab: switched to {url}", url=target.url)
            return builder.ok(f"Switched to tab: {target.url}")
        except Exception as exc:
            logger.exception("BrowserSwitchTab failed")
            return builder.error(f"Failed to switch tab: {exc}", brief="Switch tab failed")


class BrowserNewTab(CallableTool2[NewTabParams]):
    name: str = "BrowserNewTab"
    description: str = load_desc(Path(__file__).parent / "tabs_new.md", {})
    params: type[NewTabParams] = NewTabParams

    @override
    async def __call__(self, params: NewTabParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserNewTab: creating new tab")
            _, browser, _ = await get_browser()
            contexts = browser.contexts
            if not contexts:
                return builder.error("No browser contexts.", brief="No contexts")

            page = await contexts[0].new_page()
            if params.url:
                await page.goto(params.url)
                logger.info("BrowserNewTab: opened {url}", url=params.url)
            else:
                logger.info("BrowserNewTab: new tab created")

            return builder.ok(f"New tab opened: {page.url}")
        except Exception as exc:
            logger.exception("BrowserNewTab failed")
            return builder.error(f"Failed to create tab: {exc}", brief="New tab failed")
