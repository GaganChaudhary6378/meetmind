"""LLM router — task 1.4.

One function: ask(prompt, context) -> text. Everything else in the app
calls this, never a provider SDK directly. Swapping OpenRouter for a
direct provider later means editing this file only.

Tier routing (plan §3): "answer" = live, high-stakes, said out loud ->
strong model. "summary" = cheap, high-volume, facilitator/summarize
calls -> small model.
"""
from __future__ import annotations

from typing import Literal

from openai import OpenAI

from app.config import settings

Tier = Literal["answer", "summary"]

_MODEL_BY_TIER: dict[Tier, str] = {
    "answer": settings.llm_model_answer,
    "summary": settings.llm_model_summary,
}


def _client() -> OpenAI:
    # OpenRouter exposes an OpenAI-compatible API.
    return OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)


def _provider_routing() -> dict:
    """OpenRouter provider-routing options (docs: openrouter.ai/docs/features/provider-routing).

    `allow_fallbacks` lets OpenRouter retry the next provider for this
    model if the first one is busy/rate-limited, instead of the call
    just failing. `order` is optional — an explicit preferred-provider
    list; left empty, OpenRouter picks.
    """
    provider: dict = {"allow_fallbacks": settings.llm_allow_fallbacks}
    order = [p.strip() for p in settings.llm_provider_order.split(",") if p.strip()]
    if order:
        provider["order"] = order
    return provider


def ask(prompt: str, context: str, tier: Tier = "answer") -> str:
    """Send prompt + retrieved memory context to the routed model, return text.

    `context` is pre-formatted retrieved memory (private + shared), not
    raw conversation history — retrieval happens in the caller.
    """
    model = _MODEL_BY_TIER[tier]
    messages = [
        {
            "role": "system",
            "content": (
                "You are a personal meeting agent. Answer only from the "
                "provided context. If the context does not contain the "
                "answer, say you are not sure — do not guess."
            ),
        },
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{prompt}"},
    ]
    response = _client().chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=settings.llm_max_tokens,
        extra_body={"provider": _provider_routing()},
    )
    return response.choices[0].message.content or ""
