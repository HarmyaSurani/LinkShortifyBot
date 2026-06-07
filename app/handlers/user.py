"""User-facing command handlers."""
from __future__ import annotations

import asyncio
from functools import wraps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

import app.messages as msg
from app.config import config
from app.db.database import db
from app.core.middleware import current_user, require_registered, require_subscription
from app.services.api_client import api_client
from app.utils.logger import log_api_link, log_new_user, report_error
from app.utils.processing import clear_processing, send_processing

REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["▶️ Start"],
        ["🆘 Help", "🔗 API", "📝 About"],
        ["💡 Features", "🪪 Account", "💰 Balance"],
        ["⚙️ Settings"],
        ["⬆️ Header", "⬇️ Footer"],
        ["🏷 Username", "🔖 Hashtag"],
        ["⛓️ Channel Link", "🏞 Banner Image"],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or update.message is None:
        return  # channel posts / service updates have no user to start
    args = context.args or []

    # Record the start exactly once — logs "New User" only on the very first /start,
    # regardless of whether they arrive via a plain /start or a deep-link API key.
    is_new = await db.register_user_start(user.id, user.first_name, user.username or "")
    if is_new:
        log_new_user(context.bot, user.id, user.username or "", user.first_name)

    if not args:
        await update.message.reply_text(
            msg.START_MESSAGE.format(first_name=user.first_name),
            parse_mode="HTML",
            reply_markup=REPLY_KEYBOARD,
        )
        return

    api_key = args[0]
    pmsg = await update.message.reply_text(msg.PROCESSING_MESSAGE)

    # Run ban check and API call concurrently
    banned, data_result = await asyncio.gather(
        db.is_banned(user.id),
        api_client.get_user_data(api_key),
        return_exceptions=True,
    )

    if banned is True:
        await pmsg.delete()
        await update.message.reply_text(
            msg.BAN_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )
        return

    if isinstance(data_result, Exception) or data_result.get("status") != "success":
        await pmsg.delete()
        await update.message.reply_text(msg.API_INVALID_MESSAGE, parse_mode="HTML")
        return

    clash = await db.get_user_by_api(api_key)
    if clash and clash["telegram_id"] != user.id:
        await pmsg.delete()
        await update.message.reply_text(
            msg.API_ALREADY_LINKED_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )
        return

    await db.upsert_user(
        telegram_id=user.id,
        api_key=api_key,
        email=data_result.get("email", ""),
        site_username=data_result.get("username", ""),
        first_name=user.first_name,
        username=user.username or "",
    )
    await pmsg.delete()
    await update.message.reply_text(
        msg.WELCOME_API_MESSAGE.format(api_key=api_key),
        parse_mode="HTML",
        reply_markup=REPLY_KEYBOARD,
    )
    log_api_link(
        context.bot, user.id, user.username or "", user.first_name, api_key
    )


# ── /help  /about  /features ──────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        msg.HELP_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        msg.ABOUT_MESSAGE.format(
            version=config.BOT_VERSION, owner_contact=config.OWNER_CONTACT
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def cmd_features(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        msg.FEATURES_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ── /api ──────────────────────────────────────────────────────────────────────

async def cmd_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "🔗 Open Dashboard",
            url="https://linkshortify.com/member/dashboard",
        )]]
    )
    await update.effective_message.reply_text(
        msg.API_MESSAGE, parse_mode="HTML", reply_markup=keyboard
    )


# ── /logout ───────────────────────────────────────────────────────────────────

async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    # Disconnect the API account but KEEP the user record, so a later /start is
    # never mistaken for a brand-new user (which re-spammed the user log group).
    await db.logout_user(user.id)
    # Drop any cached state so a re-link starts clean.
    context.user_data.pop("_db_user", None)
    await update.effective_message.reply_text(msg.LOGOUT_MESSAGE, parse_mode="HTML")


# ── /account ──────────────────────────────────────────────────────────────────

