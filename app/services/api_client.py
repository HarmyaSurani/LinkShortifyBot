"""LinkShortify HTTP API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from app.config import config

log = logging.getLogger("linkshortify.api")

_TIMEOUT = httpx.Timeout(config.API_TIMEOUT)
_http: httpx.AsyncClient | None = None


def get_http() -> httpx.AsyncClient:
    """Shared persistent HTTP client — reuses TCP connections across requests."""
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _http


class LinkShortifyClient:
    async def _get(self, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        """GET with a configurable timeout and light retry on transient failures."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, config.API_RETRIES + 2):  # initial try + retries
            try:
                resp = await get_http().get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                log.warning("API transient error (attempt %d): %s", attempt, exc)
                await asyncio.sleep(min(0.5 * attempt, 3))
            except httpx.HTTPStatusError as exc:
                # 4xx/5xx — a 5xx is worth one retry, 4xx is not.
                last_exc = exc
                if exc.response.status_code < 500:
                    raise
                log.warning("API %s (attempt %d)", exc.response.status_code, attempt)
                await asyncio.sleep(min(0.5 * attempt, 3))
        assert last_exc is not None
        raise last_exc

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
