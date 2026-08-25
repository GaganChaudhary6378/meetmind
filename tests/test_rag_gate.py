"""RagGate unit tests — tasks 3.3/3.4 core logic.

Plain and synchronous on purpose (see app/voice/rag_gate.py) — no
pipecat, no async, no audio/models. Replaces the old
tests/test_voice_pipeline.py now that the pipeline itself is pipecat's
async plumbing (app/voice/bot.py), exercised by hand instead of here.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.voice.rag_gate import RagGate


def _hits(score: float, content: str):
    return SimpleNamespace(results=[SimpleNamespace(score=score, content=content, chunks=None)])


def _empty_hits():
    return SimpleNamespace(results=[])


def test_above_threshold_returns_formatted_context():
    gate = RagGate()
    with patch("app.voice.rag_gate.shared.query", return_value=_hits(0.95, "decided to use REST")):
        result = gate.resolve("what did we decide on the API")

    assert result == "[shared] decided to use REST"


def test_below_threshold_returns_none():
    gate = RagGate()
    with patch("app.voice.rag_gate.shared.query", return_value=_hits(0.10, "unrelated fragment")):
        result = gate.resolve("what did we decide")

    assert result is None


def test_no_hits_does_not_short_circuit():
    gate = RagGate()
    with patch("app.voice.rag_gate.shared.query", return_value=_empty_hits()):
        result = gate.resolve("something never discussed")

    assert result == "(no relevant memory found)"
