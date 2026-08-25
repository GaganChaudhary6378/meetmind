"""org_shared retrieval + confidence gate — tasks 3.3/3.4 core logic.

Kept plain, synchronous, and dependency-light on purpose: `app/voice/bot.py`
wires this into an async pipecat pipeline, but the retrieval + gating
decision itself has no reason to be async or pipecat-aware. Testing it
here (`tests/test_rag_gate.py`) needs no audio, no models, no event
loop — just `shared.query` mocked, same pattern the pre-pipecat tests
already used.

Shared-memory-only by design (MVP pivot, plan.md §0 / M5): a
standalone voice loop with no live meeting yet has no "whose private
memory" identity to attach to, so this queries `org_shared` only. The
private-memory branch lives in `app/agents/person_agent.py` for the
Slack surface, not here.
"""
from __future__ import annotations

from app.config import settings
from app.memory import shared

NOT_SURE_REPLY = "Not sure — best to ask them directly."

# Fed to the LLM as its system prompt (see app/voice/bot.py). TTS
# speaks whatever text comes back verbatim, so this must produce plain
# spoken sentences: no markdown, no source lists (those go to Meet
# chat as text, task M5a, not into the spoken answer).
VOICE_SYSTEM_PROMPT = (
    "You are a voice assistant speaking answers out loud in a live "
    "meeting. Answer only from the provided context, in 1-3 short "
    "spoken sentences, as if you were talking, not writing. Never use "
    "markdown, asterisks, bullet points, headers, or any other text "
    "formatting — plain spoken sentences only, nothing else on the "
    "page but words a person could say aloud. If the context does not "
    "contain the answer, say you are not sure — do not guess."
)


class RagGate:
    """Retrieves `org_shared` context for a question and applies the
    confidence gate (task 3.4) — below `CONFIDENCE_THRESHOLD`, refuses
    to guess.
    """

    def resolve(self, question: str) -> str | None:
        """Return formatted context to hand the LLM, or None if the
        top retrieval score is below the confidence threshold — the
        caller should speak `NOT_SURE_REPLY` directly and skip the LLM
        call entirely.

        A question with zero hits does NOT short-circuit here (there
        is no score to compare against the threshold) — it still goes
        to the LLM with "(no relevant memory found)" as context, and
        the system prompt (`VOICE_SYSTEM_PROMPT`) tells the model to
        say it's not sure rather than guess. Same behavior as before
        this module existed (`app/voice/pipeline.py`'s original logic).
        """
        hits = shared.query(question)
        top_score = _top_score(hits)
        if top_score is not None and top_score < settings.confidence_threshold:
            return None
        return _format_context(hits)


def _top_score(hits) -> float | None:
    results = getattr(hits, "results", None) or []
    if not results:
        return None
    return max(getattr(r, "score", 0.0) for r in results)


def _format_context(hits) -> str:
    lines: list[str] = []
    for r in getattr(hits, "results", None) or []:
        content = getattr(r, "content", None) or getattr(r, "summary", None)
        if not content:
            chunk_texts = [c.content for c in getattr(r, "chunks", None) or []]
            content = "\n".join(chunk_texts)
        if content:
            lines.append(f"[shared] {content}")
    return "\n".join(lines) if lines else "(no relevant memory found)"
