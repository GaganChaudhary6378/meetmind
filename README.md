# Personalised Meeting Agents

Federated multi-agent system. One personal agent per person, private memory
each, shared org memory, Slack chat surface (phase 1). Full design in
`plan.md`, task list in `breakdown.md`, build status in `progress.md`.

## 1. Setup

```bash
python -m venv venv
source venv/bin/activate      # zsh/bash
pip install -r requirements.txt
```

Copy the env template and fill in real values:

```bash
cp .env.example .env
```

Fill in `.env`:

| Var | Where to get it |
| --- | --- |
| `SLACK_BOT_TOKEN` | Slack app → OAuth & Permissions (starts `xoxb-`) |
| `SLACK_APP_TOKEN` | Slack app → Basic Information → App-Level Tokens (starts `xapp-`, needs `connections:write` scope for Socket Mode) |
| `SLACK_SIGNING_SECRET` | Slack app → Basic Information |
| `SLACK_SHARED_KNOWLEDGE_CHANNEL_ID` | Target channel → View channel details → channel ID (starts `C`) |
| `SUPERMEMORY_API_KEY` | Supermemory dashboard |
| `SUPERMEMORY_SHARED_WRITE_API_KEY` | Supermemory dashboard, scope to `org_shared` tag only (leave blank until an ingestion job needs to write) |
| `OPENROUTER_API_KEY` | OpenRouter dashboard |
| `LLM_ALLOW_FALLBACKS` | `true` (default) — auto-retries another provider if one is busy/rate-limited |
| `LLM_PROVIDER_ORDER` | Optional, comma-separated preferred provider order (e.g. `openai,azure`). Blank = OpenRouter picks. |
| `A2A_AGENT_HOST` | Local dev: `127.0.0.1`. Only matters once each teammate's PersonAgent A2A server is running (phase 2). |
| `A2A_TEAM_ROSTER` | `slack_user_id:port,...` — one entry per teammate running a PersonAgent A2A server (see §3). |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials → OAuth client ID, type "Desktop app" |
| `GMAIL_REFRESH_TOKEN` | One-time local OAuth consent flow — see §6 |
| `GMAIL_TRANSCRIPT_QUERY` | Gmail search query for transcript emails. Default `in:inbox` — narrow once a real transcript email format is seen |

Required Slack app scopes: `chat:write`, `commands`, `channels:history` (or
`groups:history` for private channels), Socket Mode enabled.

Slash commands to register in the Slack app config: `/update`, `/ask`,
`/ask-person`, `/standup`.

## 2. Run the Slack bot

```bash
python -m app.api.slack_app
```

Runs in Socket Mode — no public HTTPS endpoint needed for local dev.

In Slack:
- `/update <what you did today>` — saves to your private memory.
- `/ask <question>` — answers from your private memory + shared org memory.
- Any plain message posted in the channel set as
  `SLACK_SHARED_KNOWLEDGE_CHANNEL_ID` gets auto-ingested into shared org
  memory (chat-archiver path, task 1.3).

## 3. Run facilitator mode (phase 2, A2A)

Each teammate's PersonAgent needs to run as its own A2A server before the
facilitator (`/standup`) can reach it. Start one per teammate, one port
each, matching the ports in `A2A_TEAM_ROSTER`:

```bash
python -m app.agents.a2a_server U0ALICE 9001
python -m app.agents.a2a_server U0BOB   9002
```

Then, with the Slack bot running (§2), use `/standup` or `/ask-person`
in Slack:

```
/standup             # everyone in A2A_TEAM_ROSTER is pulled
/standup @bob        # @bob is marked absent, still pulled via A2A
/ask-person @rahul what did you complete this week?
```

`@name` mentions work directly — Slack expands them to `<@U0RAHUL|rahul>`
before the bot sees them, and `app/api/slack_mentions.py` parses that
back into the user_id (both commands still also accept a raw user_id).

Both commands call the target teammate's own A2A server, never another
person's private memory directly (see `app/agents/a2a_executor.py`).
`/standup` compiles every reply into one summary via the LLM router's
cheap "summary" tier; `/ask-person` returns one teammate's own answer
as-is.

## 4. Seed test company knowledge

To push sample company-knowledge messages into the shared-knowledge
channel (for testing ingestion + retrieval + the 1.6 leak test):

```bash
python -m tests.seed_company_knowledge
```

Posts 12 test messages to `SLACK_SHARED_KNOWLEDGE_CHANNEL_ID`, 1 second
apart — covering auth migration, planning freeze, PTO policy, Jira
connector note, a leak-test canary fact, and full company policies
(security, travel/expense, remote work, code review standards, incident
response, holiday calendar, onboarding checklist). The bot must already
be a member of that channel, and the Slack bot (`message` event handler
in `slack_app.py`) must be running to auto-ingest them — start the bot
first, then run the seed script.

