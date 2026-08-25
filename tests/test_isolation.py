"""Cross-person leak test — task 1.6.

Proves agent A never answers from agent B's private memory. Run this
against a real (or sandboxed) Supermemory project before starting
phase 2 — it is the core privacy invariant the whole system depends on.
"""
from __future__ import annotations

from app.agents.person_agent import PersonAgent


def test_private_memory_does_not_leak_across_users():
    alice = PersonAgent("alice")
    bob = PersonAgent("bob")

    alice.record_update("I merged the auth-refactor PR and it broke staging.")

    # Bob asks about something only in Alice's private memory. Check for a
    # fact fragment ("broke staging") that only exists in Alice's private
    # memory — the question text itself repeats "auth-refactor", so that
    # word alone is not a valid leak signal (the model echoes it while
    # correctly saying it does not know).
    answer = bob.answer("What did I do with the auth-refactor PR?")

    assert "broke staging" not in answer.lower(), (
        "Bob's agent answered from Alice's private memory — isolation broken"
    )
