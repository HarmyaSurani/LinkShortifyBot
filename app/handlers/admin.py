"""Admin-only command handlers."""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

import psutil
from telegram import Update
from telegram.error import Forbidden
from telegram.ext import ContextTypes

import app.messages as msg
from app.config import config
from app.core.metrics import metrics
from app.core.middleware import require_admin
from app.db.database import db
from app.utils.logger import log_admin_action, report_error


def _summarize(message) -> str:
    """Short human summary of a message being broadcast."""
    text = message.text or message.caption
    if text:
        return text[:80].replace("\n", " ")
    if message.photo:
        return "[photo]"
    if message.video:
        return "[video]"
    if message.document:
        return "[document]"
    return "[media]"


@require_admin
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin = update.effective_user
    args = context.args or []
    if not args:
        await update.message.reply_text(msg.ADMIN_BAN_USAGE, parse_mode="HTML")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.", parse_mode="HTML")
        return

    reason = " ".join(args[1:]) or "No reason provided"
    try:
        await db.ban_user(target_id, reason, admin.id)
    except Exception as e:
        report_error(context.bot, e, context_info="/ban", user_id=admin.id,
                     username=admin.username or "")
        await update.message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT), parse_mode="HTML"
        )
        return

    await update.message.reply_text(
        msg.ADMIN_BAN_SUCCESS.format(user_id=target_id, reason=reason),
        parse_mode="HTML",
    )
    log_admin_action(
        context.bot, admin.id, admin.username or "", "Ban",
        f"user_id={target_id}, reason={reason}",
    )
    # Notify the banned user (best-effort)
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=msg.BANNED_NOTIFICATION_MESSAGE.format(
                reason=reason, owner_contact=config.OWNER_CONTACT
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


@require_admin
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin = update.effective_user
    args = context.args or []
    if not args:
        await update.message.reply_text(msg.ADMIN_UNBAN_USAGE, parse_mode="HTML")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.", parse_mode="HTML")
        return

    try:
        await db.unban_user(target_id)
    except Exception as e:
        report_error(context.bot, e, context_info="/unban", user_id=admin.id,
                     username=admin.username or "")
        await update.message.reply_text(
            msg.ERROR_MESSAGE.format(owner_contact=config.OWNER_CONTACT), parse_mode="HTML"
        )
        return

    await update.message.reply_text(
        msg.ADMIN_UNBAN_SUCCESS.format(user_id=target_id), parse_mode="HTML"
    )
    log_admin_action(
        context.bot, admin.id, admin.username or "", "Unban", f"user_id={target_id}"
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=msg.UNBANNED_NOTIFICATION_MESSAGE,
            parse_mode="HTML",
        )
    except Exception:
        pass


@require_admin
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin = update.effective_user

    if not update.message.reply_to_message:
        await update.message.reply_text(msg.BROADCAST_USAGE, parse_mode="HTML")
        return

    source = update.message.reply_to_message
    summary = _summarize(source)
    user_ids = await db.get_all_user_ids()
    total = len(user_ids)
    success = failed = blocked = 0
    batch_size = config.BROADCAST_BATCH_SIZE
    started = time.monotonic()

    # Log broadcast start (admin group)
    log_admin_action(
        context.bot, admin.id, admin.username or "", "Broadcast started",
        f"total={total}, content={summary!r}",
    )

    status_msg = await update.message.reply_text(
        msg.BROADCAST_STARTED.format(total=total), parse_mode="HTML"
    )

    try:
        for i in range(0, total, batch_size):
            batch = user_ids[i : i + batch_size]
            to_send = [uid for uid in batch if uid != admin.id]
            success += len(batch) - len(to_send)  # admin id counted as delivered
            results = await asyncio.gather(
                *[source.copy(chat_id=uid) for uid in to_send],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Forbidden):
                    blocked += 1
                elif isinstance(r, Exception):
                    failed += 1
                else:
                    success += 1
            await asyncio.sleep(1)  # respect Telegram rate limits between batches
    except Exception as e:
        report_error(context.bot, e, context_info="/broadcast", user_id=admin.id,
                     username=admin.username or "")

    duration = round(time.monotonic() - started, 1)
    await db.log_broadcast(admin.id, success, failed + blocked)
    log_admin_action(
        context.bot, admin.id, admin.username or "", "Broadcast completed",
        f"total={total}, success={success}, failed={failed}, "
        f"blocked={blocked}, duration={duration}s",
    )
    report = msg.BROADCAST_REPORT.format(
        success=success, failed=failed, blocked=blocked, total=total, duration=duration
    )
    try:
        await status_msg.edit_text(report, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(report, parse_mode="HTML")


@require_admin
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin = update.effective_user
    now = datetime.now(timezone.utc)
    start_time: datetime = context.bot_data.get("start_time", now)
    delta = now - start_time
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)

    stats, mongo_ok = await asyncio.gather(db.get_stats(), db.ping())

    await update.message.reply_text(
        msg.STATUS_MESSAGE.format(
            total_users=stats["total_users"],
            total_bans=stats["total_bans"],
            total_links=stats["total_links_shortened"],
            total_messages=stats["total_messages_processed"],
            total_broadcasts=stats["total_broadcasts"],
            commands=metrics.commands,
            links_session=metrics.links_converted,
            errors_hour=metrics.errors_last_hour(),
            mongo_status="✅ Connected" if mongo_ok else "❌ Disconnected",
            uptime=uptime_str,
            python_version=sys.version.split()[0],
            bot_version=config.BOT_VERSION,
            memory_usage=f"{mem_mb:.1f} MB",
        ),
        parse_mode="HTML",
    )
    log_admin_action(context.bot, admin.id, admin.username or "", "Status")
