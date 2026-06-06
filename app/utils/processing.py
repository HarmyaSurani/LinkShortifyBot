"""One-active-processing-message-per-user manager.

Ensures users never see multiple ⏳ messages when sending bursts.
All state is in-process memory (per bot instance).
"""
from __future__ import annotations

from typing import Dict, Optional

from telegram import Message, Update

from app.config import config
from app.messages import PROCESSING_MESSAGE

# telegram_id → active processing Message
_active: Dict[int, Message] = {}


async def send_processing(update: Update) -> Optional[Message]:
    """Send a processing message, deleting any previous one for this user."""
    if not config.PROCESSING_MESSAGE_ENABLED:
        return None

    user_id = update.effective_user.id
    await clear_processing(user_id)

    sent = await update.effective_message.reply_text(PROCESSING_MESSAGE)
    _active[user_id] = sent
    return sent


async def clear_processing(user_id: int) -> None:
    """Delete and forget the active processing message for this user."""
    msg = _active.pop(user_id, None)
    if msg:
        try:
            await msg.delete()
        except Exception:
            pass
