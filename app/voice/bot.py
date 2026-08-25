"""Voice loop, pipecat-backed — tasks 3.1 (STT), 3.2 (wake phrase),
3.5 (TTS), 3.6 (standalone test harness, no live meeting join).

Built on pipecat (https://github.com/pipecat-ai/pipecat) instead of a
hand-rolled loop — see plan notes / progress.md for why. Every service
below wraps the exact backend the hand-rolled version used directly:
`WhisperSTTService` wraps faster-whisper, `KokoroTTSService` wraps
kokoro-onnx, `OpenRouterLLMService` is a thin OpenAI-compatible client
against the same OpenRouter endpoint `app/llm/router.py` uses.
`SileroVADAnalyzer` gives real voice-activity-detected turn taking
(the hand-rolled version recorded a fixed N-second chunk instead) and
`WakePhraseUserTurnStartStrategy` replaces the old regex wake-word
check in `app/voice/wake_word.py` (now removed).

Run directly: `python -m app.voice.bot` — a continuous, always-listening
process (Ctrl+C to stop). No fixed recording duration; pipecat starts
a "turn" on real speech and ends it on real silence.

The one piece of custom logic — org_shared retrieval + the confidence
gate (tasks 3.3/3.4) — lives in `app/voice/rag_gate.py`, kept plain
and synchronously unit-tested (`tests/test_rag_gate.py`) rather than
folded into this async pipeline, per the decision recorded when this
migration was planned.

Still shared-memory-only (MVP pivot, plan.md §0 / M5): a standalone
voice loop with no live meeting yet has no "whose private memory"
identity to attach to.

Does NOT solve M4 (Google Meet bot-join) — no native Meet transport
in pipecat. `LocalAudioTransport` here is for standalone testing only,
same role the old `manual_voice_mic.py` played.
"""
from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import Frame, LLMContextFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.openrouter.llm import OpenRouterLLMService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.turns.user_start import WakePhraseUserTurnStartStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies, default_user_turn_start_strategies
from pipecat.workers.runner import WorkerRunner

from app.config import settings
from app.voice.rag_gate import VOICE_SYSTEM_PROMPT, NOT_SURE_REPLY, RagGate


class RagGateProcessor(FrameProcessor):
    """Sits between the user-turn aggregator and the LLM. On each
    completed user turn (an `LLMContextFrame`), resolves org_shared
    context via `RagGate` and either injects it into the context
    before forwarding to the LLM, or — below the confidence threshold
    — skips the LLM entirely and pushes `NOT_SURE_REPLY` straight to
    TTS (same short-circuit pattern pipecat's own voicemail-detection
    example uses for a conditional TTSSpeakFrame bypass).
    """

    def __init__(self, gate: RagGate | None = None):
        super().__init__()
        self._gate = gate or RagGate()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not isinstance(frame, LLMContextFrame):
            await self.push_frame(frame, direction)
            return

        question = _last_user_text(frame.context)
        context_text = self._gate.resolve(question) if question else None

        if question and context_text is None:
            await self.push_frame(TTSSpeakFrame(NOT_SURE_REPLY), direction)
            return

        if context_text:
            frame.context.add_message(
                {"role": "system", "content": f"Context:\n{context_text}"}
            )
        await self.push_frame(frame, direction)


def _last_user_text(context: LLMContext) -> str:
    for message in reversed(context.get_messages()):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def build_pipeline() -> Pipeline:
    transport = LocalAudioTransport(
        LocalAudioTransportParams(audio_in_enabled=True, audio_out_enabled=True)
    )

    stt = WhisperSTTService(
        device="cpu",
        compute_type="int8",
        settings=WhisperSTTService.Settings(model=settings.stt_model_size),
    )

    llm = OpenRouterLLMService(
        api_key=settings.openrouter_api_key,
        settings=OpenRouterLLMService.Settings(
            model=settings.llm_model_answer,
            system_instruction=VOICE_SYSTEM_PROMPT,
        ),
    )

    tts = KokoroTTSService(
        model_path=settings.kokoro_model_path,
        voices_path=settings.kokoro_voices_path,
        settings=KokoroTTSService.Settings(voice=settings.tts_voice),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                start=[
                    WakePhraseUserTurnStartStrategy(phrases=[settings.agent_name], timeout=5.0),
                    *default_user_turn_start_strategies(),
                ]
            ),
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    return Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            RagGateProcessor(),
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )


async def main() -> None:
    logger.info(f"Voice loop starting — say '{settings.agent_name}' to trigger an answer. Ctrl+C to stop.")
    pipeline = build_pipeline()
    worker = PipelineWorker(pipeline, params=PipelineParams(enable_metrics=True))
    runner = WorkerRunner()
    await runner.add_workers(worker)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
