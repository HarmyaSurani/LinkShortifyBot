"""Handler registration — wires every command/message/callback to the app."""
from __future__ import annotations

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from app.core.metrics import metrics

# Import order: user first (message depends on it) to keep imports clean.
from app.handlers import user, admin, message


async def _count_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lightweight metrics tap (group -1) — never blocks other handlers."""
    metrics.inc_update()
    message_ = update.effective_message
    if message_ and message_.text and message_.text.startswith("/"):
        metrics.inc_command()


def register_handlers(app: Application) -> None:
    """Register all bot handlers on the given Application."""

    # ── Metrics tap (runs first, in its own group so it never stops others) ──
    app.add_handler(TypeHandler(Update, _count_update), group=-1)

    # ── User commands ──────────────────────────────────────────────────────
    user_commands = {
        "start": user.cmd_start,
        "help": user.cmd_help,
        "about": user.cmd_about,
        "features": user.cmd_features,
        "api": user.cmd_api,
        "logout": user.cmd_logout,
        "account": user.cmd_account,
        "balance": user.cmd_balance,
        "settings": user.cmd_settings,
        "header": user.cmd_header,
        "footer": user.cmd_footer,
        "username": user.cmd_username,
        "hashtag": user.cmd_hashtag,
        "channel_link": user.cmd_channel_link,
        "banner_image": user.cmd_banner_image,
    }
    for name, handler in user_commands.items():
        app.add_handler(CommandHandler(name, handler))

    # ── Admin commands ─────────────────────────────────────────────────────
    admin_commands = {
        "ban": admin.cmd_ban,
        "unban": admin.cmd_unban,
        "broadcast": admin.cmd_broadcast,
        "status": admin.cmd_status,
    }
    for name, handler in admin_commands.items():
        app.add_handler(CommandHandler(name, handler))

    # ── Inline keyboard callbacks ──────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(user.btn_settings_toggle, pattern=r"^toggle_"))

    # ── Message handlers ───────────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message.handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, message.handle_photo))
