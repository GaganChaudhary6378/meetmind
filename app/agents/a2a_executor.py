"""A2A executor — task 2.1.

Wraps a PersonAgent so it can be reached over the A2A protocol. This is
the server-side seam: the facilitator agent's A2A client (see
`a2a_client.py`) sends a message here, this executor runs it against
the person's own private memory (never anyone else's), and publishes
the reply back as an A2A message.
"""
from __future__ import annotations

import asyncio

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from app.agents.person_agent import PersonAgent

STATUS_UPDATE_PROMPT = (
    "Give a short status update: what did I work on, and is anything "
    "blocked? Use only my own daily updates."
)


class PersonAgentExecutor(AgentExecutor):
    """Runs one person's PersonAgent behind an A2A server."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._agent = PersonAgent(user_id)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = context.get_user_input() or STATUS_UPDATE_PROMPT
        # PersonAgent.answer() is a blocking network call (Supermemory +
        # LLM router) — run it off the event loop so one slow teammate
        # doesn't stall every other A2A request this server is handling.
        answer = await asyncio.to_thread(self._agent.answer, question)
        await event_queue.enqueue_event(
            new_agent_text_message(answer, context_id=context.context_id, task_id=context.task_id)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Status-update calls are single-shot, nothing to cancel mid-flight.
        pass
