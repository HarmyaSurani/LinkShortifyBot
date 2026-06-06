"""LinkShortify Bot — entry point."""
from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import config
from db.database import db
from handlers import admin, message, user
from handlers.user import btn_settings_toggle

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("motor").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


async def _post_init(application) -> None:
    application.bot_data["start_time"] = datetime.utcnow()
    await db.ensure_indexes()
    log.info("MongoDB indexes ensured.")
    log.info("Bot v%s started.", config.BOT_VERSION)


async def _error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    log.error("Unhandled exception", exc_info=context.error)
    if not config.ERROR_LOG_GROUP:
        return
    tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    try:
        await context.bot.send_message(
            chat_id=config.ERROR_LOG_GROUP,
            text=f"🔴 <b>Unhandled Error</b>\n<pre>{tb[:3800]}</pre>",
            parse_mode="HTML",
        )
    except Exception:
        pass


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    app.add_error_handler(_error_handler)

    # ── User commands ────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", user.cmd_start))
    app.add_handler(CommandHandler("help", user.cmd_help))
    app.add_handler(CommandHandler("about", user.cmd_about))
    app.add_handler(CommandHandler("features", user.cmd_features))
    app.add_handler(CommandHandler("api", user.cmd_api))
    app.add_handler(CommandHandler("logout", user.cmd_logout))
    app.add_handler(CommandHandler("account", user.cmd_account))
    app.add_handler(CommandHandler("balance", user.cmd_balance))
    app.add_handler(CommandHandler("settings", user.cmd_settings))
    app.add_handler(CommandHandler("header", user.cmd_header))
    app.add_handler(CommandHandler("footer", user.cmd_footer))
    app.add_handler(CommandHandler("username", user.cmd_username))
    app.add_handler(CommandHandler("hashtag", user.cmd_hashtag))
    app.add_handler(CommandHandler("channel_link", user.cmd_channel_link))
    app.add_handler(CommandHandler("banner_image", user.cmd_banner_image))

    # ── Admin commands ───────────────────────────────────────────────────────
    app.add_handler(CommandHandler("ban", admin.cmd_ban))
    app.add_handler(CommandHandler("unban", admin.cmd_unban))
    app.add_handler(CommandHandler("broadcast", admin.cmd_broadcast))
    app.add_handler(CommandHandler("status", admin.cmd_status))

    # ── Inline keyboard callbacks ────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(btn_settings_toggle, pattern=r"^toggle_"))

    # ── Message handlers ─────────────────────────────────────────────────────
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message.handle_text)
    )
    app.add_handler(
        MessageHandler(filters.PHOTO & filters.CAPTION, message.handle_photo)
    )

    log.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
