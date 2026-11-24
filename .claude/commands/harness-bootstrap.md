---
description: Provision the tracker — create the UTILS issues folder and Kanban board if missing (idempotent)
argument-hint: (none)
---

# /harness-bootstrap — provision the tracker

**Idempotent** setup. Reads `.claude/tracker.md` and creates anything the harness
assumes but that doesn't exist yet. Safe to re-run — never overwrites an existing
note or board. Run `/harness-setup` first if `.claude/tracker.md` is missing.

## Read config

Load `.claude/tracker.md`: `tracker` (`obsidian-kanban`), `project_code`
(`UTILS`), `project_id` (the issues folder), `board`, `vault_root`.

## Steps (each is "check, then create only if missing")

1. **Vault.** Confirm `<vault_root>/.obsidian/` exists. If not, warn that
   Obsidian won't show the board until `vault_root` is opened as a vault
   (Obsidian → *Open folder as vault*), and continue — the agents only need the
   files.

2. **Issues folder.** `mkdir -p <project_id>`.

3. **Board.** If `<project_id>/<board>` is missing, write it with the four empty
   lanes — **Todo**, **In Progress**, **In Review**, **Done** (`**Complete**`
   under Done) — using the exact format in `.claude/tracker.md`. Set the
   settings block's `new-note-folder` to `project_id` relative to `vault_root`
   (`issues/utils`), so *New note from card* in Obsidian lands in the right
   folder. If the board exists, only check that all four lane headings are
   present and add any missing one (never reorder or touch cards).

4. **Syncthing ignores.** Ensure `<vault_root>/.stignore` contains (append only
   the missing lines):
   ```
   .obsidian/workspace*.json
   .trash
   .DS_Store
   *.swp
   *~
   ```
   `workspace.json` changes on every click in Obsidian and is the usual source
   of sync conflicts.

5. **Report** what was created vs. already present, per step. Remind the user
   that adding `vault_root` as a Syncthing folder is done in Syncthing itself.

## Guardrails

- **Idempotent**: check before create; never overwrite or reformat an existing
  board or note.
- Don't edit Obsidian's or Syncthing's own config files — tell the user what to
  change instead.
