# Progress — Personalised Meeting Agents

Track against `breakdown.md` task list. Update after each work session.

## MVP scope pivot (2026-08-25)

Build priority redirected to a narrower MVP: shared-org-knowledge Q&A,
live in Google Meet, sourced from Gmail + Slack history. No private
memory or facilitator/A2A on the critical path. See `plan.md` §0 and
`breakdown.md` "MVP task list" (M1-M5). Nothing below this line is
undone by the pivot — Phase 1/2 work stays built and tested, just not
required for the MVP to ship.

| Task | Status | File(s) | Note |
| --- | --- | --- | --- |
| M1 Gmail connector | done | `app/memory/ingest_gmail.py` | per-user OAuth (user confirmed); `GMAIL_TRANSCRIPT_QUERY` defaults to `from:noreply-meet@google.com` (user confirmed sender filter). No live Gmail listener (needs Pub/Sub push, not built) — backfill/re-run only, mirrors `backfill_slack.py`. |
| M2 Slack historical ingestion | done (reused) | `app/memory/ingest_slack.py`, `app/memory/backfill_slack.py` | already covers this, no new work |
| M3 Voice loop | done | `app/voice/bot.py`, `app/voice/rag_gate.py` | shared-memory-only (no private branch — MVP scope). Migrated to pipecat (2026-08-26) after a hand-rolled first pass worked live but had real gaps (fixed-duration recording, regex wake-word) — see Phase 3 table below. |
| M4 Google Meet bot-join | not started | (Phase 4 files, none yet) | SDK pick still open |
| M5 Live answer (shared-only) | not started | | depends on M1, M3, M4 |
| M5a Source citation in Meet chat | not started | | depends on M5 + M4's chat-post capability (SDK pick still open) |

## Phase 1 — Personal Slack agent, text-only

| Task | Status | File(s) | Note |
| --- | --- | --- | --- |
| 1.1 Private memory store (per-person) | done | `app/memory/private.py`, `app/memory/client.py` | container-tag write path built |
| 1.2 Short-term → long-term memory pipeline | done | `app/memory/pipeline.py` | summarize job in place |
| 1.3 Shared org memory store | done | `app/memory/shared.py`, `app/memory/ingest_slack.py` | `org_shared` tag, ingestion job |
| 1.4 LLM router abstraction | done | `app/llm/router.py` | `ask(prompt, context) -> text` |
| 1.5 Slack bot surface | done | `app/api/slack_app.py` | need to confirm framework pick logged in breakdown open items |
| 1.6 Cross-person leak test | done | `tests/test_isolation.py` | fixed a false-fail in the assertion (checked topic word echoed from the question, not real leaked content); now checks a fact fragment unique to Alice's private memory. Passes. |

**Phase 1 status: complete. All tasks done, 1.6 leak test passes — gate cleared for phase 2.**

## Phase 2 — Facilitator mode + A2A

| Task | Status | File(s) | Note |
| --- | --- | --- | --- |
| 2.1 A2A protocol wiring | done | `app/agents/a2a_executor.py`, `app/agents/a2a_server.py`, `app/agents/a2a_client.py` | real `a2a-sdk` (pinned `<1.0`, pydantic API), one server per teammate |
| 2.2 Facilitator logic | done | `app/agents/facilitator_agent.py`, `app/api/slack_app.py` (`/standup`, `/ask-person`) | compile step routed to `router.ask(..., tier="summary")`. Added `/ask-person @teammate <question>` — direct A2A ask to one teammate's own agent, not just the full standup. Both commands accept Slack `@mentions` via `app/api/slack_mentions.py`. |
| 2.3 Absence handling | done | `app/agents/facilitator_agent.py` (`collect_updates`) | absent teammates pulled the same way, flagged with a note, not a different code path |

Tests: `tests/test_facilitator_a2a.py` — real local A2A servers over HTTP, `PersonAgent.answer` mocked (memory correctness already covered by 1.6). Covers a happy path and one unreachable-teammate path. `tests/test_slack_mentions.py` — @mention parsing. All passing.

