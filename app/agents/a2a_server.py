"""A2A server — task 2.1.

Runs one PersonAgent as a standalone A2A server (agent card + JSON-RPC
endpoint). Each teammate gets their own process/port — this is what
makes the isolation in `app/memory/private.py` hold under A2A too: the
facilitator can only ever reach a person's agent through *their own*
server, which only ever queries *their own* container tag.

Dev/local usage — start one per teammate:
    python -m app.agents.a2a_server U0ALICE 9001
    python -m app.agents.a2a_server U0BOB   9002
Register the same "user_id:port" pairs in A2A_TEAM_ROSTER (.env) so the
facilitator agent (`facilitator_agent.py`) knows where to find them.
"""
from __future__ import annotations

import sys

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from app.agents.a2a_executor import PersonAgentExecutor
from app.config import settings


def build_agent_card(user_id: str, url: str) -> AgentCard:
    skill = AgentSkill(
        id="status_update",
        name="Give status update",
        description=(
            "Reports this person's status from their own private memory "
            "and shared org memory — never another person's."
        ),
        tags=["standup", "status-update"],
        examples=["What did I do this week?", "Give a status update."],
    )
    return AgentCard(
        name=f"PersonAgent:{user_id}",
        description=f"Personal meeting agent for Slack user {user_id}.",
        url=url,
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


def build_app(user_id: str, port: int) -> A2AStarletteApplication:
    url = f"http://{settings.a2a_agent_host}:{port}/"
    agent_card = build_agent_card(user_id, url)
    handler = DefaultRequestHandler(
        agent_executor=PersonAgentExecutor(user_id),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(agent_card=agent_card, http_handler=handler)


def run_agent_server(user_id: str, port: int) -> None:
    app = build_app(user_id, port).build()
    uvicorn.run(app, host=settings.a2a_agent_host, port=port)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m app.agents.a2a_server <user_id> <port>")
    run_agent_server(sys.argv[1], int(sys.argv[2]))
