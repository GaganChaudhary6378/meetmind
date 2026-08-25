"""Central settings loader. All env vars read here, nowhere else.

Every other module imports `settings` from this file instead of
calling os.environ directly. Keeps env access in one place.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Slack (chat surface, phase 1) ---
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_signing_secret: str = ""
    # Channel ID (starts "C...") the chat-archiver ingestion job reads
    # from. Only messages posted here become shared org memory.
    slack_shared_knowledge_channel_id: str = ""

    # --- Supermemory (memory layer) ---
    supermemory_api_key: str = ""
    # Optional: scoped key restricted to the org_shared container tag.
    # Used only by ingestion jobs (codebase indexer, chat archiver) —
    # never by a person's private-update write path.
    supermemory_shared_write_api_key: str = ""
    supermemory_base_url: str = "https://api.supermemory.ai"
    shared_container_tag: str = "org_shared"

    # --- LLM routing (OpenRouter) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Strong/low-latency model for live, high-stakes answers.
    llm_model_answer: str = "openai/gpt-4.1"
    # Cheap/small model for summarization and facilitator-summary calls.
    llm_model_summary: str = "openai/gpt-4.1-mini"
    # Explicit output cap — without this, OpenRouter defaults to the
    # model's max (e.g. 65536), which can exceed a free/low-balance
    # account's affordable credits and returns a 402.
    llm_max_tokens: int = 800
    # If one provider is busy/rate-limited, OpenRouter retries the next
    # provider for the same model automatically.
    llm_allow_fallbacks: bool = True
    # Optional preferred provider order, comma-separated (e.g.
    # "openai,azure"). Empty = let OpenRouter pick.
    llm_provider_order: str = ""

    # --- Retrieval confidence gate (plan §6) ---
    # 0.90 is plan.md's target once tuned, but real cosine-similarity
    # scores rarely reach that against short queries — start lower and
    # raise it once you've measured real false-pos/false-neg rate.
    confidence_threshold: float = 0.50

    # --- Gmail (transcript ingestion, task M1) ---
    # Per-user OAuth (not domain-wide delegation) — reads only the
    # connecting user's mailbox. Refresh token comes from a one-time
    # local OAuth consent flow (see README §Gmail setup).
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    # Gmail search query used to find transcript emails — scoped to
    # Google Meet's auto-transcript sender.
    gmail_transcript_query: str = "from:noreply-meet@google.com"

    # --- Voice loop (phase 3, tasks 3.1-3.5, pipecat-backed — app/voice/bot.py) ---
    # Word/phrase pipecat's WakePhraseUserTurnStartStrategy (3.2) listens
    # for to start a turn.
    agent_name: str = "Agent"
    # faster-whisper model size, passed to pipecat's WhisperSTTService
    # (3.1). "base" is a reasonable CPU default; swap to "small"/"medium"
    # if accuracy is too low.
    stt_model_size: str = "base"
    # NOT currently wired up: pipecat's WhisperSTTService does not expose
    # faster-whisper's initial_prompt vocabulary-biasing param, so this
    # has no effect since the pipecat migration (was used directly by our
    # own faster-whisper wrapper before that). Kept in case a future
    # pipecat version adds it, or a custom STT subclass wires it back in.
    stt_vocab_hint: str = "auth, migration, PTO, Jira, Slack, Supermemory, standup"
    # Kokoro voice id, passed to pipecat's KokoroTTSService (3.5).
    # "af_heart" is one of Kokoro's built-in American-English voices.
    tts_voice: str = "af_heart"
    # kokoro-onnx model files, passed to pipecat's KokoroTTSService.
    # Optional — if the files aren't at these paths, KokoroTTSService
    # auto-downloads them to ~/.cache/pipecat/kokoro-onnx on first use
    # (same files, same GitHub release URLs). Fetch manually instead
    # (README §7 Voice loop) to control where they land or reuse an
    # existing download.
    kokoro_model_path: str = "kokoro-v1.0.onnx"
    kokoro_voices_path: str = "voices-v1.0.bin"

    # --- A2A (agent-to-agent, phase 2 facilitator mode) ---
    # Host each PersonAgent's A2A server binds to.
    a2a_agent_host: str = "127.0.0.1"
    # Team roster: "slack_user_id:port,slack_user_id:port,...". Each
    # person's PersonAgent runs its own A2A server on its own port; the
    # facilitator agent looks up each teammate's URL here to call them.
    a2a_team_roster: str = ""

    # --- App ---
    log_level: str = "INFO"

    def a2a_roster(self) -> dict[str, str]:
        """Parse `a2a_team_roster` into {user_id: base_url}."""
        roster: dict[str, str] = {}
        for pair in self.a2a_team_roster.split(","):
            pair = pair.strip()
            if not pair:
                continue
            user_id, _, port = pair.partition(":")
            roster[user_id] = f"http://{self.a2a_agent_host}:{port}"
        return roster


settings = Settings()
