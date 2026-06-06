"""Regex-based text transformation utilities."""
from __future__ import annotations

import re

_TG_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/"
    r"(?:\+[\w-]+|[\w-]+(?:/[\w-]+)?)",
    re.IGNORECASE,
)
_USERNAME_RE = re.compile(r"@\w+")
_HASHTAG_RE = re.compile(r"#\w+")


def replace_usernames(text: str, replacement: str) -> str:
    if not replacement:
        return text
    return _USERNAME_RE.sub(replacement, text)


def replace_hashtags(text: str, replacement: str) -> str:
    if not replacement:
        return text
    return _HASHTAG_RE.sub(replacement, text)


def replace_channel_links(text: str, replacement: str) -> str:
    if not replacement:
        return text
    return _TG_LINK_RE.sub(replacement, text)


def apply_header(text: str, header: str) -> str:
    return f"{header}\n{text}" if header else text


def apply_footer(text: str, footer: str) -> str:
    return f"{text}\n{footer}" if footer else text
