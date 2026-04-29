"""Browser network interception tool."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger

# Module-level storage for intercepted requests
_intercepted_requests: list[dict] = []
_intercepting: bool = False


class StartParams(BaseModel):
    url_pattern: str = Field(
        default="**",
        description="URL pattern to intercept (glob). Use '**/*api*' for API calls, '**' for all.",
    )


class StopParams(BaseModel):
    pass


class ListParams(BaseModel):
    limit: int = Field(
        default=50,
        description="Maximum number of requests to return.",
        ge=1,
        le=200,
    )
    filter_url: str | None = Field(
        default=None,
        description="Optional substring filter for URLs.",
    )


class BrowserNetworkStart(CallableTool2[StartParams]):
    name: str = "BrowserNetworkStart"
    description: str = load_desc(Path(__file__).parent / "network_start.md", {})
    params: type[StartParams] = StartParams

    @override
    async def __call__(self, params: StartParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        global _intercepting, _intercepted_requests

        try:
            logger.info("BrowserNetworkStart: starting interception for {pattern}", pattern=params.url_pattern)
            _, _, page = await get_browser()

            _intercepted_requests = []
            _intercepting = True

            async def handle_route(route, request):
                _intercepted_requests.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                })
                await route.continue_()

            await page.route(params.url_pattern, handle_route)
            logger.info("BrowserNetworkStart: interception active")
            return builder.ok(f"Network interception started for pattern: {params.url_pattern}")
        except Exception as exc:
            logger.exception("BrowserNetworkStart failed")
            return builder.error(f"Failed to start interception: {exc}", brief="Network start failed")


class BrowserNetworkList(CallableTool2[ListParams]):
    name: str = "BrowserNetworkList"
    description: str = load_desc(Path(__file__).parent / "network_list.md", {})
    params: type[ListParams] = ListParams

    @override
    async def __call__(self, params: ListParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        global _intercepted_requests

        try:
            logger.info("BrowserNetworkList: listing {count} requests", count=len(_intercepted_requests))
            requests = _intercepted_requests[:]
            if params.filter_url:
                requests = [r for r in requests if params.filter_url in r["url"]]
            requests = requests[-params.limit:]

            if not requests:
                builder.write("No intercepted requests yet. Make sure BrowserNetworkStart was called and page navigation happened.")
                return builder.ok()

            for i, req in enumerate(requests):
                builder.write(f"{i+1}. [{req['method']}] {req['url']}\n")
                if req.get("headers"):
                    builder.write(f"   Headers: {req['headers']}\n")

            return builder.ok(f"Total intercepted: {len(_intercepted_requests)}")
        except Exception as exc:
            logger.exception("BrowserNetworkList failed")
            return builder.error(f"Failed to list requests: {exc}", brief="Network list failed")


class BrowserNetworkStop(CallableTool2[StopParams]):
    name: str = "BrowserNetworkStop"
    description: str = load_desc(Path(__file__).parent / "network_stop.md", {})
    params: type[StopParams] = StopParams

    @override
    async def __call__(self, params: StopParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        global _intercepting, _intercepted_requests

        try:
            logger.info("BrowserNetworkStop: stopping interception")
            _intercepting = False
            count = len(_intercepted_requests)
            _intercepted_requests = []

            _, _, page = await get_browser()
            await page.unroute_all()

            logger.info("BrowserNetworkStop: stopped, cleared {count} requests", count=count)
            return builder.ok(f"Network interception stopped. Cleared {count} requests.")
        except Exception as exc:
            logger.exception("BrowserNetworkStop failed")
            return builder.error(f"Failed to stop interception: {exc}", brief="Network stop failed")
