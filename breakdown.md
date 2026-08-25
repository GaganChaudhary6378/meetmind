# Personalised Meeting Agents — Task Breakdown

Derived from `plan.md`. No implementation here — task breakdown only.
Each task lists **What**, **Why**, **Stack**.

## MVP task list (current build target — see plan.md §0)

Reordered, narrower scope: shared-org-knowledge Q&A live in Google Meet,
sourced from Gmail + Slack history. No private memory, no facilitator/A2A
in this path. Tasks below reuse existing phase-numbered tasks where noted;
new tasks get an `M` prefix.

**M1. Gmail connector (ingestion job)**
- What: pull past meeting-transcript emails from Gmail (labeled/filtered
  thread or attachment), extract text, ingest into `org_shared` via the
  same write-gated path as Slack (`app/memory/shared.py`).
- Why: user-specified source for past meeting transcripts (plan §0).
- Stack: Gmail API (OAuth), new `app/memory/ingest_gmail.py` — mirror
  `ingest_slack.py`'s pattern (one function, write-gate check, calls
  `shared.ingest(...)`). One-off backfill script mirroring
  `backfill_slack.py` for existing mailbox history.

**M2. Slack historical ingestion — reuse, no new work**
- What: confirm `app/memory/ingest_slack.py` (live) +
  `app/memory/backfill_slack.py` (history sync) already cover "past
  channel conversation" into `org_shared`.
- Why: already built and tested (task 1.3, progress.md). Zero new build.
- Stack: unchanged.

**M3. Voice loop — reuse Phase 3 tasks 3.1-3.5 unchanged**
- What: STT (faster-whisper), name-mention trigger, LLM answer call,
  confidence gate, TTS (Kokoro). See Phase 3 below for full detail.
- Why: a Google Meet call is audio — text-only Q&A doesn't satisfy "join
  the meeting and answer when called" (plan §0).
- Stack: same as Phase 3, brought forward in priority ahead of Phase 2
  (facilitator/A2A), which is not required for this MVP.

