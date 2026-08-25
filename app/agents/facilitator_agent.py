"""Facilitator agent — tasks 2.2 and 2.3.

Runs the daily standup (DSM) in Slack on the Scrum Master's behalf.
Pulls each teammate's status update from their own PersonAgent via A2A
(never reads another person's private memory directly) and compiles
one summary. Absent teammates are pulled the same way as present ones
(task 2.3) — the facilitator doesn't need a human relay either way.
"""
from __future__ import annotations

import asyncio

from app.agents.a2a_client import request_status_update
from app.config import settings
from app.llm import router

_ABSENT_NOTE = "(absent from standup — update pulled via A2A)"


async def collect_updates(
    roster: dict[str, str] | None = None, absent: set[str] | None = None
) -> dict[str, str]:
    """Call every teammate's PersonAgent for their status update.

    `roster` defaults to `settings.a2a_roster()`. `absent` is a set of
    user_ids not present in the standup — task 2.3: their update is
    still pulled via A2A, just flagged in the returned text.
    """
    roster = roster if roster is not None else settings.a2a_roster()
    absent = absent or set()

    async def _one(user_id: str, base_url: str) -> tuple[str, str]:
        try:
            text = await request_status_update(base_url)
        except Exception as exc:  # noqa: BLE001 — one unreachable teammate shouldn't kill the standup
            return user_id, f"(could not reach {user_id}'s agent — {exc})"
        if user_id in absent:
            text = f"{text}\n{_ABSENT_NOTE}"
        return user_id, text

    results = await asyncio.gather(*(_one(uid, url) for uid, url in roster.items()))
    return dict(results)


def compile_standup_summary(updates: dict[str, str]) -> str:
    """Compile individual updates into one DSM summary.

    Routed to the cheap/small model tier (plan §3) — facilitator-summary
    calls are high-volume, not the live/high-stakes "answer" path.
    """
    if not updates:
        return "No teammates in the roster to pull updates from."
    context = "\n\n".join(f"[{user_id}]\n{text}" for user_id, text in updates.items())
    prompt = (
        "Compile these per-person status updates into one daily standup "
        "summary: what each person did, and call out anything blocked."
    )
    return router.ask(prompt, context, tier="summary")


def run_standup(roster: dict[str, str] | None = None, absent: set[str] | None = None) -> str:
    """Sync entry point for Slack command handlers (task 2.2)."""
    updates = asyncio.run(collect_updates(roster, absent))
    return compile_standup_summary(updates)
