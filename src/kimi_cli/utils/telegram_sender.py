"""Telegram notification sender for Kimi CLI.

Reuses the same bot token as telegram_bot.py.
Set TELEGRAM_BOT_TOKEN and TELEGRAM_NOTIFICATION_CHAT_ID env vars.
"""

from __future__ import annotations

import os

from kimi_cli.utils.logging import logger

_bot = None


def _get_bot():
    global _bot
    if _bot is None:
        try:
            from aiogram import Bot
        except ImportError:
            logger.warning("aiogram not installed, Telegram notifications disabled")
            return None
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram notifications disabled")
            return None
        _bot = Bot(token=token)
    return _bot


async def send_telegram_notification(text: str) -> None:
    bot = _get_bot()
    if bot is None:
        return
    chat_id = os.getenv("TELEGRAM_NOTIFICATION_CHAT_ID")
    if not chat_id:
        allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        if allowed:
            chat_id = allowed.split(",")[0].strip()
    if not chat_id:
        logger.warning(
            "TELEGRAM_NOTIFICATION_CHAT_ID not set, cannot send Telegram notification"
        )
        return
    try:
        await bot.send_message(chat_id=int(chat_id), text=text)
    except Exception:
        logger.exception("Failed to send Telegram notification")
