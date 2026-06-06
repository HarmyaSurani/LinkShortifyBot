"""LinkShortify Bot — application setup and lifecycle."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from app.config import config
from app.core.logging import setup_logging
from app.db.database import db
from app.handlers import register_handlers
from app.utils.logger import report_error

setup_logging()
log = logging.getLogger(__name__)

_application: Optional[Application] = None


def _loop_exception_handler(loop, ctx: dict) -> None:
    """Catch stray exceptions from background tasks (otherwise only warned)."""
    exc = ctx.get("exception")
    if exc and _application is not None:
        report_error(_application.bot, exc, context_info="event-loop")
    else:
        log.error("Event loop error: %s", ctx.get("message"))


async def _post_init(application: Application) -> None:
    global _application
    _application = application
    application.bot_data["start_time"] = datetime.now(timezone.utc)
    asyncio.get_running_loop().set_exception_handler(_loop_exception_handler)
    await db.ensure_indexes()
    log.info("MongoDB indexes ensured.")
    log.info("Bot v%s started in %s mode.", config.BOT_VERSION, config.ENVIRONMENT)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Single funnel for every uncaught handler exception."""
    user_id = None
    username = None
    if isinstance(update, Update) and update.effective_user:
        user_id = update.effective_user.id
        username = update.effective_user.username
    report_error(
        context.bot,
        context.error,
        context_info="global-handler",
        user_id=user_id,
        username=username,
    )


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .post_init(_post_init)
        .concurrent_updates(True)
        .build()
    )

    app.add_error_handler(_error_handler)
    register_handlers(app)

    log.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)
