from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import config

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            config.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=50,
        )
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[config.MONGODB_DB_NAME]
