"""Global middleware: force subscription, ban check, auth check."""
from __future__ import annotations

from functools import wraps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import config
from db.database import db
from messages import ADMIN_NOT_AUTHORIZED, BAN_MESSAGE, NOT_REGISTERED_MESSAGE, SUBSCRIBE_MESSAGE


def _join_markup() -> InlineKeyboardMarkup:
    ch = config.CHANNEL_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{ch}")]]
    )


async def _is_subscribed(bot, user_id: int) -> bool:
    if not config.CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(
            chat_id=config.CHANNEL_USERNAME, user_id=user_id
        )
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return True  # Don't block on API errors


def require_subscription(func):
    """Check ban status and channel membership before running handler."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if await db.is_banned(user_id):
            await update.effective_message.reply_text(
                BAN_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
                parse_mode="HTML",
            )
            return

        if not await _is_subscribed(context.bot, user_id):
            await update.effective_message.reply_text(
                SUBSCRIBE_MESSAGE,
                parse_mode="HTML",
                reply_markup=_join_markup(),
            )
            return

        return await func(update, context)

    return wrapper


def require_registered(func):
    """Ensure the user has a linked API key."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await db.get_user(update.effective_user.id)
        if not user or not user.get("api_key"):
            await update.effective_message.reply_text(
                NOT_REGISTERED_MESSAGE, parse_mode="HTML"
            )
            return
        return await func(update, context)

    return wrapper


def require_admin(func):
    """Ensure the caller is in the ADMINS list."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not config.is_admin(update.effective_user.id):
            await update.effective_message.reply_text(
                ADMIN_NOT_AUTHORIZED, parse_mode="HTML"
            )
            return
        return await func(update, context)

    return wrapper
