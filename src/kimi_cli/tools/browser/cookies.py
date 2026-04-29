"""Browser cookie and storage tools."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class GetCookiesParams(BaseModel):
    domain: str | None = Field(
        default=None,
        description="Optional domain filter for cookies.",
    )


class SetCookieParams(BaseModel):
    name: str = Field(description="Cookie name.")
    value: str = Field(description="Cookie value.")
    domain: str | None = Field(default=None, description="Cookie domain.")
    path: str = Field(default="/", description="Cookie path.")
    http_only: bool = Field(default=False, description="HttpOnly flag.")
    secure: bool = Field(default=False, description="Secure flag.")


class GetStorageParams(BaseModel):
    storage_type: str = Field(
        default="localStorage",
        description="Type of storage: localStorage or sessionStorage.",
    )
    key: str | None = Field(
        default=None,
        description="Specific key to read. If omitted, returns all keys.",
    )


class BrowserGetCookies(CallableTool2[GetCookiesParams]):
    name: str = "BrowserGetCookies"
    description: str = load_desc(Path(__file__).parent / "cookies_get.md", {})
    params: type[GetCookiesParams] = GetCookiesParams

    @override
    async def __call__(self, params: GetCookiesParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserGetCookies: getting cookies")
            _, _, page = await get_browser()
            cookies = await page.context.cookies()

            if params.domain:
                cookies = [c for c in cookies if params.domain in (c.get("domain") or "")]

            if not cookies:
                builder.write("No cookies found.")
                return builder.ok()

            for c in cookies:
                builder.write(
                    f"{c.get('name')}={c.get('value')[:50]} "
                    f"(domain={c.get('domain')} path={c.get('path')} "
                    f"secure={c.get('secure')} httpOnly={c.get('httpOnly')})\n"
                )

            return builder.ok(f"Total cookies: {len(cookies)}")
        except Exception as exc:
            logger.exception("BrowserGetCookies failed")
            return builder.error(f"Failed to get cookies: {exc}", brief="Get cookies failed")


class BrowserSetCookie(CallableTool2[SetCookieParams]):
    name: str = "BrowserSetCookie"
    description: str = load_desc(Path(__file__).parent / "cookies_set.md", {})
    params: type[SetCookieParams] = SetCookieParams

    @override
    async def __call__(self, params: SetCookieParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserSetCookie: setting {name}", name=params.name)
            _, _, page = await get_browser()
            cookie = {
                "name": params.name,
                "value": params.value,
                "path": params.path,
                "httpOnly": params.http_only,
                "secure": params.secure,
            }
            if params.domain:
                cookie["domain"] = params.domain

            await page.context.add_cookies([cookie])
            logger.info("BrowserSetCookie: set {name}", name=params.name)
            return builder.ok(f"Cookie '{params.name}' set.")
        except Exception as exc:
            logger.exception("BrowserSetCookie failed")
            return builder.error(f"Failed to set cookie: {exc}", brief="Set cookie failed")


class BrowserGetStorage(CallableTool2[GetStorageParams]):
    name: str = "BrowserGetStorage"
    description: str = load_desc(Path(__file__).parent / "storage.md", {})
    params: type[GetStorageParams] = GetStorageParams

    @override
    async def __call__(self, params: GetStorageParams) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info("BrowserGetStorage: reading {storage}", storage=params.storage_type)
            _, _, page = await get_browser()

            if params.key:
                result = await page.evaluate(
                    f"() => {params.storage_type}.getItem('{params.key}')"
                )
                builder.write(f"{params.key}={result}")
            else:
                keys = await page.evaluate(
                    f"() => Object.keys({params.storage_type})"
                )
                if not keys:
                    builder.write("Storage is empty.")
                else:
                    for key in keys:
                        value = await page.evaluate(
                            f"() => {params.storage_type}.getItem('{key}')"
                        )
                        builder.write(f"{key}={value[:200] if value else 'null'}\n")

            return builder.ok(f"{params.storage_type} read.")
        except Exception as exc:
            logger.exception("BrowserGetStorage failed")
            return builder.error(f"Failed to read storage: {exc}", brief="Get storage failed")
