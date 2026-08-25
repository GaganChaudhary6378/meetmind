# Personalised Meeting Agents — Build Plan

Federated multi-agent system: one personal agent per person, private memory
each, shared org memory, agent-to-agent (A2A) handoff, live voice presence
in meetings via a standard bot-join + admission-control flow (Google Meet
knock-to-join, same model Fathom uses).

## 0. MVP scope (revised 2026-08-25)

Original design (§1-§7 below) still stands as the long-term architecture.
Build priority is now reordered around a narrower MVP, decided after CEO
review of the standup-agent framing:

- **Shared knowledge only.** No private per-person memory in this MVP —
  drop `1.1`/`1.2`/`1.6` (private memory, leak test) and Phase 2
  (facilitator + A2A) from the critical path. They stay in the codebase
  (already built) but are not required for this build.
- **Sources: Gmail + Slack, historical.** Ingest past meeting transcripts
  from Gmail and past channel conversation from Slack into `org_shared`.
  Slack side reuses `app/memory/ingest_slack.py` +
  `app/memory/backfill_slack.py` unchanged (task 1.3, already done).
  Gmail side is new (task M1 in `breakdown.md`).
- **Live surface: Google Meet only,** not "Meet/Zoom" generic. Bot joins
  as a named participant, admission-gated (plan §1, §5 phase 4 design
  carries over unchanged — just brought forward in priority).
- **Trigger: name-mention during the call** (plan §2 voice pipeline
  carries over unchanged), answers sourced from `org_shared` only.

Why narrower: premise challenge found the standup/private-memory path
required the person to type an update by hand before the agent could say
anything — no advantage over a Slack post at that step (see CEO review,
2026-08-25). Shared-knowledge Q&A has no such step: ingestion is fully
automatic (Gmail + Slack pull), so the agent adds value on every call
without anyone doing extra work first. This also removes the standup
path's inherited risk from live meeting join (Phase 4 was flagged as
highest-risk in the original plan because a wrong answer is heard live,
in someone's name — that risk is unchanged here, but at least nothing
upstream of it is dead weight).

Revised build order for this MVP (supersedes §5 ordering, does not
delete it — §5 phases still apply once this MVP is stable and the
product expands back toward per-person use cases):

1. Gmail ingestion connector (new) + confirm Slack historical ingestion
   already covers "past channel conversation" (it does, 1.3/backfill).
2. Voice loop (§2, §3 STT/TTS picks unchanged) — needed because a Meet
   call is audio, not text.
3. Google Meet bot-join + admission control (§5 phase 4 design, brought
   forward) — answers sourced from `org_shared` only, no private-memory
   branch needed for this MVP.

See `breakdown.md` "MVP task list" for the concrete task breakdown.

## 1. Core idea recap

