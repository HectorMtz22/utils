---
description: Choose the issue tracker (this repo uses an Obsidian Kanban folder) and (re)write .claude/tracker.md
argument-hint: (none; interactive)
---

# /harness-setup — configure the tracker

One-time, **offline** setup. Asks which tracker the harness should use and writes
`.claude/tracker.md`. Run `/harness-bootstrap` after this to create the folder
and board.

> This repo is configured for an **Obsidian Kanban** folder
> (`~/tracker/issues/utils`, board `Utils.md`, ids `UTILS-<n>`), synced with
> Syncthing. You only need this command to change trackers or regenerate the
> file.

## Steps

1. **Ask which tracker** (default **Obsidian Kanban**):
   `[Obsidian Kanban]` / `GitHub Issues` / `other`.

2. **Ask the tracker-specific fields** (accept defaults unless overridden):
   - `project_code` — short identifier used in issue ids (`UTILS`).
   - `project_id` — the issues folder (`~/tracker/issues/utils`); for another
     tracker, its project id or slug.
   - `board` (`Utils.md`) and `vault_root` (`~/tracker`) — Obsidian Kanban only.
     `project_id` must be inside `vault_root`, or Obsidian won't show it.
   - `id_start` — first id when the folder is empty (`100`).
   - `has_cycles` — `false` (the board lanes are the workflow).

3. **Write `.claude/tracker.md`** with the chosen values, keeping the existing
   key set and the format sections (issue notes, board, Done ← merged) — the
   other commands follow those sections literally. Overwrite if it exists.

4. **Report** the written values and tell the user to run `/harness-bootstrap`
   next.

## Guardrails

- No network calls here — this command only writes the local config file.
- Keep the exact key set so `/harness-bootstrap`, `/task-init`, `/issues-init`,
  `/task-implement`, and `/task-run` can read it.
- Switching away from Obsidian Kanban means rewriting the tracker steps in those
  commands too; say so rather than leaving them pointing at the old tracker.
