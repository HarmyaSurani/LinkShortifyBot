"""User-facing command handlers."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

import messages as msg
from config import config
from db.database import db
from middleware import require_registered, require_subscription
from services.api_client import api_client
from utils.logger import log_error, log_new_user, log_user_action
from utils.processing import clear_processing, send_processing

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
    args = context.args or []

    existing = await db.get_user(user.id)
    if existing is None:
        await log_new_user(context.bot, user.id, user.username or "", user.first_name)

    if not args:
        await update.message.reply_text(
            msg.START_MESSAGE.format(first_name=user.first_name),
            parse_mode="HTML",
            reply_markup=REPLY_KEYBOARD,
        )
        return

    api_key = args[0]
    pmsg = await update.message.reply_text(msg.PROCESSING_MESSAGE)

    if await db.is_banned(user.id):
        await pmsg.delete()
        await update.message.reply_text(
            msg.BAN_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )
        return

    try:
        data = await api_client.get_user_data(api_key)
    except Exception:
        await pmsg.delete()
        await update.message.reply_text(msg.API_INVALID_MESSAGE, parse_mode="HTML")
        return

    if data.get("status") != "success":
        await pmsg.delete()
        await update.message.reply_text(msg.API_INVALID_MESSAGE, parse_mode="HTML")
        return

    # Enforce one API key → one account
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
        email=data.get("email", ""),
        site_username=data.get("username", ""),
        first_name=user.first_name,
        username=user.username or "",
    )
    await pmsg.delete()
    await update.message.reply_text(
        msg.WELCOME_API_MESSAGE.format(api_key=api_key),
        parse_mode="HTML",
        reply_markup=REPLY_KEYBOARD,
    )
    await log_user_action(
        context.bot, user.id, user.username or "", user.first_name, "Linked API"
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
    await db.delete_user(user.id)
    await update.effective_message.reply_text(msg.LOGOUT_MESSAGE, parse_mode="HTML")
    await log_user_action(
        context.bot, user.id, user.username or "", user.first_name, "Logout"
    )


# ── /account ──────────────────────────────────────────────────────────────────

@require_subscription
@require_registered
async def cmd_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await send_processing(update)
    try:
        usr = await db.get_user(user.id)
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
        await log_error(
            context.bot, user.id, user.username or "", user.first_name, "/account", e
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
        usr = await db.get_user(user.id)
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
        await log_error(
            context.bot, user.id, user.username or "", user.first_name, "/balance", e
        )
        await update.effective_message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT),
            parse_mode="HTML",
        )


# ── /settings ─────────────────────────────────────────────────────────────────

def _settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    def label(enabled_key: str, name: str) -> str:
        on = settings.get(enabled_key, False)
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
    user = update.effective_user
    usr = await db.get_user(user.id)
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

    user_id = query.from_user.id
    usr = await db.get_user(user_id)
    if not usr:
        await query.answer("Please link your API first.", show_alert=True)
        return

    setting_key = query.data.removeprefix("toggle_")
    await db.toggle_setting(user_id, setting_key)

    usr = await db.get_user(user_id)
    try:
        await query.edit_message_reply_markup(
            reply_markup=_settings_keyboard(usr.get("settings", {}))
        )
    except Exception:
        pass


# ── Customization commands ────────────────────────────────────────────────────

@require_subscription
@require_registered
async def cmd_header(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            msg.HEADER_USAGE_MESSAGE, parse_mode="HTML"
        )
        return
    if args[0] == "remove":
        await db.update_setting_value(user.id, "header_text", "")
        await db.update_setting_value(user.id, "header_enabled", False)
        await update.effective_message.reply_text(
            msg.REMOVED_SUCCESS.format(item="Header")
        )
        return
    await db.update_setting_value(user.id, "header_text", " ".join(args))
    await db.update_setting_value(user.id, "header_enabled", True)
    await update.effective_message.reply_text(msg.ADDED_SUCCESS.format(item="Header"))


@require_subscription
@require_registered
async def cmd_footer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            msg.FOOTER_USAGE_MESSAGE, parse_mode="HTML"
        )
        return
    if args[0] == "remove":
        await db.update_setting_value(user.id, "footer_text", "")
        await db.update_setting_value(user.id, "footer_enabled", False)
        await update.effective_message.reply_text(
            msg.REMOVED_SUCCESS.format(item="Footer")
        )
        return
    await db.update_setting_value(user.id, "footer_text", " ".join(args))
    await db.update_setting_value(user.id, "footer_enabled", True)
    await update.effective_message.reply_text(msg.ADDED_SUCCESS.format(item="Footer"))


@require_subscription
@require_registered
async def cmd_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            msg.USERNAME_USAGE_MESSAGE, parse_mode="HTML"
        )
        return
    if args[0] == "remove":
        await db.update_setting_value(user.id, "username_replace", "")
        await db.update_setting_value(user.id, "username_enabled", False)
        await update.effective_message.reply_text(
            msg.REMOVED_SUCCESS.format(item="Username")
        )
        return
    if not args[0].startswith("@"):
        await update.effective_message.reply_text(
            msg.MUST_START_WITH.format(item="Username", prefix="@"),
            parse_mode="HTML",
        )
        return
    await db.update_setting_value(user.id, "username_replace", args[0])
    await db.update_setting_value(user.id, "username_enabled", True)
    await update.effective_message.reply_text(
        msg.ADDED_SUCCESS.format(item="Username")
    )


@require_subscription
@require_registered
async def cmd_hashtag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            msg.HASHTAG_USAGE_MESSAGE, parse_mode="HTML"
        )
        return
    if args[0] == "remove":
        await db.update_setting_value(user.id, "hashtag_replace", "")
        await db.update_setting_value(user.id, "hashtag_enabled", False)
        await update.effective_message.reply_text(
            msg.REMOVED_SUCCESS.format(item="Hashtag")
        )
        return
    if not args[0].startswith("#"):
        await update.effective_message.reply_text(
            msg.MUST_START_WITH.format(item="Hashtag", prefix="#"),
            parse_mode="HTML",
        )
        return
    await db.update_setting_value(user.id, "hashtag_replace", args[0])
    await db.update_setting_value(user.id, "hashtag_enabled", True)
    await update.effective_message.reply_text(
        msg.ADDED_SUCCESS.format(item="Hashtag")
    )


@require_subscription
@require_registered
async def cmd_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            msg.CHANNEL_LINK_USAGE_MESSAGE, parse_mode="HTML"
        )
        return
    if args[0] == "remove":
        await db.update_setting_value(user.id, "channel_link", "")
        await db.update_setting_value(user.id, "channel_enabled", False)
        await update.effective_message.reply_text(
            msg.REMOVED_SUCCESS.format(item="Channel Link")
        )
        return
    if "t.me" not in args[0]:
        await update.effective_message.reply_text(
            msg.MUST_START_WITH.format(item="Channel Link", prefix="t.me"),
            parse_mode="HTML",
        )
        return
    await db.update_setting_value(user.id, "channel_link", args[0])
    await db.update_setting_value(user.id, "channel_enabled", True)
    await update.effective_message.reply_text(
        msg.ADDED_SUCCESS.format(item="Channel Link")
    )


@require_subscription
@require_registered
async def cmd_banner_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            msg.BANNER_IMAGE_USAGE_MESSAGE, parse_mode="HTML"
        )
        return
    if args[0] == "remove":
        await db.update_setting_value(user.id, "banner_image", "")
        await db.update_setting_value(user.id, "banner_enabled", False)
        await update.effective_message.reply_text(
            msg.REMOVED_SUCCESS.format(item="Banner Image")
        )
        return
    await db.update_setting_value(user.id, "banner_image", args[0])
    await db.update_setting_value(user.id, "banner_enabled", True)
    await update.effective_message.reply_text(
        msg.ADDED_SUCCESS.format(item="Banner Image")
    )
