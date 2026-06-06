"""URL shortening and post-processing pipeline."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app.db.database import db
from app.services.api_client import api_client
from app.utils.html_parser import extract_alias_links, extract_links, is_alias_format
from app.utils.text_filters import (
    apply_footer,
    apply_header,
    replace_channel_links,
    replace_hashtags,
    replace_usernames,
)


@dataclass
class ProcessResult:
    """Outcome of processing one message through the pipeline."""

    text: str
    link_type: str = "none"  # none | standard | alias
    conversions: List[Tuple[str, str]] = field(default_factory=list)  # (original, short)

    @property
    def count(self) -> int:
        return len(self.conversions)


async def process_message(html_text: str, api_key: str, settings: Dict) -> ProcessResult:
    """Full pipeline: shorten links then apply all active user settings."""
    if is_alias_format(html_text):
        result = await _process_alias(html_text, api_key)
    else:
        skip_tg = settings.get("channel_enabled", False)
        result = await _process_standard(html_text, api_key, skip_tg)

    text = result.text
    if settings.get("username_enabled"):
        text = replace_usernames(text, settings.get("username_replace", ""))
    if settings.get("hashtag_enabled"):
        text = replace_hashtags(text, settings.get("hashtag_replace", ""))
    if settings.get("channel_enabled"):
        text = replace_channel_links(text, settings.get("channel_link", ""))
    if settings.get("header_enabled"):
        text = apply_header(text, settings.get("header_text", ""))
    if settings.get("footer_enabled"):
        text = apply_footer(text, settings.get("footer_text", ""))

    result.text = text
    return result


async def _process_standard(
    html_text: str, api_key: str, skip_tg: bool = False
) -> ProcessResult:
    links = extract_links(html_text)
    if not links:
        return ProcessResult(text=html_text, link_type="none")

    kept = [
        (href, label)
        for href, label in links
        if not (skip_tg and href.startswith("https://t.me"))
    ]
    if not kept:
        return ProcessResult(text=html_text, link_type="none")

    shortened_results = await asyncio.gather(
        *[api_client.shorten(href, api_key) for href, _ in kept]
    )

    conversions: List[Tuple[str, str]] = []
    result = html_text
    for (href, label), short in zip(kept, shortened_results):
        if not short:
            continue
        conversions.append((href, short))
        result = result.replace(href, short, 1)
        if label == href:
            result = result.replace(label, short, 1)

    if conversions:
        await db.inc_links_shortened(len(conversions))

    return ProcessResult(text=result, link_type="standard", conversions=conversions)


async def _process_alias(html_text: str, api_key: str) -> ProcessResult:
    links = [
        item
        for item in extract_alias_links(html_text)
        if not item.get("url", "").startswith("https://t.me")
    ]
    if not links:
        return ProcessResult(text="", link_type="alias")

    async def _shorten_one(item: dict) -> str:
        url = item.get("url", "")
        alias = item.get("alias", "")
        short = (
            await api_client.shorten_with_alias(url, api_key, alias)
            if alias
            else await api_client.shorten(url, api_key)
        )
        return short or url

    results = await asyncio.gather(*[_shorten_one(item) for item in links])

    conversions: List[Tuple[str, str]] = [
        (item.get("url", ""), res)
        for item, res in zip(links, results)
        if res != item.get("url", "")
    ]
    if conversions:
        await db.inc_links_shortened(len(conversions))

    return ProcessResult(
        text="\n".join(results), link_type="alias", conversions=conversions
    )
