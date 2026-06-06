"""Text and media message handlers."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import app.messages as msg
from app.config import config
from app.db.database import db
from app.handlers.user import (
    REPLY_KEYBOARD,
    cmd_about,
    cmd_api,
    cmd_balance,
    cmd_banner_image,
    cmd_channel_link,
    cmd_features,
    cmd_footer,
    cmd_hashtag,
    cmd_header,
    cmd_help,
    cmd_settings,
    cmd_start,
    cmd_username,
    cmd_account,
)
from app.core.metrics import metrics
from app.core.middleware import require_subscription
from app.services.api_client import get_http
from app.services.shortener import process_message
from app.utils.logger import log_link_conversion, report_error
from app.utils.processing import clear_processing, send_processing

# Maps keyboard button labels to their handler functions
_BUTTON_MAP = {
    "▶️ Start": cmd_start,
    "🆘 Help": cmd_help,
    "📝 About": cmd_about,
    "🔗 API": cmd_api,
    "💡 Features": cmd_features,
    "🪪 Account": cmd_account,
    "💰 Balance": cmd_balance,
    "⚙️ Settings": cmd_settings,
    "⬆️ Header": cmd_header,
    "⬇️ Footer": cmd_footer,
    "🏷 Username": cmd_username,
    "🔖 Hashtag": cmd_hashtag,
    "⛓️ Channel Link": cmd_channel_link,
    "🏞 Banner Image": cmd_banner_image,
}


async def _fetch_image(url: str) -> bytes | None:
    try:
        resp = await get_http().get(url)
        ct = resp.headers.get("content-type", "")
        if resp.status_code == 200 and "image/" in ct:
            return resp.content
    except Exception:
        pass
    return None


async def _reply_with_banner(message, caption: str, banner: str) -> bool:
    """Reply with a banner photo. Tries the stored value (file_id or URL)
    directly — Telegram fetches it, no proxy download — and only falls back to
    downloading bytes if that fails. Returns True if a photo was sent."""
    try:
        await message.reply_photo(photo=banner, caption=caption, parse_mode=ParseMode.HTML)
        return True
    except Exception:
        img = await _fetch_image(banner)
        if img:
            await message.reply_photo(photo=img, caption=caption, parse_mode=ParseMode.HTML)
            return True
    return False


def _log_conversion(context, user, api_key, result) -> None:
    """Record a link conversion to metrics + the user log group (only if links were converted)."""
    if result.count <= 0:
        return
    metrics.inc_links(result.count)
    log_link_conversion(
        context.bot,
        user.id,
        user.username or "",
        api_key,
        result.link_type,
        result.count,
        result.conversions,
    )


@require_subscription
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text.strip()

    # Keyboard button dispatch — no API key required for informational commands
    if text in _BUTTON_MAP:
        await _BUTTON_MAP[text](update, context)
        return

    # Everything below requires a registered account
    usr = await db.get_user(user.id)
    if not usr or not usr.get("api_key"):
        await update.message.reply_text(msg.NOT_REGISTERED_MESSAGE, parse_mode="HTML")
        return

    # "set_image" reply sets a banner from a replied-to photo.
    # Store the file_id (permanent, reusable) — not file_path, which expires ~1h.
    if (
        update.message.reply_to_message
        and text == "set_image"
        and update.message.reply_to_message.photo
    ):
        file_id = update.message.reply_to_message.photo[-1].file_id
        await db.set_setting(user.id, "banner_image", file_id, "banner_enabled", True)
        await update.message.reply_text(msg.BANNER_SET_SUCCESS)
        return

    await send_processing(update)
    try:
        settings = usr.get("settings", {})
        result = await process_message(
            update.message.text_html_urled, usr["api_key"], settings
        )
        await clear_processing(user.id)

        banner = (
            settings.get("banner_image")
            if settings.get("banner_enabled") and settings.get("banner_image")
            else None
        )
        if not (banner and await _reply_with_banner(update.message, result.text, banner)):
            await update.message.reply_html(result.text)

        _log_conversion(context, user, usr["api_key"], result)
        await db.record_processing(messages=1, links=result.count)
    except Exception as e:
        await clear_processing(user.id)
        report_error(
            context.bot, e, context_info="handle_text",
            user_id=user.id, username=user.username or "",
        )
        await update.message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )


@require_subscription
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    usr = await db.get_user(user.id)
    if not usr or not usr.get("api_key"):
        await update.message.reply_text(msg.NOT_REGISTERED_MESSAGE, parse_mode="HTML")
        return

    await send_processing(update)
    try:
        settings = usr.get("settings", {})
        caption_html = update.message.caption_html_urled or ""
        result = await process_message(caption_html, usr["api_key"], settings)

        # Resend by file_id (no download/reupload). If a banner is set, use it;
        # Telegram fetches the banner URL/file_id directly.
        original_id = update.message.photo[-1].file_id
        banner = (
            settings.get("banner_image")
            if settings.get("banner_enabled") and settings.get("banner_image")
            else None
        )
        photo_arg = banner or original_id

        await clear_processing(user.id)
        try:
            await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=photo_arg,
                caption=result.text,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            # Banner unusable (bad URL etc.) — fall back to the original photo.
            await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=original_id,
                caption=result.text,
                parse_mode=ParseMode.HTML,
            )

        _log_conversion(context, user, usr["api_key"], result)
        await db.record_processing(messages=1, links=result.count)
    except Exception as e:
        await clear_processing(user.id)
        report_error(
            context.bot, e, context_info="handle_photo",
            user_id=user.id, username=user.username or "",
        )
        await update.message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )
