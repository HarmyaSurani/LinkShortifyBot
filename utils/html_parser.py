"""HTML link extraction utilities."""
from __future__ import annotations

from typing import Dict, List, Tuple

from lxml import html


def extract_links(html_content: str) -> List[Tuple[str, str]]:
    """Return (href, label) pairs for every anchor tag in html_content."""
    if not html_content or "<a " not in html_content:
        return []
    try:
        tree = html.fromstring(html_content)
        result: List[Tuple[str, str]] = []
        for node in tree.xpath("//a"):
            href = (node.get("href") or "").strip()
            label = (node.text_content() or "").strip()
            if href and label:
                result.append((href, label))
        return result
    except Exception:
        return []


def extract_alias_links(html_content: str) -> List[Dict[str, str]]:
    """
    Parse lines of the form: <a href="URL">LABEL</a> | alias

    Returns a list of dicts: {url, label, alias}.
    """
    if not html_content:
        return []
    try:
        tree = html.fromstring(html_content)
        a_tags = tree.xpath("//a")
        # All text nodes split on "|" give us the alternating url-text / alias pairs
        all_text = tree.text_content()
        text_parts = [t.strip() for t in all_text.split("|")]
        results = []
        for i, tag in enumerate(a_tags):
            url = (tag.get("href") or "").strip()
            label = tag.text_content().strip()
            alias_idx = i * 2 + 1
            alias = (
                text_parts[alias_idx].replace(" ", "")
                if alias_idx < len(text_parts)
                else ""
            )
            if url:
                results.append({"url": url, "label": label, "alias": alias})
        return results
    except Exception:
        return []


def is_alias_format(message: str) -> bool:
    """Return True if the first line looks like 'url | alias'."""
    first_line = message.split("\n")[0].strip()
    parts = first_line.split("|")
    return len(parts) == 2 and all(p.strip() for p in parts)
