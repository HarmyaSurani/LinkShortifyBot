"""Telegram-channel logging helpers.

All log functions are fire-and-forget: they never raise.
"""
from __future__ import annotations

import traceback
from datetime import datetime

from telegram import Bot
from telegram.constants import ParseMode

from config import config


async def _send(bot: Bot, chat_id: str, text: str) -> None:
    if not chat_id:
        return
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text[:4096],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception:
        pass


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


async def log_new_user(
    bot: Bot, user_id: int, username: str, first_name: str
) -> None:
    await _send(
        bot,
        config.USER_LOG_GROUP,
        (
            f"🆕 <b>New User</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Name: {first_name}\n"
            f"🔗 Username: @{username or 'N/A'}\n"
            f"🕐 {_ts()}"
        ),
    )


async def log_user_action(
    bot: Bot,
    user_id: int,
    username: str,
    first_name: str,
    action: str,
    content: str = "",
) -> None:
    await _send(
        bot,
        config.USER_LOG_GROUP,
        (
            f"👤 <b>User Action</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Name: {first_name}\n"
            f"🔗 Username: @{username or 'N/A'}\n"
            f"⚡ Action: {action}\n"
            f"📝 Content: {content[:300] if content else '—'}\n"
            f"🕐 {_ts()}"
        ),
    )


async def log_error(
    bot: Bot,
    user_id: int,
    username: str,
    first_name: str,
    context_info: str,
    exc: Exception,
) -> None:
    tb = traceback.format_exc()
    await _send(
        bot,
        config.ERROR_LOG_GROUP,
        (
            f"🔴 <b>Error</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Name: {first_name}\n"
            f"🔗 Username: @{username or 'N/A'}\n"
            f"📍 Context: <code>{context_info}</code>\n"
            f"⚠️ <code>{type(exc).__name__}: {exc}</code>\n"
            f"🕐 {_ts()}\n\n"
            f"<pre>{tb[:2000]}</pre>"
        ),
    )


async def log_admin_action(
    bot: Bot,
    admin_id: int,
    username: str,
    action: str,
    target: str = "",
) -> None:
    await _send(
        bot,
        config.ADMIN_LOG_GROUP,
        (
            f"🛡️ <b>Admin Action</b>\n"
            f"🆔 Admin: <code>{admin_id}</code> (@{username or 'N/A'})\n"
            f"⚡ Action: {action}\n"
            f"🎯 Target: {target or '—'}\n"
            f"🕐 {_ts()}"
        ),
    )
