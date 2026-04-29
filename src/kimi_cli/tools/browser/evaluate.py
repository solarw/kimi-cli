"""Browser JavaScript evaluation tool."""

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.browser.manager import get_browser
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class Params(BaseModel):
    script: str = Field(
        description="JavaScript code to execute on the current page. Use 'return' to get a result."
    )
    args: list = Field(
        default_factory=list,
        description="Optional arguments to pass to the script (available as 'args' array).",
    )


class BrowserEvaluate(CallableTool2[Params]):
    name: str = "BrowserEvaluate"
    description: str = load_desc(Path(__file__).parent / "evaluate.md", {})
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)
        try:
            logger.info(
                "BrowserEvaluate: executing script (len={len})", len=len(params.script)
            )
            _, _, page = await get_browser()

            # Wrap script in an IIFE so Playwright can evaluate it.
            # Playwright page.evaluate expects a function expression.
            script_body = params.script.strip()
            if params.args:
                wrapped = f"""
                (function() {{
                    const args = {params.args};
                    {script_body}
                }})()
                """
            else:
                wrapped = f"() => {{ {script_body} }}"

            result = await page.evaluate(wrapped)
            logger.info("BrowserEvaluate: executed successfully")

            # Serialize result for display
            import json

            if result is None:
                builder.write("[null]")
            elif isinstance(result, (str, int, float, bool)):
                builder.write(str(result))
            else:
                try:
                    pretty = json.dumps(result, ensure_ascii=False, indent=2, default=str)
                    builder.write(pretty)
                except Exception:
                    builder.write(str(result))

            return builder.ok("Script executed successfully.")
        except Exception as exc:
            logger.exception("BrowserEvaluate failed")
            return builder.error(
                f"Script execution failed: {exc}", brief="Evaluate failed"
            )
