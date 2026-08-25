"""Parse Slack @mentions out of slash-command text.

Slack expands a typed `@name` inside slash-command text into
`<@U0RAHUL|rahul>` (or `<@U0RAHUL>` with no label, depending on client)
before it reaches the bot. These helpers pull the raw user_id back out
so commands can accept `@person` instead of a raw user_id.
"""
from __future__ import annotations

import re

_MENTION_RE = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")


def extract_mention(text: str) -> tuple[str | None, str]:
    """Return (first mentioned user_id or None, text with that mention removed)."""
    match = _MENTION_RE.search(text)
    if not match:
        return None, text
    remainder = (text[: match.start()] + text[match.end() :]).strip()
    return match.group(1), remainder


def extract_all_mentions(text: str) -> tuple[list[str], str]:
    """Return (all mentioned user_ids, text with every mention removed)."""
    user_ids = _MENTION_RE.findall(text)
    remainder = _MENTION_RE.sub("", text).strip()
    return user_ids, remainder