After seeding, test retrieval with `/ask` in Slack, e.g.:

```
/ask when does the auth token migration ship, and who owns it?
/ask what is the office plant on the 4th floor named?
/ask what is the hotel cap for tier-1 cities?
/ask how many approvals does a PR touching billing need?
```

The second question checks the private/shared boundary (task 1.6): the
answer should come from `org_shared`, and a different person's private
agent should never surface another person's private update.

## 5. Backfill existing channel history

Live ingestion (`handle_channel_message` in `slack_app.py`) only catches
messages posted while the bot is running. To sync messages already
sitting in the shared-knowledge channel (e.g. from the seed script if
the bot was down, or older channel history) into `org_shared`:

```bash
python -m app.memory.backfill_slack
```

Requires `SUPERMEMORY_SHARED_WRITE_API_KEY` set in `.env` — the script
aborts loud if it's missing (same guard as `shared.ingest`). Bot must be
a member of the channel and have the `channels:history` scope. Safe to
re-run; each run re-ingests the full history (dedup is not yet built —
track under a future task if channel history gets long).

## 6. Gmail transcript ingestion (M1)

One-time OAuth consent to get a refresh token (per-user OAuth, reads only
the connecting mailbox — not domain-wide delegation):

```bash
python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_config(
    {'installed': {
        'client_id': '<GMAIL_CLIENT_ID>',
        'client_secret': '<GMAIL_CLIENT_SECRET>',
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
    }},
    scopes=['https://www.googleapis.com/auth/gmail.readonly'],
)
creds = flow.run_local_server(port=0)
print('GMAIL_REFRESH_TOKEN=' + creds.refresh_token)
"
```

Paste the printed value into `.env` as `GMAIL_REFRESH_TOKEN`. Then run
the ingestion job:

```bash
python -m app.memory.ingest_gmail
```

Scans the connected mailbox for messages matching `GMAIL_TRANSCRIPT_QUERY`
(default `in:inbox`) and writes each into `org_shared`. No confirmed
sample of Google Meet's real auto-transcript email exists yet — for
testing, send a test email from a different address to the connected
mailbox and it will be picked up by the default broad query. Narrow
`GMAIL_TRANSCRIPT_QUERY` once a real transcript email format is known
(open item, breakdown.md). Requires `SUPERMEMORY_SHARED_WRITE_API_KEY`
set — aborts loud if missing, same guard as `backfill_slack.py`. Safe
to re-run; dedup is not yet built (same known gap as §5).

There is no live Gmail listener yet (would need a separate Pub/Sub push
subscription) — this is backfill/re-run only, same role
`backfill_slack.py` plays for Slack.

## 7. Run tests

```bash
pytest
```

## 8. Project layout

```
app/
  config.py           # all env vars read here, nowhere else
  agents/
    person_agent.py    # PersonAgent — record_update() / answer()
    a2a_executor.py     # wraps PersonAgent for the A2A server (2.1)
    a2a_server.py        # runs one PersonAgent as an A2A server (2.1)
    a2a_client.py          # calls a teammate's A2A server (2.1)
    facilitator_agent.py    # runs the standup, compiles updates (2.2/2.3)
  memory/
    private.py         # per-person container tag (1.1)
    shared.py           # org_shared container tag (1.3)
    pipeline.py          # short-term -> long-term summarize job (1.2)
    ingest_slack.py       # chat-archiver ingestion job (live events)
    backfill_slack.py       # chat-archiver ingestion job (history sync)
    ingest_gmail.py            # Gmail transcript ingestion job (M1, backfill/re-run only)
    client.py                 # Supermemory API wrapper
  llm/
    router.py           # ask(prompt, context) -> text (1.4)
  api/
    slack_app.py         # Slack bot surface (1.5), /standup + /ask-person (2.2)
    slack_mentions.py     # parse @mentions from slash-command text
tests/
  seed_company_knowledge.py   # posts test org-knowledge messages
  test_isolation.py           # cross-person leak test (1.6)
  test_facilitator_a2a.py     # A2A wiring test, real local servers (2.1/2.2/2.3)
  test_slack_mentions.py      # @mention parsing unit tests
```

## 9. Status

See `progress.md` for phase-by-phase build status. Phase 1 is complete
(1.6 leak test passes). Phase 2 (facilitator mode + A2A) is done and
tested (real local A2A servers in `test_facilitator_a2a.py`) — still
worth a real multi-teammate Slack test once a second person is on the
workspace (§3).
