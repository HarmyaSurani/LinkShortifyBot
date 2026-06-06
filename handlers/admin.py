"""Admin-only command handlers."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

import psutil
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import messages as msg
from config import config
from db.database import db
from middleware import require_admin
from utils.logger import log_admin_action


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
    await db.ban_user(target_id, reason, admin.id)
    await update.message.reply_text(
        msg.ADMIN_BAN_SUCCESS.format(user_id=target_id, reason=reason),
        parse_mode="HTML",
    )
    await log_admin_action(
        context.bot,
        admin.id,
        admin.username or "",
        "Ban",
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

    await db.unban_user(target_id)
    await update.message.reply_text(
        msg.ADMIN_UNBAN_SUCCESS.format(user_id=target_id), parse_mode="HTML"
    )
    await log_admin_action(
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
    user_ids = await db.get_all_user_ids()
    total = len(user_ids)
    success = failed = 0
    batch_size = config.BROADCAST_BATCH_SIZE

    status_msg = await update.message.reply_text(
        f"📢 Broadcasting to {total} users...", parse_mode="HTML"
    )

    for i in range(0, total, batch_size):
        batch = user_ids[i : i + batch_size]
        for uid in batch:
            if uid == admin.id:
                success += 1
                continue
            try:
                await source.copy(chat_id=uid)
                success += 1
            except Exception:
                failed += 1
        await asyncio.sleep(1)  # respect Telegram rate limits between batches

    await db.log_broadcast(admin.id, success, failed)
    await log_admin_action(
        context.bot,
        admin.id,
        admin.username or "",
        "Broadcast",
        f"success={success}, failed={failed}, total={total}",
    )
    report = msg.BROADCAST_REPORT.format(
        success=success, failed=failed, total=total
    )
    try:
        await status_msg.edit_text(report, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(report, parse_mode="HTML")


@require_admin
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    start_time: datetime = context.bot_data.get("start_time", datetime.utcnow())
    delta = datetime.utcnow() - start_time
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)

    stats = await db.get_stats()
    mongo_ok = await db.ping()

    await update.message.reply_text(
        msg.STATUS_MESSAGE.format(
            total_users=stats["total_users"],
            total_bans=stats["total_bans"],
            total_links=stats["total_links_shortened"],
            total_messages=stats["total_messages_processed"],
            total_broadcasts=stats["total_broadcasts"],
            mongo_status="✅ Connected" if mongo_ok else "❌ Disconnected",
            uptime=uptime_str,
            python_version=sys.version.split()[0],
            bot_version=config.BOT_VERSION,
            memory_usage=f"{mem_mb:.1f} MB",
        ),
        parse_mode="HTML",
    )
