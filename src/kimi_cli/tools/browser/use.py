"""BrowserUse integration — delegates to browser_use.Agent with Kimi API."""

import asyncio
import os
from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.soul.agent import Runtime
from kimi_cli.tools.utils import ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger


class Params(BaseModel):
    task: str = Field(
        description="The task to perform in the browser. Be specific about what to do."
    )
    initial_url: str | None = Field(
        default=None,
        description="Optional starting URL. If not provided, the agent starts with a blank page.",
    )
    max_steps: int = Field(
        default=30,
        description="Maximum number of steps the agent can take.",
        ge=1,
        le=100,
    )
    use_vision: bool = Field(
        default=True,
        description="Whether to use vision capabilities (screenshots) for the agent.",
    )


class BrowserUse(CallableTool2[Params]):
    name: str = "BrowserUse"
    description: str = load_desc(Path(__file__).parent / "use.md", {})
    params: type[Params] = Params

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        builder = ToolResultBuilder(max_line_length=None)

        try:
            from browser_use import Agent, Browser
            from browser_use.llm import ChatAnthropic
        except ImportError as exc:
            return builder.error(
                "browser-use is not installed. "
                "Run: poetry add browser-use playwright",
                brief="Missing browser-use",
            )

        # Resolve Kimi API credentials
        api_key, base_url, model_name, provider_type = self._resolve_kimi_credentials()
        if not api_key:
            return builder.error(
                "Could not resolve Kimi API key. Ensure kimi-cli is configured or "
                "set MOONSHOT_API_KEY / KIMI_API_KEY environment variable.",
                brief="No API key",
            )

        default_headers={
            "User-Agent": "OpenClaw", 
            "HTTP-Referer": "https://github.com/OpenClaw/OpenClaw",
            "X-Title": "OpenClaw"
        }
        #raise Exception(api_key, base_url, model_name, provider_type)
        llm = ChatAnthropic(
            model=model_name,
            api_key=api_key,
            base_url="https://api.kimi.com/coding/",
            default_headers=default_headers,
        )

        task = params.task
        if params.initial_url:
            task = f"Start at {params.initial_url}. {task}"

        logger.info("BrowserUse: launching agent with task: {task}", task=task[:100])

        try:
            # Use system Chrome if available, otherwise Playwright
            browser = Browser.from_system_chrome()
        except Exception as exc:
            logger.warning("BrowserUse: system chrome failed ({error}), using Playwright", error=exc)
            browser = Browser()

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            use_vision=params.use_vision,
        )

        try:
            result = await asyncio.wait_for(
                agent.run(max_steps=params.max_steps),
                timeout=300,
            )
            final_text = result.final_result() if hasattr(result, "final_result") else str(result)
            logger.info("BrowserUse: task completed")
            if final_text:
                builder.write(final_text)
            else:
                builder.write("[Task completed but no final result returned]")
            return builder.ok("BrowserUse task completed.")
        except asyncio.TimeoutError:
            logger.warning("BrowserUse: task timed out")
            return builder.error(
                "BrowserUse task timed out after 5 minutes.",
                brief="Task timed out",
            )
        except Exception as exc:
            logger.exception("BrowserUse: task failed")
            return builder.error(
                f"BrowserUse failed: {exc}", brief="BrowserUse failed"
            )

    def _resolve_kimi_credentials(self) -> tuple[str | None, str, str, str]:
        """Return (api_key, base_url, model_name, provider_type) from kimi-cli configuration."""
        # 1. Try environment variables (same precedence as kimi-cli)
        for env_var in ("MOONSHOT_API_KEY", "KIMI_API_KEY", "OPENAI_API_KEY"):
            if key := os.getenv(env_var):
                return key, "https://api.moonshot.ai/v1", self._get_default_model(), "openai_legacy"

        # 2. Try runtime config (the same way kimi-cli resolves it)
        runtime = self._runtime
        if runtime.llm and runtime.llm.provider_config:
            provider = runtime.llm.provider_config
            api_key = None
            if provider.oauth and runtime.oauth:
                api_key = runtime.oauth.resolve_api_key(
                    provider.api_key, provider.oauth
                )
            else:
                api_key = provider.api_key.get_secret_value()
            base_url = provider.base_url or "https://api.moonshot.ai/v1"
            model = runtime.llm.model_name or self._get_default_model()
            return api_key, base_url, model, provider.type

        # 3. Try config.models directly
        config = runtime.config
        if config.models:
            for alias, model_cfg in config.models.items():
                provider = config.providers.get(model_cfg.provider)
                if provider and provider.type in ("kimi", "openai_legacy", "anthropic"):
                    api_key = provider.api_key.get_secret_value()
                    base_url = provider.base_url or "https://api.moonshot.ai/v1"
                    return api_key, base_url, model_cfg.model, provider.type

        return None, "https://api.moonshot.ai/v1", self._get_default_model(), "openai_legacy"

    def _get_default_model(self) -> str:
        """Return a sensible default model name."""
        if self._runtime.llm and self._runtime.llm.model_name:
            return self._runtime.llm.model_name
        return "kimi-k2.5"