- **Per-person agent** — private memory (own PRs/commits/chat, "what I did
today"). No agent holds another person's private data.
- **Shared org memory** — codebase, cross-team chat, decisions. Every
agent reads it; nothing writes private data into it.
- **Facilitator mode** — Scrum Master's agent runs the DSM when the SM is
out. Calls on each person's agent via A2A instead of a human.
- **Live presence** — agent joins the meeting as a named participant.
Host/admin explicitly accepts or rejects the bot per meeting (Meet's
built-in waiting-room gate) — no silent access, ever.
- **Voice loop** — someone says the agent's name → STT captures the
question → LLM answers from that person's private memory + shared org
memory → TTS speaks the answer back into the call.



## 2. Voice pipeline

```
 [Meeting audio] --(mic capture, bot participant)--> [STT]
        |
        v
 "<name>, what's the PR status on auth?"  -----> wake-word / name-mention
        |                                          detector (cheap, local)
        v
 [STT transcript] --> [LLM router: OpenRouter] --> [answer text]
        ^                     |
        |          reads: private memory (own) +
        |                 shared org memory (read-only)
        |
 [TTS] <-------------------------------------------+
        |
        v
 [Meeting audio out] — agent "speaks" the answer
```

Trigger is name-mention, not always-on listening. STT runs continuously
on a local buffer (rolling few seconds); only a transcript segment
containing the agent's wake name gets sent to the LLM. Keeps cost and
privacy exposure low — most of the meeting audio never leaves STT.

## 3. Recommended open-source building blocks (as of Aug 2026)



### STT (speech-to-text)


| Option                            | Why                                                                                                                                                                 | Repo                                                                                     |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **faster-whisper** (primary pick) | CTranslate2 port of Whisper. Mature, widely deployed, easy to self-host, good accuracy/latency balance, active maintenance. Best default to start building against. | [https://github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)   |
| NVIDIA Parakeet-TDT               | Fastest throughput (RTFx 2000+), streaming-native via RNN-Transducer. Swap in once latency becomes the bottleneck.                                                  | [https://github.com/NVIDIA/NeMo](https://github.com/NVIDIA/NeMo)                         |
| Moonshine                         | Tiny (27MB), built for edge/low-resource — useful if the agent later runs partly on-device instead of a server.                                                     | [https://github.com/usefulsensors/moonshine](https://github.com/usefulsensors/moonshine) |


Start with faster-whisper. It's the lowest-friction path to a working
demo; move to Parakeet only if 300ms+ latency becomes a real problem in
testing.

### TTS (text-to-speech)


| Option                    | Why                                                                                                                    | Repo                                                                                 |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **Kokoro** (primary pick) | MIT license, tops TTS Arena for open models, runs on plain CPU — no GPU needed to start, cheapest to self-host.        | [https://github.com/hexgrad/Kokoro-82M](https://github.com/hexgrad/Kokoro-82M)       |
| CosyVoice2                | ~150ms streaming latency if Kokoro's CPU latency isn't enough once you're on GPU infra.                                | [https://github.com/FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice) |
| Fish Speech / Chatterbox  | Voice cloning from a short sample — relevant later if each person's agent should sound like them, not a generic voice. | [https://github.com/fishaudio/fish-speech](https://github.com/fishaudio/fish-speech) |


Start with Kokoro for the generic-voice MVP. Personalised voice cloning
(agent sounds like the actual person) is a phase-3+ decision, not day one
— it raises consent questions that need answering before it ships, not
after.

### LLM routing

- **OpenRouter** as the model router — lets you swap/mix models
(cost-tier vs quality-tier) per call without rewriting the app. Use it
for both the "answer this question" call and any summarization calls.
- Keep the router abstraction thin (one function: `ask(prompt, context) -> text`) so swapping OpenRouter for a direct provider later costs nothing.
- Route facilitator-summary calls (cheap, high-volume) to a smaller/cheaper
model; route live-answer calls (low-latency, high-stakes, said out loud)
to a stronger model. Don't use the same tier for both.

#### Free tier (dev/testing only)

- OpenRouter has 28+ `:free` models (DeepSeek R1, Llama 4 Scout, Qwen3
Coder 480B, Gemini Flash, etc). Rate-limited: 20 req/min hard cap always;
50 req/day at $0 balance, 1000 req/day permanently once you've bought
$10 credit. Fine for dev, not enough for a real team pilot.
- **Ox Alpha** (`0x Alpha`) — stealth model on OpenRouter since 20 Aug
2026, up to 100T free tokens/day, 1M context, anonymous provider
(guesses: Z.ai GLM or Microsoft MAI, unconfirmed). Preview only, runs
until ~27 Aug 2026. Use now for scaffolding/prompt dev — the thin
router abstraction makes swapping it out a one-line change when it
disappears. Do not point it at real private-memory data while the
provider is unnamed and the window is this short.



## 4. Memory layer

- **Provider: Supermemory** (hosted memory API) instead of a self-built
vector store. Handles ingestion, fact extraction, embeddings, temporal
awareness, and retrieval behind one API — cuts the "build our own vector
DB" scope entirely.
- **Isolation mechanism: container tags.** A container tag is an opaque
namespace string attached to each memory at write time and passed back
on every search/list/update. Each tag hashes to its own dedicated vector
namespace — no shared index, so isolation is strict, not best-effort.
- **Private memory** — one container tag per person (e.g. `user_<id>`).
Written to by that person's daily updates, their own PRs/commits.
Read-only to everyone except that person's own agent.
- **Shared org memory** — one container tag for the org (e.g. `org_shared`),
read access for all agents, write access gated to defined ingestion jobs
(codebase indexer, chat archiver) via **scoped API keys** restricted to
that tag — never written to directly by a person's private update.
- Enforce the private/shared boundary at the **data layer** (Supermemory
container tags + scoped API keys), not just in the prompt. A prompt
instruction not to leak data is not a security boundary. Supermemory's
isolation model — separate vector namespace per tag — satisfies this
directly, so this requirement carries over unchanged from the
self-built-DB version of this plan.



## 5. Build order (phased)

1. **Personal Slack agent, text-only.** Private memory + shared org memory
  working end to end. Feed it "what I did today," ask it questions in
   Slack, verify it answers correctly and doesn't leak across people.
2. **Facilitator mode + A2A.** SM's agent runs the standup in Slack,
  pulls updates from other agents when someone's absent. Still text.
3. **Voice loop, no live meeting join yet.** Wire STT → LLM → TTS as a
  standalone loop (e.g. answer questions in a voice channel or local
   test harness) to prove the pipeline and tune the name-mention trigger.
4. **Live meeting presence.** Bot joins Meet/Zoom as a named participant,
  admission-gated per meeting. Only attempt this after 1-3 are solid —
   this is the step where a wrong answer is heard live, in someone's name.
5. **Multi-product expansion.** Same core, new connectors: Jira, Linear.



## 6. Open questions — resolved

- **Confidence threshold.** Check the RAG store for the answer before
speaking. If retrieval confidence < 90%, agent says "not sure, ask them
directly" instead of guessing live. 90% is a starting number — tune
against real false-positive/false-negative rate once in testing.
- **Consent model.** The individual person owns their own agent's scope —
they decide what it can say on their behalf. No org-wide override; each
person edits their own agent's permissions.
- **Voice identity.** Generic TTS voice per agent for now. Voice cloning
deferred until explicitly requested (separate consent flow needed then).
- **Data retention — two-tier memory:**
  - **Short-term memory** — today's update lands here first ("what I did
  today," raw form).
  - **Long-term memory** — short-term entries get summarized and moved
  into long-term storage (embeddings/summary form, not raw). Long-term
  is what the shared/private RAG lookups actually query against.



## 7. Stack summary


| Layer          | Choice                                                      |
| -------------- | ----------------------------------------------------------- |
| STT            | faster-whisper (start), Parakeet-TDT (scale)                |
| TTS            | Kokoro (start), CosyVoice2 (latency), Fish Speech (cloning) |
| LLM            | OpenRouter router, thin abstraction over provider           |
| Private memory | Supermemory, per-person container tag, access-scoped        |
| Shared memory  | Supermemory, org-wide container tag, read-all / write-gated |
| Agent comms    | A2A protocol (Google-backed, 150+ orgs on it already)       |
| Meeting join   | standard bot-participant + host admission gate              |
| Chat surface   | Slack (v1), expand to Jira/Linear later                     |


