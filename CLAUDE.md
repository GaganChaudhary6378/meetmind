# CLAUDE.md — Personalised Meeting Agents

Instructions for any AI coding agent (Claude Code or other) working in
this repo. Follow these on top of default behavior.

## Project docs — read before starting work

- `plan.md` — full design, decided answers to open questions.
- `breakdown.md` — task-by-task build list, phase by phase.
- `progress.md` — current build status, task by task.
- `README.md` — how to set up and run the app.

## Rule: after finishing any implementation task, update these

Do not treat a task as done until every file below that applies has
been updated in the same change. Do not create a separate doc for
this — update the four files that already exist.

1. **`progress.md`** — mark the task `done`, `in progress`, or leave
   `not started`. Update the file/note columns if new files were
   touched. Update the phase-status line at the bottom of each phase
   table. Update "Last updated" date at the bottom of the file.

2. **`README.md`** —
   - New command/script to run → add a numbered section with the
     exact run command.
   - New env var required → add a row to the `.env` table in Setup.
   - New file added under `app/` or `tests/` → add it to Project
     layout with a one-line comment.
   - Section numbers stay sequential — renumber if inserting mid-file.

3. **`breakdown.md`** —
   - If a task's stack choice changed from what's written, update
     the **Stack** line for that task.
   - If a new open item surfaces (a decision not yet made), add it
     under "Open items — stack not yet decided."
   - If an open item gets resolved, strike it through
     (`~~text~~ — resolved: ...`) like the Vector DB line already
     shows, don't delete it — keeps the decision trail.

4. **`.env.example`** — any new setting added to `app/config.py` gets
   a matching commented entry here with a one-line explanation of
   where to get the real value. Never put a real secret in this file.

## Rule: config changes

All env vars are read once, in `app/config.py`, nowhere else. A new
setting means: add the field to `Settings` in `config.py`, add the row
to `.env.example`, add the row to the README `.env` table. All three
or none — don't add a var to only one of the three.

## Rule: don't break the memory boundary

`app/memory/private.py` (per-person, `user_<id>` tag) and
`app/memory/shared.py` (`org_shared` tag, write-gated to the scoped
key) enforce the private/shared isolation at the data layer. Any new
code that writes memory must go through one of these two modules, not
call the Supermemory client directly. Task 1.6 (cross-person leak
test) is the standing gate — if you touch either module, re-run the
leak test before calling the change done.

## Rule: SDK version drift

`supermemory` SDK has moved methods before (`client.memories.add` →
`client.add`, see git history / progress.md phase 1 notes). If a
Supermemory call throws `AttributeError`, check the installed
version's actual client surface (`python -c "from supermemory import
Supermemory; print(dir(Supermemory(api_key='x')))"`) before assuming
the code is wrong — the wrapper in `app/memory/client.py` is the only
place that constructs the client, fix call sites in
`private.py`/`shared.py`/`pipeline.py` to match.

## Rule: phase gates

Do not start Phase 2 work until task 1.6 (cross-person leak test) is
marked `done` in `progress.md`. Do not start Phase 4 (live meeting
presence) until Phases 1–3 are solid — plan.md §5 flags this as the
step where a wrong answer gets heard live, in someone's name.
