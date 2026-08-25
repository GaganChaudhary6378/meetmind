"""Slack bot surface — task 1.5.

Slash commands instead of NLU-guessing intent from free text:
/update  — store "what I did today"
/ask        — ask your own agent (private + shared memory).
/ask-person — ask a teammate's own agent via A2A (phase 2, task 2.1).
              `/ask-person @rahul what did you complete this week?`
              Never touches @rahul's private memory directly — the
              question is routed to Rahul's own agent, which answers
              under his own consent (plan §6).
/standup    — facilitator mode (phase 2, task 2.2/2.3): SM's agent
              pulls every teammate's status update via A2A and
              compiles it. Text after the command is a space- or
              @mention-separated list of teammates absent from the
              standup (still pulled via A2A) — e.g. `/standup @bob`.

Run with Socket Mode (SLACK_APP_TOKEN) so no public HTTP endpoint is
needed for local dev.
"""
from __future__ import annotations

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import asyncio

from app.agents.a2a_client import request_status_update
from app.agents.facilitator_agent import run_standup
from app.agents.person_agent import PersonAgent
from app.api.slack_mentions import extract_all_mentions, extract_mention
from app.config import settings
from app.memory.ingest_slack import handle_channel_message

app = App(token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret)


@app.event("message")
def handle_message_events(event, logger):
    # Ignore bot's own messages, edits, and non-plain messages (no subtype).
    if event.get("subtype") is not None:
        return
    try:
        handle_channel_message(
            channel_id=event.get("channel", ""),
            user_id=event.get("user", ""),
            text=event.get("text", ""),
        )
    except Exception:
        logger.exception("chat-archiver ingestion failed")


@app.command("/update")
def handle_update(ack, command, respond):
    ack()
    user_id = command["user_id"]
    text = command["text"].strip()
    if not text:
        respond("Usage: /update <what you did today>")
        return
    agent = PersonAgent(user_id)
    agent.record_update(text)
    respond("Got it — saved to your private memory.")


@app.command("/ask")
def handle_ask(ack, command, respond):
    ack()
    user_id = command["user_id"]
    question = command["text"].strip()
    if not question:
        respond("Usage: /ask <question>")
        return
    agent = PersonAgent(user_id)
    answer = agent.answer(question)
    respond(answer)


@app.command("/ask-person")
def handle_ask_person(ack, command, respond):
    ack()
    target_user_id, question = extract_mention(command["text"])
    if not target_user_id or not question:
        respond("Usage: /ask-person @teammate <question>")
        return
    roster = settings.a2a_roster()
    base_url = roster.get(target_user_id)
    if not base_url:
        respond(f"<@{target_user_id}> isn't in A2A_TEAM_ROSTER — can't reach their agent.")
        return
    try:
        answer = asyncio.run(request_status_update(base_url, question))
    except Exception as exc:  # noqa: BLE001 — surface the failure to the asker, don't crash the bot
        respond(f"Couldn't reach <@{target_user_id}>'s agent — {exc}")
        return
    respond(answer)


@app.command("/standup")
def handle_standup(ack, command, respond):
    ack()
    mentioned, remainder = extract_all_mentions(command["text"])
    absent = set(mentioned) | set(remainder.split())
    respond("Pulling status updates from the team...")
    summary = run_standup(absent=absent)
    respond(summary)


def main():
    SocketModeHandler(app, settings.slack_app_token).start()


if __name__ == "__main__":
    main()
