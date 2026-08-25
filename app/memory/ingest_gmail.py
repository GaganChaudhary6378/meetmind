"""Gmail transcript ingestion — task M1.

Pulls past meeting-transcript emails from one connected Gmail mailbox
(per-user OAuth, not domain-wide delegation — reads only the connecting
user's inbox) and writes them into shared org memory via the same
write-gated path as Slack (`app/memory/shared.py`).

`GMAIL_TRANSCRIPT_QUERY` defaults to Google Meet's known auto-transcript
sender (`from:noreply-meet@google.com`).

Gmail has no live-push listener wired up here (would need a separate
Pub/Sub subscription) — this module only supports a one-off / re-runnable
backfill scan, same role as `backfill_slack.py` plays for Slack.

Run:
    python -m app.memory.ingest_gmail
"""
from __future__ import annotations

import base64
import sys
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.memory import shared

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _gmail_client():
    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


def _extract_text(payload: dict) -> str:
    """Pull plain-text body out of a Gmail message payload.

    Walks multipart messages depth-first for the first text/plain part;
    falls back to the top-level body if the message isn't multipart.
    """
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []) or []:
        text = _extract_text(part)
        if text:
            return text

    data = payload.get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def handle_message(message_id: str, sender: str, subject: str, body: str) -> str | None:
    """Ingest one Gmail message as a shared-memory transcript record.

    Returns the new shared-memory id, or None if the message had no
    usable body text (ignored, not an error).
    """
    if not body.strip():
        return None

    content = f"Subject: {subject}\n\n{body}"
    permalink = f"https://mail.google.com/mail/u/0/#all/{message_id}"
    return shared.ingest(
        content=content,
        source="gmail_transcript_ingest",
        metadata={"gmail_message_id": message_id, "gmail_sender": sender, "permalink": permalink},
    )


def main() -> None:
    if not settings.gmail_client_id or not settings.gmail_client_secret or not settings.gmail_refresh_token:
        print(
            "GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN not set "
            "in .env — aborting.",
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

    service = _gmail_client()
    query = settings.gmail_transcript_query

    total = 0
    ingested = 0
    page_token = None
    while True:
        try:
            resp = (
                service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=100)
                .execute()
            )
        except HttpError as e:
            print(f"Gmail API error: {e}", file=sys.stderr)
            sys.exit(1)

        for msg_ref in resp.get("messages", []):
            total += 1
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_ref["id"], format="full")
                    .execute()
                )
            except HttpError as e:
                print(f"skip {msg_ref['id']}: {e}", file=sys.stderr)
                continue

            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            sender = headers.get("from", "")
            subject = headers.get("subject", "")
            body = _extract_text(msg.get("payload", {}))

            result_id = handle_message(msg_ref["id"], sender, subject, body)
            if result_id:
                ingested += 1
                print(f"ingested id={msg_ref['id']} shared_id={result_id}")
            time.sleep(0.3)  # stay under Supermemory + Gmail rate limits

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"Done. {ingested}/{total} messages ingested into org_shared.")


if __name__ == "__main__":
    main()
