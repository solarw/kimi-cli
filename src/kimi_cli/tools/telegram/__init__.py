from __future__ import annotations

from pathlib import Path
from typing import Literal, override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.utils import load_desc
from kimi_cli.utils.telegram_sender import send_telegram_notification


class Params(BaseModel):
    title: str = Field(description="Short title of the notification.")
    body: str = Field(default="", description="Optional body text of the notification.")
    severity: Literal["info", "success", "warning", "error"] = Field(
        default="info", description="Severity level of the notification."
    )


class SendTelegramNotification(CallableTool2[Params]):
    name: str = "SendTelegramNotification"
    description: str = load_desc(
        Path(__file__).parent / "send_telegram_notification.md", {}
    )
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        emoji = {"error": "❌", "warning": "⚠️", "success": "✅"}.get(params.severity, "ℹ️")
        text = f"{emoji} [{params.severity.upper()}] {params.title}"
        if params.body:
            text += f"\n\n{params.body[:800]}"
        await send_telegram_notification(text)
        return ToolOk(output="", message="Notification sent")
