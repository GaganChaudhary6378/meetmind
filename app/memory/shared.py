"""Shared org memory — task 1.3.

One Supermemory container tag (`org_shared`, see settings). Read access
is open to every agent. Write access is gated: only ingestion jobs
(codebase indexer, chat archiver) may write here, and they must use the
scoped write key (`SUPERMEMORY_SHARED_WRITE_API_KEY`), not the general
private-memory key. A person's private update never lands here.
"""
from __future__ import annotations

from app.config import settings
from app.memory.client import get_client


def query(question: str, limit: int = 5):
    """Read-only search over shared org memory. Any agent may call this."""
    client = get_client()
    return client.search.execute(
        q=question,
        container_tags=[settings.shared_container_tag],
        limit=limit,
        include_full_docs=True,
    )


def ingest(content: str, source: str, metadata: dict | None = None) -> str:
    """Write to shared memory. Ingestion jobs only.

    Requires the scoped shared-write key to be configured. Raises if it
    is missing, so a misconfigured deploy fails loudly instead of
    silently writing with an over-privileged key.
    """
    if not settings.supermemory_shared_write_api_key:
        raise RuntimeError(
            "SUPERMEMORY_SHARED_WRITE_API_KEY not set — refusing to write "
            "to shared memory with an unscoped key."
        )
    client = get_client(api_key=settings.supermemory_shared_write_api_key)
    result = client.add(
        content=content,
        container_tag=settings.shared_container_tag,
        metadata={**(metadata or {}), "source": source},
    )
    return result.id
