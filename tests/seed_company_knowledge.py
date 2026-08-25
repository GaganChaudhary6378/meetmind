"""Seed script — post test company-knowledge messages to the configured
Slack shared-knowledge channel (SLACK_SHARED_KNOWLEDGE_CHANNEL_ID).

Use to test the 1.3 shared org memory ingestion path (chat archiver ->
org_shared container tag) and later query/leak tests (1.6).

Run:
    python -m tests.seed_company_knowledge
"""
from __future__ import annotations

import sys
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.config import settings

MESSAGES = [
    (
        ":rocket: *Auth service migration — 2026-09-01*\n"
        "Auth token schema moves to new JWT `sub` claim format on "
        "2026-09-01. Old format deprecated 2026-09-15. Owner: Priya "
        "(backend team). Rollback: feature flag `auth_v2_enabled`, "
        "default off until QA sign-off. Questions: #auth-migration."
    ),
    (
        ":bar_chart: *Q3 planning freeze — 2026-08-28*\n"
        "Feature branches must merge by 2026-08-28 EOD for Q3 planning "
        "review. Anything unmerged after that slips to Q4. Owner: "
        "engineering leads. Exceptions need director sign-off."
    ),
    (
        ":lock: *New PTO policy — effective 2026-09-15*\n"
        "PTO requests now go through the HR portal, not Slack DM to "
        "manager. Manager still approves, portal just tracks it. "
        "Owner: People Ops. Old process retired 2026-09-15."
    ),
    (
        ":satellite: *Jira connector — Phase 5 kickoff target*\n"
        "Jira connector work (breakdown.md 5.1) targeted to start after "
        "phase 4 live-pilot sign-off, no fixed date yet. Owner: "
        "platform team. Feeds org_shared container tag, same as "
        "codebase indexer and chat archiver."
    ),
    (
        ":test_tube: *Test fact for leak-test (1.6)*\n"
        "Canary value: the office plant on the 4th floor is named "
        "Gerald. This fact lives ONLY in org_shared — use it to "
        "confirm a private agent query never surfaces org_shared data "
        "unless it explicitly queries the shared tag, and vice versa."
    ),
    (
        ":shield: *Security policy — data handling & access*\n"
        "1. All laptops must run full-disk encryption and MDM enrollment "
        "within 48 hours of issue. Owner: IT Security.\n"
        "2. Production DB access requires a signed access request in the "
        "#access-requests channel, approved by the on-call lead, expires "
        "after 7 days.\n"
        "3. No customer PII in Slack, email, or local files — use the "
        "masked-data sandbox for debugging. Violations get logged and "
        "escalated to the security lead automatically.\n"
        "4. Report suspected breaches to security@company immediately — "
        "do not wait for confirmation. SLA: security team acks within "
        "30 minutes, 24/7.\n"
        "5. Password manager (1Password) mandatory for all service "
        "credentials; personal password reuse across systems is a "
        "fireable policy violation.\n"
        "Effective 2026-07-01. Owner: Security team. Review cycle: "
        "every 6 months."
    ),
    (
        ":airplane: *Travel & expense policy*\n"
        "1. Flights: economy under 6 hours, premium economy allowed "
        "over 6 hours with manager approval.\n"
        "2. Hotels: cap $250/night in tier-1 cities ($180 elsewhere), "
        "book through the Navan portal, not direct.\n"
        "3. Meals: $75/day per diem, no receipts needed under $75; "
        "itemized receipt required above that.\n"
        "4. Client entertainment: pre-approval required above $200, "
        "submit via Expensify with client name + business purpose.\n"
        "5. Reimbursement turnaround: 5-10 business days after "
        "submission; late submissions (>60 days after travel) may be "
        "denied.\n"
        "Owner: Finance. Questions: #finance-help."
    ),
    (
        ":house: *Remote work & hybrid policy*\n"
        "1. Default: 3 days/week in-office (Tue/Wed/Thu) for hybrid "
        "roles; fully remote roles exempt, set at offer stage.\n"
        "2. Core hours 10am-4pm local time — meetings should stay "
        "inside this window across time zones where possible.\n"
        "3. Home office stipend: $500 one-time, $50/month ongoing for "
        "internet, claimed via Expensify code REMOTE-STIPEND.\n"
        "4. Working from a different country for >30 consecutive days "
        "needs People Ops + legal sign-off first (tax/visa reasons) — "
        "do not book travel before approval lands.\n"
        "5. Async-first for cross-timezone teams: default to written "
        "updates over live meetings when a 6+ hour gap exists.\n"
        "Effective 2026-06-01. Owner: People Ops."
    ),
    (
        ":mag: *Code review & merge standards*\n"
        "1. Every PR needs 1 approval minimum, 2 for changes touching "
        "auth, billing, or data-deletion paths.\n"
        "2. No self-merge, even with approval, except documented "
        "hotfixes (must be tagged `hotfix` and posted in "
        "#eng-incidents within 1 hour).\n"
        "3. CI must be green — no merging on red or skipped checks, no "
        "exceptions.\n"
        "4. PRs open >5 business days without activity get auto-flagged "
        "stale and pinged to the author + reviewer.\n"
        "5. Squash-merge default; keep merge commits only for release "
        "branches.\n"
        "Owner: Eng leads. Doc: internal wiki > Engineering > Git "
        "Workflow."
    ),
    (
        ":rotating_light: *Incident response process*\n"
        "1. Severity levels: SEV1 (full outage, customer-facing) — page "
        "on-call immediately, exec notified within 15 min. SEV2 "
        "(degraded, partial impact) — page on-call, exec notified "
        "within 1 hour. SEV3 (minor, internal) — ticket, no page.\n"
        "2. Incident commander role rotates weekly, posted in "
        "#incident-response pinned message.\n"
        "3. Postmortem required for all SEV1/SEV2 within 5 business "
        "days, blameless format, owner assigns action items with due "
        "dates.\n"
        "4. Status page (status.company.com) updated within 10 minutes "
        "of a confirmed SEV1 — comms lead owns this, not the IC.\n"
        "5. On-call rotation: 1 week shifts, compensated per the "
        "on-call pay policy (see #people-ops-faq).\n"
        "Owner: SRE team. Runbook: internal wiki > Ops > Incidents."
    ),
    (
        ":calendar: *2026 holiday calendar & office closures*\n"
        "Observed company-wide (US offices): New Year's Day (Jan 1), "
        "Memorial Day (May 25), Juneteenth (Jun 19), Independence Day "
        "(Jul 4, observed Jul 3), Labor Day (Sep 7), Thanksgiving "
        "(Nov 26-27), Winter break (Dec 24-Jan 1, office fully closed).\n"
        "Regional offices: check the regional calendar in the wiki, "
        "dates differ for non-US locations.\n"
        "Floating holidays: 2 per year, use anytime with manager "
        "approval, do not roll over to next year.\n"
        "Owner: People Ops."
    ),
    (
        ":handshake: *New-hire onboarding checklist (first 2 weeks)*\n"
        "Day 1: laptop setup + MDM enrollment (IT), Slack/email/1Password "
        "provisioned (IT), buddy assigned (manager).\n"
        "Week 1: complete security training (mandatory, 45 min, in "
        "Learning portal), read Engineering Git Workflow doc, shadow "
        "one on-call handoff.\n"
        "Week 2: first small PR merged with buddy review, 1:1 with "
        "skip-level manager scheduled, benefits enrollment deadline is "
        "day 30 — do not miss it, no exceptions after.\n"
        "Owner: People Ops + hiring manager jointly. Checklist lives in "
        "the onboarding Notion doc."
    ),
]


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

    client = WebClient(token=settings.slack_bot_token)
    channel = settings.slack_shared_knowledge_channel_id

    for i, text in enumerate(MESSAGES, start=1):
        try:
            client.chat_postMessage(channel=channel, text=text)
            print(f"[{i}/{len(MESSAGES)}] posted OK")
        except SlackApiError as e:
            print(f"[{i}/{len(MESSAGES)}] FAILED: {e.response['error']}", file=sys.stderr)
        time.sleep(1)  # stay well under Slack's rate limit


if __name__ == "__main__":
    main()