@require_subscription
@require_registered
async def cmd_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await send_processing(update)
    try:
        usr = current_user(context)  # fetched by @require_registered — no re-query
        data = await api_client.get_user_data(usr["api_key"])
        full = data.get("full_info", {})
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔗 Share Referral",
                url=(
                    f"https://t.me/share/url"
                    f"?url=https://linkshortify.com/ref/{data.get('username', '')}"
                ),
            )
        ]])
        await clear_processing(user.id)
        await update.effective_message.reply_text(
            msg.ACCOUNT_MESSAGE.format(
                username=data.get("username", "N/A"),
                email=data.get("email", "N/A"),
                withdrawal_method=full.get("withdrawal_method", "None").upper(),
                withdrawal_account=full.get("withdrawal_account", "None"),
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        await clear_processing(user.id)
        report_error(
            context.bot, e, context_info="/account",
            user_id=user.id, username=user.username or "",
        )
        await update.effective_message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )


# ── /balance ──────────────────────────────────────────────────────────────────

@require_subscription
@require_registered
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await send_processing(update)
    try:
        usr = current_user(context)  # fetched by @require_registered — no re-query
        data = await api_client.get_user_data(usr["api_key"])
        full = data.get("full_info", {})
        stats_data = data.get("stats", {})
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "💸 Withdraw", url="https://linkshortify.com/member/withdraws"
            )
        ]])
        await clear_processing(user.id)
        await update.effective_message.reply_text(
            msg.BALANCE_MESSAGE.format(
                username=data.get("username", "N/A"),
                publisher_earnings=float(full.get("publisher_earnings", 0)),
                referral_earnings=float(full.get("referral_earnings", 0)),
                available_balance=stats_data.get("available_balance", "N/A"),
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        await clear_processing(user.id)
        report_error(
            context.bot, e, context_info="/balance",
            user_id=user.id, username=user.username or "",
        )
        await update.effective_message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )


# ── /settings ─────────────────────────────────────────────────────────────────

# Only these keys may be toggled via callback data (prevents arbitrary writes
# to settings.* through a hand-crafted callback query).
_TOGGLEABLE = frozenset({
    "header_enabled",
    "footer_enabled",
    "username_enabled",
    "channel_enabled",
    "hashtag_enabled",
    "banner_enabled",
})


def _settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    def label(key: str, name: str) -> str:
        on = settings.get(key, False)
        return f"{'❌ Disable' if on else '✅ Enable'} {name}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(label("header_enabled", "Header"), callback_data="toggle_header_enabled"),
            InlineKeyboardButton(label("footer_enabled", "Footer"), callback_data="toggle_footer_enabled"),
        ],
        [
            InlineKeyboardButton(label("username_enabled", "Username"), callback_data="toggle_username_enabled"),
            InlineKeyboardButton(label("channel_enabled", "Channel Link"), callback_data="toggle_channel_enabled"),
        ],
        [
            InlineKeyboardButton(label("hashtag_enabled", "Hashtag"), callback_data="toggle_hashtag_enabled"),
            InlineKeyboardButton(label("banner_enabled", "Banner"), callback_data="toggle_banner_enabled"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="toggle_close")],
    ])


@require_subscription
@require_registered
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    usr = current_user(context)  # fetched by @require_registered — no re-query
    s = usr.get("settings", {})

    def disp(k: str) -> str:
        v = s.get(k)
        return f"<code>{v}</code>" if v else "—"

    await update.effective_message.reply_text(
        msg.SETTINGS_MESSAGE.format(
            api_key=usr.get("api_key", "N/A"),
            header_text=disp("header_text"),
            footer_text=disp("footer_text"),
            username_replace=disp("username_replace"),
            hashtag_replace=disp("hashtag_replace"),
            channel_link=disp("channel_link"),
            banner_image="✅ Set" if s.get("banner_image") else "—",
        ),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(s),
        disable_web_page_preview=True,
    )


@require_subscription
async def btn_settings_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "toggle_close":
        await query.delete_message()
        return

    setting_key = query.data.removeprefix("toggle_")
    if setting_key not in _TOGGLEABLE:
        await query.answer("Unknown setting.", show_alert=True)
        return

    settings = await db.toggle_setting(query.from_user.id, setting_key)
    if settings is None:
        await query.answer("Please link your API first.", show_alert=True)
        return

    try:
        await query.edit_message_reply_markup(reply_markup=_settings_keyboard(settings))
    except Exception:
        pass


# ── Customization commands ────────────────────────────────────────────────────
#
# Factory that generates /header, /footer, /username, /hashtag,
# /channel_link, and /banner_image from a single template.

def _make_setting_cmd(
    field: str,
    enabled_key: str,
    usage_msg: str,
    display_name: str,
    *,
    prefix: str = "",
    contains: str = "",
    multi_word: bool = False,
):
    @require_subscription
    @require_registered
    async def _handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        args = context.args or []
        em = update.effective_message

        if not args:
            await em.reply_text(usage_msg, parse_mode="HTML")
            return

        val = args[0]

        if val == "remove":
            await db.set_setting(user_id, field, "", enabled_key, False)
            await em.reply_text(msg.REMOVED_SUCCESS.format(item=display_name))
            return

        if prefix and not val.startswith(prefix):
            await em.reply_text(
                msg.MUST_START_WITH.format(item=display_name, prefix=prefix),
                parse_mode="HTML",
            )
            return

        if contains and contains not in val:
            await em.reply_text(
                msg.MUST_START_WITH.format(item=display_name, prefix=contains),
                parse_mode="HTML",
            )
            return

        value = " ".join(args) if multi_word else val
        await db.set_setting(user_id, field, value, enabled_key, True)
        await em.reply_text(msg.ADDED_SUCCESS.format(item=display_name))

    return _handler


cmd_header = _make_setting_cmd(
    "header_text", "header_enabled", msg.HEADER_USAGE_MESSAGE, "Header", multi_word=True
)
cmd_footer = _make_setting_cmd(
    "footer_text", "footer_enabled", msg.FOOTER_USAGE_MESSAGE, "Footer", multi_word=True
)
cmd_username = _make_setting_cmd(
    "username_replace", "username_enabled", msg.USERNAME_USAGE_MESSAGE, "Username", prefix="@"
)
cmd_hashtag = _make_setting_cmd(
    "hashtag_replace", "hashtag_enabled", msg.HASHTAG_USAGE_MESSAGE, "Hashtag", prefix="#"
)
cmd_channel_link = _make_setting_cmd(
    "channel_link", "channel_enabled", msg.CHANNEL_LINK_USAGE_MESSAGE, "Channel Link", contains="t.me"
)
cmd_banner_image = _make_setting_cmd(
    "banner_image", "banner_enabled", msg.BANNER_IMAGE_USAGE_MESSAGE, "Banner Image"
)
