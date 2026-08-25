"""One-off / re-runnable backfill — sync existing channel history into
shared org memory.

`handle_channel_message` (ingest_slack.py) only fires on live Slack
`message` events, so anything posted before the bot was running (or
while it was down) never reaches org_shared. Run this to catch up.

Run:
    python -m app.memory.backfill_slack
"""
from __future__ import annotations

import sys
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.config import settings
from app.memory.ingest_slack import handle_channel_message


def main() -> None:
    if not settings.slack_bot_token:
        print("SLACK_BOT_TOKEN not set in .env — aborting.", file=sys.stderr)
        sys.exit(1)
    if not settings.slack_shared_knowledge_channel_id:
        print(
            "SLACK_SHARED_KNOWLEDGE_CHANNEL_ID not set in .env — aborting.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not settings.supermemory_shared_write_api_key:
        print(
            "SUPERMEMORY_SHARED_WRITE_API_KEY not set in .env — "
            "shared.ingest() will refuse to write. Set it before running.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = WebClient(token=settings.slack_bot_token)
    channel = settings.slack_shared_knowledge_channel_id

    cursor = None
    total = 0
    ingested = 0
    while True:
        try:
            resp = client.conversations_history(channel=channel, cursor=cursor, limit=200)
        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}", file=sys.stderr)
            sys.exit(1)

        messages = resp.get("messages", [])
        for msg in messages:
            # Skip bot messages, edits, thread-broadcast dupes, etc.
            if msg.get("subtype") is not None:
                continue
            total += 1
            try:
                permalink = client.chat_getPermalink(
                    channel=channel, message_ts=msg["ts"]
                ).get("permalink", "")
            except SlackApiError:
                permalink = ""
            result_id = handle_channel_message(
                channel_id=channel,
                user_id=msg.get("user", ""),
                text=msg.get("text", ""),
                permalink=permalink,
            )
            if result_id:
                ingested += 1
                print(f"ingested ts={msg['ts']} id={result_id}")
            time.sleep(0.3)  # stay under Supermemory + Slack rate limits

        if not resp.get("has_more"):
            break
        cursor = resp.get("response_metadata", {}).get("next_cursor")

    print(f"Done. {ingested}/{total} messages ingested into org_shared.")


if __name__ == "__main__":
    main()
