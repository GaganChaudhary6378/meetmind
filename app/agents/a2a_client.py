"""A2A client — task 2.1.

Calls a teammate's PersonAgent A2A server and returns their reply as
plain text. Used by the facilitator agent (task 2.2/2.3) — it never
touches another person's private memory directly, only through their
own agent's A2A endpoint.
"""
from __future__ import annotations

import uuid

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart


async def request_status_update(base_url: str, question: str | None = None) -> str:
    """Send a status-update request to the PersonAgent at `base_url`.

    `question` defaults to the executor's own status-update prompt when
    omitted (see `PersonAgentExecutor.STATUS_UPDATE_PROMPT`).
    """
    async with httpx.AsyncClient(timeout=30.0) as httpx_client:
        resolver = A2ACardResolver(httpx_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()
        client = A2AClient(httpx_client, agent_card=agent_card)

        message = Message(
            role=Role.user,
            message_id=str(uuid.uuid4()),
            parts=[Part(root=TextPart(text=question or ""))],
        )
        request = SendMessageRequest(
            id=str(uuid.uuid4()), params=MessageSendParams(message=message)
        )
        response = await client.send_message(request)
        return _extract_text(response)


def _extract_text(response) -> str:
    result = response.root.result
    parts = getattr(result, "parts", None) or []
    texts = []
    for part in parts:
        root = getattr(part, "root", part)
        text = getattr(root, "text", None)
        if text:
            texts.append(text)
    return "\n".join(texts) if texts else "(no reply)"
