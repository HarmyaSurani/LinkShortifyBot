"""Text and media message handlers."""
from __future__ import annotations

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import messages as msg
from config import config
from db.database import db
from handlers.user import (
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
from middleware import require_subscription
from services.shortener import process_message
from utils.logger import log_error, log_user_action
from utils.processing import clear_processing, send_processing

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
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
        ct = resp.headers.get("content-type", "")
        if resp.status_code == 200 and "image/" in ct:
            return resp.content
    except Exception:
        pass
    return None


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

    # "set_image" reply sets a banner from a replied-to photo
    if (
        update.message.reply_to_message
        and text == "set_image"
        and update.message.reply_to_message.photo
    ):
        photo = await update.message.reply_to_message.photo[-1].get_file()
        await db.update_setting_value(user.id, "banner_image", photo.file_path)
        await db.update_setting_value(user.id, "banner_enabled", True)
        await update.message.reply_text(msg.BANNER_SET_SUCCESS)
        return

    await send_processing(update)
    try:
        settings = usr.get("settings", {})
        processed = await process_message(
            update.message.text_html_urled, usr["api_key"], settings
        )
        await db.inc_messages_processed()
        await clear_processing(user.id)

        if settings.get("banner_enabled") and settings.get("banner_image"):
            img = await _fetch_image(settings["banner_image"])
            if img:
                await update.message.reply_photo(
                    photo=img, caption=processed, parse_mode=ParseMode.HTML
                )
                return
        await update.message.reply_html(processed)

        await log_user_action(
            context.bot,
            user.id,
            user.username or "",
            user.first_name,
            "Processed text",
            text[:100],
        )
    except Exception as e:
        await clear_processing(user.id)
        await log_error(
            context.bot, user.id, user.username or "", user.first_name,
            "handle_text", e,
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
        processed_caption = await process_message(
            caption_html, usr["api_key"], settings
        )
        await db.inc_messages_processed()

        photo_file = await update.message.photo[-1].get_file()
        img_url = (
            settings.get("banner_image")
            if settings.get("banner_enabled") and settings.get("banner_image")
            else photo_file.file_path
        )
        img = await _fetch_image(img_url)
        if img is None:
            img = await _fetch_image(photo_file.file_path)

        await clear_processing(user.id)
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=img,
            caption=processed_caption,
            parse_mode=ParseMode.HTML,
        )
        await log_user_action(
            context.bot,
            user.id,
            user.username or "",
            user.first_name,
            "Processed photo",
        )
    except Exception as e:
        await clear_processing(user.id)
        await log_error(
            context.bot, user.id, user.username or "", user.first_name,
            "handle_photo", e,
        )
        await update.message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )
