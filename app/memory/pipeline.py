"""Short-term -> long-term memory pipeline — task 1.2.

Supermemory already handles chunking/embedding on write. This module
adds the plan's explicit two-tier step: summarize a person's recent
short_term entries into one long_term entry. Run this on a schedule
(cron / background job), not inline on every write.
"""
from __future__ import annotations

from app.llm.router import ask
from app.memory.client import get_client
from app.memory.private import _tag

SUMMARY_PROMPT = (
    "Summarize the following raw daily updates from one person into a "
    "concise long-term memory entry. Keep concrete facts (PRs, decisions, "
    "blockers). Drop filler.\n\nUpdates:\n{updates}"
)


def summarize_and_promote(user_id: str, updates: list[str]) -> str:
    """Summarize raw short-term updates and write them as one long_term entry.

    Returns the new memory id. Callers are responsible for deciding which
    short-term entries to include (e.g. "today's" or "this week's").
    """
    if not updates:
        raise ValueError("no updates to summarize")

    prompt = SUMMARY_PROMPT.format(updates="\n".join(f"- {u}" for u in updates))
    summary = ask(prompt, context="", tier="summary")

    client = get_client()
    result = client.add(
        content=summary,
        container_tag=_tag(user_id),
        metadata={"kind": "daily_summary", "tier": "long_term"},
    )
    return result.id
