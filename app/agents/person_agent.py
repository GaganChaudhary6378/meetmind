"""One PersonAgent per user. Combines that person's private memory,
read-only shared org memory, and the LLM router.

This is the seam A2A (phase 2) will call into — another agent's
facilitator asks *this* agent for a status update, never reaches into
another person's private memory directly.
"""
from __future__ import annotations

from app.config import settings
from app.llm import router
from app.memory import private, shared


class PersonAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def record_update(self, text: str) -> str:
        """Store a raw "what I did today" entry. Task 1.1/1.5 entry point."""
        return private.add_update(self.user_id, text)

    def answer(self, question: str) -> str:
        """Answer a question using this person's private memory plus
        shared org memory. Applies the confidence gate (task 3.4):
        below threshold, say so instead of guessing.
        """
        private_hits = private.query(self.user_id, question)
        shared_hits = shared.query(question)

        scores = [s for s in (_top_score(private_hits), _top_score(shared_hits)) if s is not None]
        top_score = max(scores) if scores else None
        if top_score is not None and top_score < settings.confidence_threshold:
            return "Not sure — best to ask them directly."

        context = _format_context(private_hits, shared_hits)
        return router.ask(question, context, tier="answer")


def _top_score(hits) -> float | None:
    results = getattr(hits, "results", None) or []
    if not results:
        return None
    return max(getattr(r, "score", 0.0) for r in results)


def _format_context(private_hits, shared_hits) -> str:
    lines: list[str] = []
    for label, hits in (("private", private_hits), ("shared", shared_hits)):
        for r in getattr(hits, "results", None) or []:
            content = getattr(r, "content", None) or getattr(r, "summary", None)
            if not content:
                chunk_texts = [c.content for c in getattr(r, "chunks", None) or []]
                content = "\n".join(chunk_texts)
            if content:
                lines.append(f"[{label}] {content}")
    return "\n".join(lines) if lines else "(no relevant memory found)"
