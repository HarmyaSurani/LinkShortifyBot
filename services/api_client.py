"""LinkShortify HTTP API client."""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from config import config

_TIMEOUT = httpx.Timeout(15.0)


class LinkShortifyClient:
    async def _get(self, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_user_data(self, api_key: str) -> Dict[str, Any]:
        return await self._get(config.LINKSHORTIFY_STATS_URL, {"api": api_key})

    async def shorten(self, url: str, api_key: str) -> Optional[str]:
        try:
            data = await self._get(
                config.LINKSHORTIFY_API_URL, {"api": api_key, "url": url}
            )
            if data.get("status") == "success":
                return data.get("shortenedUrl")
        except Exception:
            pass
        return None

    async def shorten_with_alias(
        self, url: str, api_key: str, alias: str
    ) -> Optional[str]:
        clean = url.removeprefix("https://").removeprefix("http://")
        try:
            data = await self._get(
                config.LINKSHORTIFY_API_URL,
                {"api": api_key, "url": clean, "alias": alias},
            )
            if data.get("status") == "success":
                return data.get("shortenedUrl")
        except Exception:
            pass
        return None


api_client = LinkShortifyClient()
