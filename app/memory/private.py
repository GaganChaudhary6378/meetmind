"""Private memory — task 1.1.

One Supermemory container tag per person (`user_<id>`). Only that
person's own agent reads or writes this tag. Isolation is enforced by
Supermemory itself: each container tag hashes to its own vector
namespace, so there is no shared index to leak across.
"""
from __future__ import annotations

from app.config import settings
from app.memory.client import get_client


def _tag(user_id: str) -> str:
    return f"user_{user_id}"


def add_update(user_id: str, text: str) -> str:
    """Write a raw "what I did today" entry to short-term memory.

    Returns the Supermemory memory id. The long-term summarize job
    (see app.memory.pipeline) later folds this into long-term storage.
    """
    client = get_client()
    result = client.add(
        content=text,
        container_tag=_tag(user_id),
        metadata={"kind": "daily_update", "tier": "short_term"},
    )
    return result.id


def query(user_id: str, question: str, limit: int = 5):
    """Search this person's private memory only.

    Returns Supermemory search results, each carrying a relevance
    score — callers use this for the confidence gate (task 3.4).
    """
    client = get_client()
    return client.search.execute(
        q=question,
        container_tags=[_tag(user_id)],
        limit=limit,
        include_full_docs=True,
    )
