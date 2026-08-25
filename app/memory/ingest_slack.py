"""Chat archiver — ingestion job feeding shared org memory.

Reads messages from one designated Slack channel
(SLACK_SHARED_KNOWLEDGE_CHANNEL_ID) and writes them into shared memory
via the write-gated scoped key. This is the only path allowed to write
to org_shared besides other future ingestion jobs (e.g. codebase
indexer) — a person's private /update never lands here.
"""
from __future__ import annotations

from app.config import settings
from app.memory import shared


def handle_channel_message(channel_id: str, user_id: str, text: str, permalink: str = "") -> str | None:
    """Ingest one Slack message if it came from the shared-knowledge channel.

    Returns the new shared-memory id, or None if the message was
    outside the configured channel (ignored, not an error).
    """
    if not text.strip():
        return None
    if channel_id != settings.slack_shared_knowledge_channel_id:
        return None

    content = f"{text}"
    return shared.ingest(
        content=content,
        source="slack_chat_archiver",
        metadata={"slack_user_id": user_id, "slack_channel_id": channel_id, "permalink": permalink},
    )
