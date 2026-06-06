"""Database abstraction layer — all MongoDB operations live here.

No MongoDB logic should appear in handlers or services.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.config import config
from app.db import get_db

log = logging.getLogger("linkshortify.db")

# telegram_id -> (is_banned, expiry_monotonic). Avoids a DB query per message.
_ban_cache: Dict[int, Tuple[bool, float]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "header_text": "",
    "footer_text": "",
    "username_replace": "",
    "hashtag_replace": "",
    "channel_link": "",
    "banner_image": "",
    "header_enabled": False,
    "footer_enabled": False,
    "username_enabled": False,
    "hashtag_enabled": False,
    "channel_enabled": False,
    "banner_enabled": False,
}


class Database:
    @property
    def _db(self) -> AsyncIOMotorDatabase:
        return get_db()

    # ── indexes ───────────────────────────────────────────────────────────────

    async def ensure_indexes(self) -> None:
        await self._db.users.create_index("telegram_id", unique=True)
        await self._db.users.create_index("api_key", unique=True, sparse=True)
        await self._db.users.create_index("created_at")  # analytics / new-user queries
        await self._db.bans.create_index("telegram_id", unique=True)
        await self._db.broadcasts.create_index("timestamp")

    # ── users ─────────────────────────────────────────────────────────────────

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        return await self._db.users.find_one({"telegram_id": telegram_id})

    async def get_user_by_api(self, api_key: str) -> Optional[Dict]:
        return await self._db.users.find_one({"api_key": api_key})

    async def register_user_start(
        self, telegram_id: int, first_name: str = "", username: str = ""
    ) -> bool:
        """Record that a user has started the bot.

        Creates a user document on first contact (independent of API linking) so
        the 'new user' event is logged exactly once, ever. Returns True only when
        this call inserted a brand-new document.
        """
        now = _now()
        try:
            result = await self._db.users.update_one(
                {"telegram_id": telegram_id},
                {
                    "$set": {
                        "first_name": first_name,
                        "username": username,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "telegram_id": telegram_id,
                        "settings": dict(_DEFAULT_SETTINGS),
                        "created_at": now,
                    },
                },
                upsert=True,
            )
        except DuplicateKeyError:
            # Concurrent first /start from the same user — the other call won.
            return False
        return result.upserted_id is not None

    async def upsert_user(
        self,
        telegram_id: int,
        api_key: str,
        email: str,
        site_username: str,
        first_name: str = "",
        username: str = "",
    ) -> None:
        now = _now()
        await self._db.users.update_one(
            {"telegram_id": telegram_id},
            {
                "$set": {
                    "api_key": api_key,
                    "email": email,
                    "site_username": site_username,
                    "first_name": first_name,
                    "username": username,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "telegram_id": telegram_id,
                    "settings": dict(_DEFAULT_SETTINGS),
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def delete_user(self, telegram_id: int) -> None:
        await self._db.users.delete_one({"telegram_id": telegram_id})

    async def delete_user_by_api(self, api_key: str) -> None:
        await self._db.users.delete_one({"api_key": api_key})

    async def update_setting_value(
        self, telegram_id: int, key: str, value: Any
    ) -> None:
        await self._db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {f"settings.{key}": value, "updated_at": _now()}},
        )

    async def toggle_setting(self, telegram_id: int, key: str) -> Optional[Dict[str, Any]]:
        """Toggle a boolean setting. Returns the full settings dict, or None if user not found."""
        result = await self._db.users.find_one_and_update(
            {"telegram_id": telegram_id},
            [{"$set": {
                f"settings.{key}": {"$not": [f"$settings.{key}"]},
                "updated_at": "$$NOW",
            }}],
            return_document=ReturnDocument.AFTER,
            projection={"settings": 1},
        )
        if not result:
            return None
        return result.get("settings", {})

    async def set_setting(
        self, telegram_id: int, field: str, value: Any, enabled_key: str, enabled: bool
    ) -> None:
        """Set a setting value and its enabled flag in a single DB write."""
        await self._db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {
                f"settings.{field}": value,
                f"settings.{enabled_key}": enabled,
                "updated_at": _now(),
            }},
        )

    async def get_all_user_ids(self) -> List[int]:
        cursor = self._db.users.find({}, {"telegram_id": 1, "_id": 0})
        docs = await cursor.to_list(length=None)
        return [d["telegram_id"] for d in docs]

    async def count_users(self) -> int:
        return await self._db.users.count_documents({})

    # ── bans ──────────────────────────────────────────────────────────────────

    async def ban_user(
        self, telegram_id: int, reason: str, banned_by: int
    ) -> None:
        await self._db.bans.update_one(
            {"telegram_id": telegram_id},
            {
                "$set": {
                    "telegram_id": telegram_id,
                    "reason": reason,
                    "banned_by": banned_by,
                    "created_at": _now(),
                }
            },
            upsert=True,
        )
        _ban_cache[telegram_id] = (True, time.monotonic() + config.BAN_CACHE_TTL)

    async def unban_user(self, telegram_id: int) -> None:
        await self._db.bans.delete_one({"telegram_id": telegram_id})
        _ban_cache[telegram_id] = (False, time.monotonic() + config.BAN_CACHE_TTL)

    async def is_banned(self, telegram_id: int) -> bool:
        now = time.monotonic()
        cached = _ban_cache.get(telegram_id)
        if cached and cached[1] > now:
            return cached[0]
        doc = await self._db.bans.find_one(
            {"telegram_id": telegram_id}, {"_id": 1}
        )
        banned = doc is not None
        _ban_cache[telegram_id] = (banned, now + config.BAN_CACHE_TTL)
        return banned

    async def get_ban(self, telegram_id: int) -> Optional[Dict]:
        return await self._db.bans.find_one({"telegram_id": telegram_id})

    async def count_bans(self) -> int:
        return await self._db.bans.count_documents({})

    # ── broadcasts ────────────────────────────────────────────────────────────

    async def log_broadcast(
        self, initiated_by: int, success: int, failed: int
    ) -> None:
        await self._db.broadcasts.insert_one(
            {
                "initiated_by": initiated_by,
                "success_count": success,
                "failed_count": failed,
                "timestamp": _now(),
            }
        )

    async def count_broadcasts(self) -> int:
        return await self._db.broadcasts.count_documents({})

    # ── stats ─────────────────────────────────────────────────────────────────

    async def record_processing(self, messages: int = 0, links: int = 0) -> None:
        """Best-effort combined stats write (one round trip). Never raises.

        Called after the user already has their reply, so a transient failure
        only loses a counter — it can't affect the response.
        """
        inc: Dict[str, int] = {}
        if messages:
            inc["total_messages_processed"] = messages
        if links:
            inc["total_links_shortened"] = links
        if not inc:
            return
        try:
            await self._db.stats.update_one(
                {"_id": "global"}, {"$inc": inc}, upsert=True
            )
        except Exception as exc:  # noqa: BLE001 - stats are non-critical
            log.warning("record_processing failed: %s", exc)

    async def get_stats(self) -> Dict:
        doc, users, bans, broadcasts = await asyncio.gather(
            self._db.stats.find_one({"_id": "global"}),
            self._db.users.count_documents({}),
            self._db.bans.count_documents({}),
            self._db.broadcasts.count_documents({}),
        )
        doc = doc or {}
        return {
            "total_users": users,
            "total_bans": bans,
            "total_links_shortened": doc.get("total_links_shortened", 0),
            "total_messages_processed": doc.get("total_messages_processed", 0),
            "total_broadcasts": broadcasts,
        }

    # ── health ────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            await self._db.command("ping")
            return True
        except Exception:
            return False


db = Database()
