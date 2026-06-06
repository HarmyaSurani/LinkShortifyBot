"""Database abstraction layer — all MongoDB operations live here.

No MongoDB logic should appear in handlers or services.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from db import get_db

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
        await self._db.bans.create_index("telegram_id", unique=True)
        await self._db.broadcasts.create_index("timestamp")

    # ── users ─────────────────────────────────────────────────────────────────

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        return await self._db.users.find_one({"telegram_id": telegram_id})

    async def get_user_by_api(self, api_key: str) -> Optional[Dict]:
        return await self._db.users.find_one({"api_key": api_key})

    async def upsert_user(
        self,
        telegram_id: int,
        api_key: str,
        email: str,
        site_username: str,
        first_name: str = "",
        username: str = "",
    ) -> None:
        now = datetime.utcnow()
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
            {"$set": {f"settings.{key}": value, "updated_at": datetime.utcnow()}},
        )

    async def toggle_setting(self, telegram_id: int, key: str) -> bool:
        user = await self.get_user(telegram_id)
        if not user:
            return False
        current = user.get("settings", {}).get(key, False)
        new_val = not current
        await self.update_setting_value(telegram_id, key, new_val)
        return new_val

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
                    "created_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

    async def unban_user(self, telegram_id: int) -> None:
        await self._db.bans.delete_one({"telegram_id": telegram_id})

    async def is_banned(self, telegram_id: int) -> bool:
        doc = await self._db.bans.find_one(
            {"telegram_id": telegram_id}, {"_id": 1}
        )
        return doc is not None

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
                "timestamp": datetime.utcnow(),
            }
        )

    async def count_broadcasts(self) -> int:
        return await self._db.broadcasts.count_documents({})

    # ── stats ─────────────────────────────────────────────────────────────────

    async def inc_links_shortened(self, count: int = 1) -> None:
        await self._db.stats.update_one(
            {"_id": "global"},
            {"$inc": {"total_links_shortened": count}},
            upsert=True,
        )

    async def inc_messages_processed(self) -> None:
        await self._db.stats.update_one(
            {"_id": "global"},
            {"$inc": {"total_messages_processed": 1}},
            upsert=True,
        )

    async def get_stats(self) -> Dict:
        doc = await self._db.stats.find_one({"_id": "global"}) or {}
        return {
            "total_users": await self.count_users(),
            "total_bans": await self.count_bans(),
            "total_links_shortened": doc.get("total_links_shortened", 0),
            "total_messages_processed": doc.get("total_messages_processed", 0),
            "total_broadcasts": await self.count_broadcasts(),
        }

    # ── health ────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            await self._db.command("ping")
            return True
        except Exception:
            return False


db = Database()
