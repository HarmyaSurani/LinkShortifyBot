"""Global middleware: force subscription, ban check, auth check.

Subscription results are cached with a short TTL so the bot does not call
Telegram's getChatMember on every single message from active users. Only
positive results are cached, so a user who just joined the channel is never
locked out waiting for the cache to expire.
"""
from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Dict, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import config
from app.db.database import db
from app.messages import (
    ADMIN_NOT_AUTHORIZED,
    BAN_MESSAGE,
    NOT_REGISTERED_MESSAGE,
    SUBSCRIBE_MESSAGE,
)

# user_id -> (is_subscribed, expiry_monotonic). Only True results are stored.
_sub_cache: Dict[int, Tuple[bool, float]] = {}
_SUB_CACHE_MAX = 10000


def _join_markup() -> InlineKeyboardMarkup:
    ch = config.CHANNEL_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{ch}")]]
    )


def _purge_expired(now: float) -> None:
    """Drop expired entries when the cache grows large (cheap amortized GC)."""
    if len(_sub_cache) < _SUB_CACHE_MAX:
        return
    for uid in [u for u, (_, exp) in _sub_cache.items() if exp <= now]:
        _sub_cache.pop(uid, None)


async def _is_subscribed(bot, user_id: int) -> bool:
    if not config.CHANNEL_USERNAME:
        return True

    now = time.monotonic()
    cached = _sub_cache.get(user_id)
    if cached and cached[1] > now:
        return cached[0]

    try:
        member = await bot.get_chat_member(
            chat_id=config.CHANNEL_USERNAME, user_id=user_id
        )
        subscribed = member.status in ("member", "administrator", "creator")
    except Exception:
        return True  # Don't block on API errors

    if subscribed:
        _purge_expired(now)
        _sub_cache[user_id] = (True, now + config.SUB_CACHE_TTL)
    return subscribed


def current_user(context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
    """Return the user document fetched by @require_registered for this update."""
    return context.user_data.get("_db_user")


def require_subscription(func):
    """Check ban status and channel membership before running handler."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return  # channel posts / service updates carry no user — ignore
        user_id = user.id

        banned, subscribed = await asyncio.gather(
            db.is_banned(user_id),
            _is_subscribed(context.bot, user_id),
        )

        if banned:
            await update.effective_message.reply_text(
                BAN_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
                parse_mode="HTML",
            )
            return

        if not subscribed:
            await update.effective_message.reply_text(
                SUBSCRIBE_MESSAGE,
                parse_mode="HTML",
                reply_markup=_join_markup(),
            )
            return

        return await func(update, context)

    return wrapper


def require_registered(func):
    """Ensure the user has a linked API key, and cache the doc for the handler."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None:
            return
        user = await db.get_user(update.effective_user.id)
        if not user or not user.get("api_key"):
            await update.effective_message.reply_text(
                NOT_REGISTERED_MESSAGE, parse_mode="HTML"
            )
            return
        # Stash so the handler doesn't re-query the same document.
        context.user_data["_db_user"] = user
        return await func(update, context)

    return wrapper


def require_admin(func):
    """Ensure the caller is in the ADMINS list."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None:
            return
        if not config.is_admin(update.effective_user.id):
            await update.effective_message.reply_text(
                ADMIN_NOT_AUTHORIZED, parse_mode="HTML"
            )
            return
        return await func(update, context)

    return wrapper
