---
description: Decompose an epic into many linked UTILS issues on the Obsidian Kanban board, ready for /task-run
argument-hint: [short description of the epic / broad goal]
---

# /issues-init — decompose an epic into issues

Take a broad goal and fan it out into several **PR-sized UTILS issues** on the
Obsidian Kanban board, linked by dependency, ready for `/task-run`. This is `/task-init`
at _epic_ scale: where `/task-init` brainstorms one task, `/issues-init`
brainstorms the whole thing and files the batch. Specs stay local and gitignored;
issues (and their links) live in the issues folder.

Epic description (may be empty — ask if so): **$ARGUMENTS**

## Tracker

Read `.claude/tracker.md` for the issues folder, board, note/card format, and id
rule. If it's missing, tell the user to run `/harness-setup` first.

- **Grouping:** a parent **epic note** (`type: epic`, no board card) whose body
  links each child; each child sets `epic: <epic id>`.
- **Dependency links:** each child lists its blockers in `blocked_by: [...]`.

## Steps

1. **Brainstorm at epic altitude.** Invoke `superpowers:brainstorming`, but aim
   one level up: agree on scope (in / out), then **decompose** the epic into
   independent, PR-sized chunks and their dependency order. For each chunk pin
   down: an imperative name, the **type** (`feat`/`fix`/`refactor`/`test`/`docs`/
   `chore`), the **project** it touches (`pdf_crop`, `music-lyrics`, `thermal-qr`,
   `pxe-boot`), a **code map** (files to touch), a test list, and **which sibling
   chunks block it**. Prefer more small independent chunks — disjoint code maps
   are what let `/task-run` parallelize them.

2. **Write one epic spec** to
   `docs/superpowers/specs/YYYY-MM-DD-<epic>-design.md` (local, gitignored), with
   a section per chunk. Get the user's approval on it (the brainstorming skill's
   normal gate). Each chunk section holds its own code map + test list — those get
   copied into the issue so `/task-run` can read them without opening the spec.

3. **Draft the issue bodies.** For **3+ chunks**, dispatch one drafting agent per
   chunk (`superpowers:dispatching-parallel-agents`, single message) to write that
   chunk's issue description (problem, approach, code map, test list) from the epic
   spec, and **report the text back**. Agents draft only — they do **not** touch
   the issues folder. For **≤2 chunks**, draft inline; don't spin up agents for that.

4. **File the batch (you, the parent, do every tracker write):**
   - Allocate consecutive ids (highest existing + 1, …) for the epic and every
     chunk up front, so `blocked_by` and epic links can reference them.
   - Write the **epic note** (`type: epic`) named for the goal, its body linking
     each child as `[[UTILS-<n>-<slug>]]` plus a pointer to the epic spec.
   - Write one **issue note** per chunk: `title` = conventional-commit-style
     summary; `project`, `type`, `epic`, `blocked_by` (per the decomposition's
     dependency order), `spec` (epic spec + section); body = the drafted text.
   - Append one **Todo card** per chunk (not the epic), in dependency order, in a
     single edit of the re-read board.

5. **Report** the parent epic and every issue identifier (e.g. `UTILS-31 …`), the
   dependency graph (what blocks what, what's parallel), and tell the user to run
   **`/task-run`** next (or `/task-implement <ids>` to hand-pick).

## Guardrails

- **Specs/plans are local-only** (`docs/superpowers/` is gitignored). Never commit
  them; the issue description carries a pointer, nothing more.
- **One chunk ≈ one PR.** Bias toward several small, disjoint issues over one big
  one — that's what makes `/task-run`'s parallel batches possible.
- **The parent centralizes tracker writes.** Drafting agents return text only;
  you write the epic, the issue notes, and the board cards.
- **Don't write production code here** — `/issues-init` only plans and files.
- **If the issues folder is missing** (e.g. Syncthing hasn't synced it to this
  machine), say so and offer to run `/harness-bootstrap` or proceed untracked:
  write the epic spec now and file the issues later.
