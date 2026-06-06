from __future__ import annotations

import os
import sys
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        print(f"[FATAL] Required env var '{key}' is not set.", file=sys.stderr)
        sys.exit(1)
    return val


def _int_list(key: str) -> List[int]:
    raw = os.getenv(key, "")
    result = []
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.append(int(part))
    return result


class _Config:
    BOT_TOKEN: str = _require("BOT_TOKEN")

    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "linkshortify")

    LINKSHORTIFY_API_URL: str = os.getenv(
        "LINKSHORTIFY_API_URL", "https://linkshortify.com/api"
    )
    LINKSHORTIFY_STATS_URL: str = os.getenv(
        "LINKSHORTIFY_STATS_URL", "https://linkshortify.com/stats"
    )

    CHANNEL_USERNAME: str = os.getenv("CHANNEL_USERNAME", "")

    ADMINS: List[int] = _int_list("ADMINS")

    USER_LOG_GROUP: str = os.getenv("USER_LOG_GROUP", "")
    ERROR_LOG_GROUP: str = os.getenv("ERROR_LOG_GROUP", "")
    ADMIN_LOG_GROUP: str = os.getenv("ADMIN_LOG_GROUP", "")

    PROCESSING_MESSAGE_ENABLED: bool = (
        os.getenv("PROCESSING_MESSAGE_ENABLED", "true").lower() == "true"
    )
    BROADCAST_BATCH_SIZE: int = int(os.getenv("BROADCAST_BATCH_SIZE", "25"))

    OWNER_CONTACT: str = os.getenv("OWNER_CONTACT", "@LinkShortifySupport")

    BOT_VERSION: str = "2.0.0"

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.ADMINS


config = _Config()
