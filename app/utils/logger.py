"""Centralized logging to the terminal, a rotating file, and Telegram channels.

Design rules
------------
* Every dynamic value is HTML-escaped before being sent with parse_mode=HTML.
  (Unescaped tracebacks contain `<module>`, `<`, `>`, `&` and make Telegram
  reject the message with BadRequest — the historical cause of "missing" logs.)
* Telegram sends are fire-and-forget but retried, and the task reference is
  retained so it is never garbage-collected mid-flight.
* Errors are ALWAYS written to the terminal + file first, so a Telegram outage
  can never make an error disappear.
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut

from app.config import config
from app.core.metrics import metrics

log = logging.getLogger("linkshortify.events")

# Retain references to in-flight send tasks so they are not GC'd (CPython gotcha).
_tasks: set[asyncio.Task] = set()


# ── helpers ───────────────────────────────────────────────────────────────────

def _esc(value: object) -> str:
    return html.escape(str(value))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _mask_key(key: str) -> str:
    """Mask an API key for logs: keep enough to identify, hide the secret."""
    if not key:
        return "—"
    if len(key) <= 10:
        return key[:2] + "…"
    return f"{key[:6]}…{key[-4:]}"


def _source_of(exc: BaseException) -> str:
    """Return 'file.py:line' of the deepest frame in the traceback."""
    tb = exc.__traceback__
    last = None
    while tb is not None:
        last = tb
        tb = tb.tb_next
    if last is None:
        return "?"
    frame = last.tb_frame
    return f"{os.path.basename(frame.f_code.co_filename)}:{last.tb_lineno}"


async def _send_with_retry(chat_id: str, text: str, bot: Bot, retries: int = 3) -> bool:
    """Send to a Telegram chat with retry. Returns True on success."""
    if not chat_id:
        return False
    text = text[:4096]
    for attempt in range(1, retries + 1):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return True
        except RetryAfter as exc:
            await asyncio.sleep(getattr(exc, "retry_after", 1) + 0.5)
        except (TimedOut, NetworkError) as exc:
            log.warning("Telegram log transient failure (chat %s): %s", chat_id, exc)
            await asyncio.sleep(min(2 ** attempt, 8))
        except BadRequest as exc:
            # Formatting/permission problem — retrying won't help. Record + stop.
            log.error("Telegram log rejected (chat %s): %s", chat_id, exc)
            return False
        except Exception as exc:  # noqa: BLE001 - logging must never raise
            log.error("Telegram log send error (chat %s): %s", chat_id, exc)
            await asyncio.sleep(min(2 ** attempt, 8))
    log.error("Telegram log giving up after %d attempts (chat %s)", retries, chat_id)
    return False


def _fire(chat_id: str, text: str, bot: Bot) -> None:
    """Schedule a retried send without blocking the caller."""
    if not chat_id:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (rare sync context) — local logging already captured it.
        return
    task = loop.create_task(_send_with_retry(chat_id, text, bot))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


# ── USER log group ──────────────────────────────────────────────────────────
# Only three events are logged here: new user, API link, link conversion.

def log_new_user(bot: Bot, user_id: int, username: str, first_name: str) -> None:
    _fire(
        config.USER_LOG_GROUP,
        (
            "🆕 <b>New User Joined</b>\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"👤 <b>Name:</b> {_esc(first_name)}\n"
            f"🔗 <b>Username:</b> @{_esc(username or 'N/A')}\n"
            f"🕐 <b>Join Date:</b> {_ts()}"
        ),
        bot,
    )


def log_api_link(
    bot: Bot, user_id: int, username: str, first_name: str, api_key: str
) -> None:
    _fire(
        config.USER_LOG_GROUP,
        (
            "🔑 <b>API Linked</b>\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"👤 <b>Name:</b> {_esc(first_name)}\n"
            f"🔗 <b>Username:</b> @{_esc(username or 'N/A')}\n"
            f"🗝 <b>API Key:</b> <code>{_esc(_mask_key(api_key))}</code>\n"
            f"🕐 {_ts()}"
        ),
        bot,
    )


# Telegram caps a message at 4096 chars; leave headroom for the surrounding fields.
_MAX_LOGGED_MESSAGE = 3500


def log_link_conversion(
    bot: Bot,
    user_id: int,
    username: str,
    api_key: str,
    link_type: str,
    count: int,
    original_text: str = "",
) -> None:
    body = (original_text or "").strip()
    if len(body) > _MAX_LOGGED_MESSAGE:
        body = body[:_MAX_LOGGED_MESSAGE] + " …(truncated)"
    body = _esc(body) if body else "—"
    _fire(
        config.USER_LOG_GROUP,
        (
            "🔁 <b>Link Conversion</b>\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🔗 <b>Username:</b> @{_esc(username or 'N/A')}\n"
            f"🗝 <b>API Key:</b> <code>{_esc(_mask_key(api_key))}</code>\n"
            f"🏷 <b>Type:</b> {_esc(link_type)}\n"
            f"🔢 <b>Links Converted:</b> {count}\n"
            f"📥 <b>Message:</b>\n{body}\n"
            f"🕐 {_ts()}"
        ),
        bot,
    )


# ── ADMIN log group ───────────────────────────────────────────────────────────

def log_admin_action(
    bot: Bot, admin_id: int, username: str, action: str, target: str = ""
) -> None:
    _fire(
        config.ADMIN_LOG_GROUP,
        (
            "🛡️ <b>Admin Action</b>\n"
            f"🆔 <b>Admin:</b> <code>{admin_id}</code> (@{_esc(username or 'N/A')})\n"
            f"⚡ <b>Action:</b> {_esc(action)}\n"
            f"🎯 <b>Details:</b> {_esc(target) if target else '—'}\n"
            f"🕐 {_ts()}"
        ),
        bot,
    )


# ── ERROR log group ───────────────────────────────────────────────────────────

def report_error(
    bot: Bot,
    exc: BaseException,
    *,
    context_info: str = "",
    user_id: Optional[int] = None,
    username: Optional[str] = None,
) -> None:
    """Single funnel for every error: terminal + file + Telegram (escaped, retried)."""
    # 1) Always record locally with the full stack trace.
    metrics.inc_error()
    log.error(
        "Error in %s (user=%s @%s): %s",
        context_info or "?",
        user_id,
        username,
        exc,
        exc_info=exc,
    )

    # 2) Build an escaped Telegram message (trace tail keeps the relevant frames).
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    user_line = (
        f"🆔 <b>User:</b> <code>{user_id}</code> (@{_esc(username or 'N/A')})\n"
        if user_id is not None
        else ""
    )
    text = (
        f"🔴 <b>Error</b> [{_esc(config.ENVIRONMENT)}]\n"
        f"📍 <b>Where:</b> <code>{_esc(context_info or '?')}</code>\n"
        f"📄 <b>Source:</b> <code>{_esc(_source_of(exc))}</code>\n"
        f"{user_line}"
        f"⚠️ <code>{_esc(type(exc).__name__)}: {_esc(exc)}</code>\n"
        f"🕐 {_ts()}\n\n"
        f"<pre>{_esc(tb[-3200:])}</pre>"
    )
    _fire(config.ERROR_LOG_GROUP, text, bot)
