"""A2A wiring test — task 2.1/2.2/2.3.

Runs two real PersonAgent A2A servers locally (own thread, ephemeral
port each) and drives the facilitator against them over real HTTP —
proves the A2A transport, not just the in-process call contract.
PersonAgent.answer() is monkeypatched so this test needs no live
Supermemory/LLM credentials; it is checking A2A wiring, not memory
retrieval (that is `test_isolation.py`'s job).
"""
from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest
import uvicorn

from app.agents import facilitator_agent
from app.agents.a2a_server import build_app
from app.agents.person_agent import PersonAgent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _run_agent_server(user_id: str, port: int):
    config = uvicorn.Config(build_app(user_id, port).build(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_facilitator_collects_updates_over_real_a2a():
    alice_port, bob_port = _free_port(), _free_port()
    roster = {
        "alice": f"http://127.0.0.1:{alice_port}",
        "bob": f"http://127.0.0.1:{bob_port}",
    }

    with (
        patch.object(PersonAgent, "answer", lambda self, q: f"{self.user_id} says: shipped the thing"),
        _run_agent_server("alice", alice_port),
        _run_agent_server("bob", bob_port),
    ):
        updates = await facilitator_agent.collect_updates(roster, absent={"bob"})

    assert "alice says: shipped the thing" in updates["alice"]
    assert "bob says: shipped the thing" in updates["bob"]
    assert facilitator_agent._ABSENT_NOTE in updates["bob"]
    assert facilitator_agent._ABSENT_NOTE not in updates["alice"]


@pytest.mark.asyncio
async def test_facilitator_survives_one_unreachable_teammate():
    alice_port = _free_port()
    unreachable_port = _free_port()  # nothing listening here
    roster = {
        "alice": f"http://127.0.0.1:{alice_port}",
        "ghost": f"http://127.0.0.1:{unreachable_port}",
    }

    with (
        patch.object(PersonAgent, "answer", lambda self, q: "all good here"),
        _run_agent_server("alice", alice_port),
    ):
        updates = await facilitator_agent.collect_updates(roster)

    assert "all good here" in updates["alice"]
    assert "could not reach" in updates["ghost"]
