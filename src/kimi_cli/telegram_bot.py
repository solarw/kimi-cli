"""Telegram bot for Kimi CLI.

Usage:
    export TELEGRAM_BOT_TOKEN=your_token
    export TELEGRAM_ALLOWED_USERS=user1_id,user2_id  # optional
    poetry run python -m kimi_cli.telegram_bot
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable, Coroutine
from kaos.path import KaosPath
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from the project root
load_dotenv()

from kimi_cli.agentspec import DEFAULT_AGENT_FILE
from kimi_cli.auth.oauth import OAuthManager
from kimi_cli.config import Config, LLMModel, LLMProvider, load_config
from kimi_cli.llm import augment_provider_with_env_vars, create_llm
from kimi_cli.session import Session

from kimi_cli.soul import RunCancelled, run_soul
from kimi_cli.soul.agent import Runtime, load_agent
from kimi_cli.soul.context import Context
from kimi_cli.soul.kimisoul import KimiSoul
from kimi_cli.utils.logging import logger
from kimi_cli.wire import Wire
from kosong.message import ThinkPart, ToolCall, ToolCallPart
from kosong.tooling import ToolResult
from kimi_cli.wire.types import ContentPart, TextPart, TurnBegin, TurnEnd, WireMessage, Notification, SubagentEvent

# aiogram imports
try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.filters import Command
except ImportError:
    raise ImportError(
        "aiogram is not installed. Run: poetry add aiogram"
    )


class TelegramBot:
    def __init__(
        self,
        token: str,
        allowed_users: set[int] | None = None,
        config_path: Path | None = None,
    ):
        self.token = token
        self.allowed_users = allowed_users
        self.config_path = config_path
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self._soul: KimiSoul | None = None
        self._runtime: Runtime | None = None
        self._cancel_event: asyncio.Event | None = None

        self._setup_handlers()

    def _setup_handlers(self) -> None:
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message) -> None:
            await message.answer(
                "Привет! Я Kimi бот.\n"
                "Отправь мне сообщение — я выполню его как задачу.\n"
                "Команды:\n"
                "/start — это сообщение\n"
                "/session — создать новую сессию\n"
                "/reset — сбросить контекст"
            )

        @self.dp.message(Command("session"))
        async def cmd_session(message: types.Message) -> None:
            if not self._check_user(message):
                return
            await self._init_session()
            await message.answer("✅ Новая сессия создана. Готов к работе!")

        @self.dp.message(Command("reset"))
        async def cmd_reset(message: types.Message) -> None:
            if not self._check_user(message):
                return
            if self._soul is not None:
                self._soul = None
                self._runtime = None
            await message.answer("🗑 Контекст сброшен. Отправь /session чтобы начать заново.")

        @self.dp.message(Command("stop"))
        @self.dp.message(Command("cancel"))
        async def cmd_stop(message: types.Message) -> None:
            if not self._check_user(message):
                return
            if self._cancel_event is not None and not self._cancel_event.is_set():
                self._cancel_event.set()
                await message.answer("🛑 Останавливаю текущую задачу...")
            else:
                await message.answer("ℹ️ Нет активной задачи для остановки.")

        @self.dp.message()
        async def handle_message(message: types.Message) -> None:
            if not self._check_user(message):
                return
            if message.text is None:
                return

            if self._soul is None:
                init_msg = await message.answer("⏳ Инициализация сессии...")
                await self._init_session()
                await init_msg.edit_text("✅ Сессия готова")

            status_msg = await message.answer("🤔 Думаю...")
            print(f"[STATUS MSG] chat_id={status_msg.chat.id}, msg_id={status_msg.message_id}")
            result = await self._run_turn(message.text, status_msg)
            final_text = result.strip() if result else ""
            if final_text:
                try:
                    await status_msg.edit_text(final_text, parse_mode=None)
                except Exception as exc:
                    print(f"[EDIT ERROR] {exc}")
                    await message.answer(final_text, parse_mode=None)
            else:
                try:
                    await status_msg.edit_text("✅ Готово (нет текстового ответа)")
                except Exception:
                    pass

    def _check_user(self, message: types.Message) -> bool:
        if self.allowed_users is None:
            return True
        user_id = message.from_user.id if message.from_user else None
        if user_id not in self.allowed_users:
            asyncio.create_task(message.answer("⛔ Доступ запрещён."))
            return False
        return True

    async def _init_session(self) -> None:
        config = load_config(self.config_path)
        oauth = OAuthManager(config)

        model_name = config.default_model
        if model_name and model_name in config.models:
            model = config.models[model_name]
            provider = config.providers[model.provider]
        else:
            model = LLMModel(provider="", model="", max_context_size=100_000)
            provider = LLMProvider(type="kimi", base_url="", api_key=os.environ.get("MOONSHOT_API_KEY", ""))

        augment_provider_with_env_vars(provider, model)

        llm = create_llm(provider, model, oauth=oauth)

        session = await Session.create(
            work_dir=KaosPath.cwd(),
        )

        runtime = await Runtime.create(
            config,
            oauth,
            llm,
            session,
            yolo=True,
            afk=True,
            runtime_afk=True,
        )
        runtime.ui_mode = "telegram"

        agent = await load_agent(
            DEFAULT_AGENT_FILE,
            runtime,
            mcp_configs=[],
            start_mcp_loading=False,
        )

        context = Context(session.context_file)
        await context.restore()

        if context.system_prompt is not None:
            agent = __import__("dataclasses").replace(agent, system_prompt=context.system_prompt)
        else:
            await context.write_system_prompt(agent.system_prompt)

        soul = KimiSoul(agent, context=context)
        self._soul = soul
        self._runtime = runtime

    async def _run_turn(self, user_input: str, status_msg: types.Message) -> str:
        assert self._soul is not None
        assert self._runtime is not None

        results: list[str] = []
        cancel_event = asyncio.Event()
        self._cancel_event = cancel_event

        # Status history: list of lines to show in Telegram
        status_history: list[str] = []
        last_status_time = 0.0
        status_lock = asyncio.Lock()
        MAX_STATUS_LINES = 15

        async def _update_status(new_line: str) -> None:
            """Append line to status history and update Telegram (throttled 1/sec)."""
            nonlocal last_status_time
            async with status_lock:
                status_history.append(new_line)
                # Keep only last N lines
                while len(status_history) > MAX_STATUS_LINES:
                    status_history.pop(0)
                # Build display text (Telegram limit is 4096; if it exceeds, edit_text will fail gracefully)
                text = "\n".join(status_history)
                now = time.monotonic()
                if now - last_status_time >= 1.0:
                    last_status_time = now
                    try:
                        await status_msg.edit_text(text, parse_mode=None)
                        print(f"[STATUS UPDATED] {new_line[:80]}")
                    except Exception as exc:
                        print(f"[STATUS EDIT ERROR] {exc}")

        async def ui_loop(wire: Wire) -> None:
            ui_side = wire.ui_side(merge=True)
            step_num = 0
            try:
                while True:
                    msg = await ui_side.receive()
                    msg_type = type(msg).__name__
                    ts = time.strftime("%H:%M:%S")
                    
                    # Text response
                    if isinstance(msg, TextPart):
                        print(f"[{ts}] [BOT] {msg.text}")
                        results.append(msg.text)
                    
                    # Thinking/reasoning — show actual think text
                    elif hasattr(msg, 'think') and msg.think:
                        think = msg.think.strip()
                        print(f"[{ts}] [THINK] {think}")
                        # Full think text in Telegram (will be truncated by MAX_STATUS_CHARS if too long)
                        preview = think.replace('\n', ' ')
                        await _update_status(f"💭 {preview}")
                    
                    # Tool call (kosong.message.ToolCall)
                    elif isinstance(msg, ToolCall):
                        tool_name = msg.function.name if hasattr(msg, 'function') else str(msg)
                        func_args = msg.function.arguments if hasattr(msg.function, 'arguments') else ""
                        print(f"[{ts}] [TOOL CALL] {tool_name} args={func_args}")
                        await _update_status(f"🔧 {tool_name}")
                    
                    # Tool call part (partial JSON)
                    elif isinstance(msg, ToolCallPart):
                        tool_name = "tool"
                        if msg.arguments_part:
                            try:
                                import json
                                args = json.loads(msg.arguments_part)
                                tool_name = args.get("name", "tool")
                            except Exception:
                                pass
                        print(f"[{ts}] [TOOL PART] {tool_name} | {msg.arguments_part}")
                        await _update_status(f"🔧 {tool_name}")
                    
                    # Tool result
                    elif isinstance(msg, ToolResult):
                        rv = msg.return_value
                        output_preview = str(rv.output)[:500] if hasattr(rv, 'output') else ""
                        print(f"[{ts}] [TOOL RESULT] {msg.tool_call_id} is_error={rv.is_error} output={output_preview}")
                        # Show result status briefly
                        status = "❌ ошибка" if rv.is_error else "✅ ок"
                        await _update_status(f"📤 результат: {status}")
                    
                    # Step begin
                    elif hasattr(msg, 'n') and msg_type == 'StepBegin':
                        step_num = msg.n
                        print(f"[{ts}] [STEP BEGIN] {msg.n}")
                        await _update_status(f"━━━ 🔄 Шаг {msg.n} ━━━")
                    
                    # Compaction
                    elif msg_type == 'CompactionBegin':
                        print(f"[{ts}] [COMPACTION] begin")
                        await _update_status("🗜 Сжатие контекста...")
                    
                    elif msg_type == 'CompactionEnd':
                        print(f"[{ts}] [COMPACTION] end")
                    
                    # Subagent event
                    elif isinstance(msg, SubagentEvent):
                        print(f"[{ts}] [SUBAGENT] type={msg.subagent_type} agent_id={msg.agent_id}")
                        await _update_status(f"👤 Под-агент {msg.subagent_type or '...'}")
                    
                    # Notifications (errors, warnings)
                    elif isinstance(msg, Notification):
                        print(f"[{ts}] [NOTIFY] {msg.severity}: {msg.title} | {msg.body}")
                        if msg.severity in ('error', 'critical'):
                            await _update_status(f"⚠️ {msg.title}")
                    
                    # Plan display
                    elif hasattr(msg, 'content') and msg_type == 'PlanDisplay':
                        print(f"[{ts}] [PLAN] {msg.content[:1000]}")
                    
                    # Turn begin/end
                    elif msg_type == 'TurnBegin':
                        print(f"[{ts}] [TURN BEGIN]")
                    elif msg_type == 'TurnEnd':
                        print(f"[{ts}] [TURN END]")
                    
                    # Other events — log type name for discovery
                    else:
                        print(f"[{ts}] [EVENT] {msg_type}: {repr(msg)[:500]}")
                        
            except Exception as exc:
                print(f"[WIRE LOOP ERROR] {exc}")

        print(f"\n{'='*60}")
        print(f"[USER] {user_input}")
        print(f"{'='*60}")

        try:
            await run_soul(
                self._soul,
                user_input,
                ui_loop,
                cancel_event,
                runtime=self._runtime,
            )
        except RunCancelled:
            results.append("\n[Отменено пользователем]")
            await _update_status("🛑 Отменено")
        except Exception as exc:
            logger.exception("Telegram bot turn failed")
            results.append(f"\n[Ошибка: {exc}]")
            await _update_status(f"❌ Ошибка: {exc}")
        finally:
            self._cancel_event = None

        result_text = "".join(results)
        print(f"[DONE] Turn completed, result length: {len(result_text)} chars\n")
        return result_text

    async def start(self) -> None:
        logger.info("Starting Telegram bot")
        await self.dp.start_polling(self.bot)


def _extract_text(msg: WireMessage) -> str | None:
    if isinstance(msg, TextPart):
        return msg.text
    return None


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable")
        return

    allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
    allowed_users: set[int] | None = None
    if allowed_users_str:
        allowed_users = {int(u.strip()) for u in allowed_users_str.split(",") if u.strip()}

    bot = TelegramBot(token=token, allowed_users=allowed_users)
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
