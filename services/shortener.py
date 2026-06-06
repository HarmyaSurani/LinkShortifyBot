"""URL shortening and post-processing pipeline."""
from __future__ import annotations

from typing import Dict

from db.database import db
from services.api_client import api_client
from utils.html_parser import extract_alias_links, extract_links, is_alias_format
from utils.text_filters import (
    apply_footer,
    apply_header,
    replace_channel_links,
    replace_hashtags,
    replace_usernames,
)


async def process_message(html_text: str, api_key: str, settings: Dict) -> str:
    """Full pipeline: shorten links then apply all active user settings."""
    if is_alias_format(html_text):
        result = await _process_alias(html_text, api_key)
    else:
        skip_tg = settings.get("channel_enabled", False)
        result = await _process_standard(html_text, api_key, skip_tg)

    if settings.get("username_enabled"):
        result = replace_usernames(result, settings.get("username_replace", ""))
    if settings.get("hashtag_enabled"):
        result = replace_hashtags(result, settings.get("hashtag_replace", ""))
    if settings.get("channel_enabled"):
        result = replace_channel_links(result, settings.get("channel_link", ""))
    if settings.get("header_enabled"):
        result = apply_header(result, settings.get("header_text", ""))
    if settings.get("footer_enabled"):
        result = apply_footer(result, settings.get("footer_text", ""))

    return result


async def _process_standard(
    html_text: str, api_key: str, skip_tg: bool = False
) -> str:
    links = extract_links(html_text)
    if not links:
        return html_text

    replacements = []
    for href, label in links:
        if skip_tg and href.startswith("https://t.me"):
            continue
        shortened = await api_client.shorten(href, api_key)
        if shortened:
            replacements.append((href, label, shortened))

    result = html_text
    for href, label, shortened in replacements:
        result = result.replace(href, shortened, 1)
        if label == href:
            result = result.replace(label, shortened, 1)

    if replacements:
        await db.inc_links_shortened(len(replacements))

    return result


async def _process_alias(html_text: str, api_key: str) -> str:
    links = extract_alias_links(html_text)
    results = []
    count = 0

    for item in links:
        url = item.get("url", "")
        if url.startswith("https://t.me"):
            continue
        alias = item.get("alias", "")
        shortened = (
            await api_client.shorten_with_alias(url, api_key, alias)
            if alias
            else await api_client.shorten(url, api_key)
        )
        results.append(shortened or url)
        if shortened:
            count += 1

    if count:
        await db.inc_links_shortened(count)

    return "\n".join(results)
