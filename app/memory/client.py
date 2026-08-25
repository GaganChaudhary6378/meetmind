"""Thin Supermemory client wrapper. One place that touches the SDK.

Keeps supermemory.Supermemory usage out of the private/shared modules
so a provider swap later only touches this file.
"""
from __future__ import annotations

from functools import lru_cache

from supermemory import Supermemory

from app.config import settings


@lru_cache(maxsize=1)
def get_client(api_key: str | None = None) -> Supermemory:
    """Return a cached Supermemory client.

    Pass api_key explicitly to use a scoped key (e.g. the shared-memory
    write-gated ingestion key). Defaults to the general private-memory key.
    """
    key = api_key or settings.supermemory_api_key
    return Supermemory(api_key=key, base_url=settings.supermemory_base_url)
