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
| M1 Gmail connector | done | `app/memory/ingest_gmail.py` | per-user OAuth (user confirmed); no real transcript sample yet, so `GMAIL_TRANSCRIPT_QUERY` defaults to `in:inbox` — user will test by emailing the connected mailbox from another address. No live Gmail listener (needs Pub/Sub push, not built) — backfill/re-run only, mirrors `backfill_slack.py`. |
| M2 Slack historical ingestion | done (reused) | `app/memory/ingest_slack.py`, `app/memory/backfill_slack.py` | already covers this, no new work |
| M3 Voice loop | not started | (Phase 3 files, none yet) | |
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
Not started.

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
Last updated: 2026-08-26 (M1 Gmail connector built — per-user OAuth, backfill-only, broad default query pending a real transcript sample)