**M4. Google Meet bot-join + admission control — reuse Phase 4 tasks 4.1-4.2**
- What: bot joins as named participant, host/admin explicit accept/reject
  per meeting (Meet's waiting-room gate). See Phase 4 below.
- Why: live-presence requirement, unchanged from original plan.
- Stack: Google Meet bot-join API/SDK (needs concrete integration pick,
  same open item as before) + Meet knock-to-join API.

**M5. Live answer — shared-memory-only variant of Phase 4 task 4.3**
- What: wire Meet mic audio into M3's STT, retrieve from `org_shared`
  only (no private-memory branch — this MVP has no per-person data),
  answer via LLM router, speak back via TTS.
- Why: core MVP deliverable — the actual "join and answer when called."
- Stack: Meet bot audio stream APIs + M3 pipeline + `app/memory/shared.py`
  retrieval. Confidence gate (3.4) still applies — "not sure, ask
  directly" beats a wrong live answer either way.

**M5a. Source citation in Meet chat (new)**
- What: whenever the agent speaks an answer, post the exact source
  link(s) into the Meet in-call text chat at the same moment — e.g.
  `Source: <Slack permalink>` or `Source: <Gmail transcript link>`. If
  the answer drew on more than one retrieved item, list every source,
  not just the top match.
- Why: real-world evidence, not a guess — industry pain point research
  (2026-08-26 search) found "new hires may follow bad advice from a
  chatbot, believing it's authoritative" and "when a speaker label is
  wrong, everything built on top of it comes out wrong too." A spoken
  answer alone gives no way to check either. Voice can't carry a URL
  well, so this is a text side-channel, not part of the TTS speech.
- Stack: uses metadata already captured at ingest — `permalink` +
  `slack_user_id` (`ingest_slack.py`, live) and the equivalent Gmail
  message link (M1, once built). Needs the Meet bot-join SDK (M4) to
  support posting to in-call chat, not just audio in/out — confirm this
  when the SDK pick (open item, M4) is made.

**Explicitly deprioritized for this MVP** (built and available, not on
the critical path): Phase 1 private-memory tasks (1.1, 1.2, 1.6), Phase 2
facilitator + A2A (2.1-2.3), Phase 5 Jira/Linear connectors (5.1-5.2).
Nothing here is deleted — `/standup`, `/ask-person`, private `/update`
all still work in the Slack surface if needed later.

---

## Phase 1 — Personal Slack agent, text-only

**1.1 Private memory store (per-person)**
- What: set up Supermemory container tag per person (`user_<id>`), write path for "today's update."
- Why: each agent own memory only, no cross-leak. Supermemory container tags hash to separate vector namespace per tag — no shared index, isolation strict not best-effort.
- Stack: Supermemory API (hosted, no self-built vector DB), one container tag per person, access-scoped via scoped API key.

**1.2 Short-term → long-term memory pipeline**
- What: raw update lands short-term first, summarize job moves it long-term (embeddings/summary form).
- Why: two-tier retention decision already resolved in plan §6.
- Stack: summarization via OpenRouter (cheap/small model tier).

**1.3 Shared org memory store**
- What: one Supermemory container tag (`org_shared`), read-all, write-gated to ingestion jobs only (codebase indexer, chat archiver).
- Why: shared context without private write path leaking in.
- Stack: Supermemory API, separate container tag from 1.1, write access enforced via scoped API key restricted to `org_shared` (data-layer boundary, not prompt-only).

**1.4 LLM router abstraction**
- What: thin function `ask(prompt, context) -> text`.
- Why: swap providers/models later, zero rewrite cost.
- Stack: OpenRouter. Dev/test only: `:free` tier models or 0x Alpha (do NOT point at real private data — unnamed provider, short preview window).

**1.5 Slack bot surface**
- What: Slack app, receives "what I did today," answers questions in-channel/DM.
- Why: chosen v1 chat surface (plan §7).
- Stack: Slack API/bot framework (not yet chosen — need pick).

**1.6 Cross-person leak test**
- What: verify agent A never answers from agent B's private memory.
- Why: core privacy invariant, must prove before phase 2.
- Stack: manual/scripted test harness against 1.1 + 1.3 boundary.

## Phase 2 — Facilitator mode + A2A

**2.1 A2A protocol wiring**
- What: agent-to-agent handoff — SM's agent calls other agents' agents.
- Why: facilitator needs to pull updates without human relay.
- Stack: `a2a-sdk` (Google-backed A2A protocol), pinned `<1.0` — 1.0+
  switched the SDK's public types to generated protobuf classes, a
  breaking change from the pydantic-model API this code uses
  (`AgentCard`, `AgentSkill`, `AgentExecutor`, `A2AClient`, etc.).
  Each PersonAgent runs its own A2A server (`app/agents/a2a_server.py`);
  the facilitator reaches it only through `app/agents/a2a_client.py` —
  never another person's private memory directly.

**2.2 Facilitator logic**
- What: SM agent runs DSM flow in Slack, requests each person's update via A2A, compiles.
- Why: phase 2 core deliverable (plan §5.2).
- Stack: same LLM router (1.4), route facilitator-summary calls to cheap/small model tier per plan §3 LLM routing note. `/standup` Slack command in `app/api/slack_app.py`; compile step is `facilitator_agent.compile_standup_summary()`, tier=`"summary"`. Also added `/ask-person @teammate <question>` — asks one teammate's own agent directly via A2A, no compile step, for the "what has X completed" case without needing a full standup. Both `/standup` and `/ask-person` accept `@name` mentions (Slack expands to `<@U0ID|name>`; parsed by `app/api/slack_mentions.py`) as well as raw user_ids.

**2.3 Absence handling**
- What: if person absent, facilitator agent pulls their agent's update anyway.
- Why: named use case in plan §1 facilitator mode.
- Stack: A2A + 1.1 private memory read (that person's own agent only).
  `facilitator_agent.collect_updates(absent=...)` calls every teammate
  the same way regardless of presence — absence is a note appended to
  their update text (`_ABSENT_NOTE`), not a different code path.

## Phase 3 — Voice loop (no live meeting join)

**3.1 STT integration**
- What: wire faster-whisper, rolling local audio buffer.
- Why: primary pick — mature, low friction, good latency/accuracy balance (plan §3).
- Stack: faster-whisper, via pipecat's `WhisperSTTService`
  (`pipecat.services.whisper.stt`, confirmed by reading its source —
  it wraps `faster-whisper` directly) rather than a hand-rolled
  wrapper. First pass (`app/voice/stt.py`, since removed) called
  `faster-whisper` directly with a fixed-duration recorded chunk;
  pipecat's own local audio transport + Silero VAD gives real
  turn-based recording instead (see 3.6). Parakeet-TDT swap-in still
  the fallback if 300ms+ latency becomes a real problem.

**3.2 Name-mention / wake-word detector**
- What: cheap local detector scans STT transcript segments for agent's name; only matching segment forwarded to LLM.
- Why: privacy + cost — most meeting audio never leaves STT (plan §2).
- Stack: pipecat's native `WakePhraseUserTurnStartStrategy`
  (`pipecat.turns.user_start`), not LLM-based — same cost/privacy
  property as originally planned. Replaces a first-pass hand-rolled
  regex whole-word match (`app/voice/wake_word.py`, since removed);
  functionally equivalent, just maintained upstream instead of by us.

**3.3 LLM answer call**
- What: on trigger, send transcript segment + retrieved memory context to LLM, get answer text.
- Why: core voice-loop step.
- Stack: OpenRouter router (1.4), route to stronger/low-latency model tier (live-answer, high-stakes — plan §3 routing note).

**3.4 Confidence threshold gate**
- What: check RAG retrieval confidence before speaking; if <90%, answer "not sure, ask them directly" instead of guessing.
- Why: resolved open question, plan §6 — avoid wrong answers spoken live.
- Stack: retrieval confidence score from Supermemory query (1.1/1.3), tune threshold against real false-pos/neg rate in testing.

**3.5 TTS integration**
- What: wire Kokoro, generic voice per agent.
- Why: primary pick — MIT license, CPU-only, cheapest self-host, tops TTS Arena open models (plan §3).
- Stack: Kokoro, via pipecat's `KokoroTTSService`
  (`pipecat.services.kokoro.tts`, confirmed by reading its source —
  it wraps the `kokoro-onnx` package directly, not `kokoro`, for the
  same reason noted below). `kokoro-onnx` was picked over the `kokoro`
  PyPI package because `kokoro` pulls `misaki[en]` -> a pinned `spacy`
  dev-prerelease -> `blis`, which has no Python 3.13 wheel and fails
  to build from source on this stack; `kokoro-onnx` runs the same
  model over ONNX runtime with no spacy dependency. Model files
  (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) are optional to fetch by
  hand (README §7) — pipecat's service auto-downloads them to
  `~/.cache/pipecat/kokoro-onnx` from the same GitHub release URLs if
  missing. CosyVoice2 if latency insufficient once on GPU; Fish
  Speech/Chatterbox deferred (voice cloning = phase 3+, needs separate
  consent flow, not day one).

**3.6 Standalone test harness**
- What: run full STT→trigger→LLM→TTS loop in voice channel or local harness, no live meeting yet.
- Why: prove pipeline + tune wake-word trigger before risking live meeting (plan §5.3).
- Stack: pipecat pipeline (`app/voice/bot.py`, run via
  `python -m app.voice.bot`) using `LocalAudioTransport` for real mic
  in / speaker out — a continuous, always-listening process (real
  Silero VAD turn detection, Ctrl+C to stop), not a fixed-duration
  recording. Confidence-gate logic (3.4) is isolated in
  `app/voice/rag_gate.py` and unit-tested directly
  (`tests/test_rag_gate.py`) rather than through an automated pipecat
  pipeline test — a deliberate trade-off (async pipeline testing adds
  real complexity; the one piece of custom logic stays fast/plain to
  test, the surrounding pipecat wiring gets exercised by hand). No
  Meet/Zoom integration yet — pipecat has no native Google Meet
  transport either, so the M4 SDK-pick open item is unchanged by this
  migration.

## Phase 4 — Live meeting presence

**4.1 Bot-participant join flow**
- What: agent joins Meet as named participant via standard bot-join.
- Why: live presence requirement (plan §1).
- Stack: Google Meet bot-join API/SDK (same model Fathom uses — needs concrete integration pick).

**4.2 Admission control**
- What: host/admin must explicitly accept/reject bot per meeting, Meet's built-in waiting-room gate. No silent access.
- Why: hard requirement, non-negotiable per plan §1.
- Stack: Meet knock-to-join / waiting-room API.

**4.3 Live audio in/out wiring**
- What: connect meeting mic audio into 3.1 STT pipeline; connect 3.5 TTS output into meeting audio out.
- Why: turns standalone test harness (3.6) into live capability.
- Stack: Meet bot audio stream APIs + phase 3 pipeline.

**4.4 Consent/permission check per person**
- What: before agent speaks on someone's behalf, confirm scope matches what that person's agent is permitted to say (owner-controlled, no org override).
- Why: resolved consent model, plan §6 — person owns own agent's scope.
- Stack: permission flags tied to 1.1 private memory access rules.

**4.5 Live pilot test**
- What: run with real meeting, real host admission, monitor for wrong-answer-heard-live risk.
- Why: plan §5.4 flags this as the step where a wrong answer is heard live, in someone's name — gate on 1–3 being solid first.
- Stack: phases 1–4 combined, no isolated stack — this is integration test.

## Phase 5 — Multi-product expansion

**5.1 Jira connector**
- What: new ingestion job feeding shared org memory (per 1.3 write-gate rule).
- Why: same core, new data source (plan §5.5).
- Stack: Jira API → ingestion job → Supermemory `org_shared` container tag.

**5.2 Linear connector**
- What: same pattern as 5.1, different source.
- Why: multi-product expansion goal.
- Stack: Linear API → ingestion job → Supermemory `org_shared` container tag.

---

## Open items — stack not yet decided

- `A2AClient` (used in `app/agents/a2a_client.py`) is deprecated in
  `a2a-sdk` 0.3.26 in favor of `ClientFactory` — still functional,
  just a deprecation warning. Swap later; not urgent.

- Slack framework pick (1.5)
- Meet bot-join SDK pick (4.1 / M4)
- Gmail transcript identification (M1) — `GMAIL_TRANSCRIPT_QUERY`
  defaults to `from:noreply-meet@google.com` (Google Meet's known
  auto-transcript sender). Not yet verified against a real Meet
  transcript email; revisit if the actual sender/subject differs.
- Gmail live listener (M1) — only a backfill/re-run job is built
  (`app/memory/ingest_gmail.py`, mirrors `backfill_slack.py`). A live
  ingest path needs a separate Gmail Pub/Sub push subscription — not
  built, not required for MVP backfill testing.
- ~~Vector DB choice (1.1 / 1.3)~~ — resolved: Supermemory (hosted memory API, container-tag isolation)
- ~~Gmail API auth model (M1)~~ — resolved: per-user OAuth (reads only
  the connecting user's mailbox), not domain-wide delegation

Flag these before phase 1 start.