**Phase 2 status: done. Needs a real multi-person Slack test when a second teammate is available — see README §3.**

## Phase 3 — Voice loop

Built twice. First pass (2026-08-26) hand-rolled STT/wake-word/TTS
wrappers directly — worked, confirmed live end to end (STT, wake-word,
`org_shared` retrieval, confidence gate, TTS all fired correctly). But
had real gaps surfaced by that live test: fixed-duration mic recording
instead of real turn detection, a regex wake-word check, and manual
backend wiring (hit one dead-end already — the `kokoro` PyPI package
doesn't install on Python 3.13, worked around with `kokoro-onnx`).
Investigated [pipecat](https://github.com/pipecat-ai/pipecat) (fetched
its README and multiple source files directly) and migrated same day
— it wraps the exact same backends (`faster-whisper`, `kokoro-onnx`,
OpenRouter) plus real VAD and native wake-phrase handling. Full plan
in `/Users/apple/.claude/plans/refactored-scribbling-boole.md`.

| Task | Status | File(s) | Note |
| --- | --- | --- | --- |
| 3.1 STT integration | done | `app/voice/bot.py` (`WhisperSTTService`) | pipecat's Whisper service, itself a direct `faster-whisper` wrapper (confirmed by reading its source); model size via `STT_MODEL_SIZE` |
| 3.2 Name-mention / wake-word detector | done | `app/voice/bot.py` (`WakePhraseUserTurnStartStrategy`) | pipecat's native wake-phrase turn strategy, replaces the old hand-rolled regex; phrase = `AGENT_NAME` |
| 3.3 LLM answer call | done | `app/voice/bot.py` (`OpenRouterLLMService`), `app/voice/rag_gate.py` (`VOICE_SYSTEM_PROMPT`) | pipecat's OpenRouter LLM service, same API key/base URL as `app/llm/router.py`; system prompt kept in `rag_gate.py` — plain spoken sentences, no markdown, since TTS speaks the reply verbatim |
| 3.4 Confidence threshold gate | done | `app/voice/rag_gate.py` (`RagGate.resolve`) | reuses `CONFIDENCE_THRESHOLD`; kept plain/synchronous on purpose (not folded into the async pipecat pipeline) so it stays fast to unit-test |
| 3.5 TTS integration | done | `app/voice/bot.py` (`KokoroTTSService`) | pipecat's Kokoro service, a direct `kokoro-onnx` wrapper — even auto-downloads the same model files we'd fetched by hand, from the same GitHub release URLs |
| 3.6 Standalone test harness | done | `app/voice/bot.py` (run via `python -m app.voice.bot`), `tests/test_rag_gate.py` | real mic/speaker via pipecat's `LocalAudioTransport`, continuous listening (Ctrl+C to stop) — no fixed duration like the old `manual_voice_mic.py`. Confidence-gate logic separately unit-tested (`test_rag_gate.py`, no audio/pipecat needed); full pipeline wiring exercised by hand, not by an automated pipecat-eval test (explicit trade-off, see plan) |

**Phase 3 status: done (standalone, no live meeting join — that's phase 4 / M4). pipecat does not solve M4 either — no native Google Meet transport; the SDK-pick open item is unchanged.**

## Phase 4 — Live meeting presence
Not started.

## Phase 5 — Multi-product expansion
Not started.

## Open items (from breakdown.md)
- Slack framework pick (1.5) — confirm which one `slack_app.py` uses
- Meet bot-join SDK pick (4.1)
- `A2AClient` deprecated in `a2a-sdk` 0.3.26, in favor of `ClientFactory` — still works, swap later
- Gmail transcript identification (M1) — `GMAIL_TRANSCRIPT_QUERY` defaults to `in:inbox` (no real Meet auto-transcript email seen yet); narrow once a real sample is available
- Gmail live listener (M1) — only backfill/re-run built; a live path needs a Gmail Pub/Sub push subscription, not built

---
Last updated: 2026-08-26 (M3 voice loop migrated to pipecat — real VAD turn detection + native wake-phrase handling, replaces the first hand-rolled pass; still standalone only, no Meet join yet)
