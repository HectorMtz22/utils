---
description: Brainstorm a new task, write a local spec, and file UTILS issue(s) on the Obsidian Kanban board
argument-hint: [short description of the task]
---

# /task-init — start a new task

Turn an idea into a local spec and one or more **UTILS** issues, ready for
`/task-implement`. This is the front half of the harness (see `HARNESS.md`):
`brainstorm → spec → issue(s)`. Issues live on the Obsidian Kanban board outside
the repo; specs/plans stay local and gitignored.

> Scaling up: for a broad goal that fans out into many linked issues, use
> **`/issues-init`** (epic decomposition) instead, then **`/task-run`** to build
> the backlog in dependency order.

Task description (may be empty — ask if so): **$ARGUMENTS**

## Tracker

Read `.claude/tracker.md` — the single source of truth for the issues folder
(`project_id`), the board file, the note/card format, and how to pick the next
id. Follow its format exactly. If the file is missing, tell the user to run
`/harness-setup` first; if the folder or board is missing, `/harness-bootstrap`.

## Steps

1. **Brainstorm.** Invoke `superpowers:brainstorming` and design the change with
   the user. Do not skip this even if the task seems small — the spec can be
   short. The brainstorming skill writes the spec to
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (local, gitignored) and
   gets the user's approval. Let it run its full flow.

2. **Plan into PR-sized chunks.** If the spec is bigger than one PR, use
   `superpowers:writing-plans` and split it into independent, PR-sized chunks —
   one issue each (this is what lets `/task-implement` run them in
   parallel). A single-PR task is just one issue. (For epic-scale work, prefer
   `/issues-init`, which also records the `blocked_by` links for you.)

3. **Determine labels per issue:**
   - **Project label** = the sub-project the work touches (`pdf_crop`,
     `music-lyrics`, `thermal-qr`, `pxe-boot`, or a new sub-project's dir name).
     If the work spans projects, ask the user which project the issue belongs
     to.
   - **Type label** = the conventional-commit type the chunk will land as
     (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`).

4. **Write each issue note** in the issues folder, per `.claude/tracker.md`:
   - Next id = highest existing `UTILS-<n>` + 1 (or `id_start`); filename
     `UTILS-<n>-<slug>.md`.
   - Frontmatter: `title` = imperative, conventional-commit-style summary, e.g.
     `feat(pdf_crop): add page-range presets`; `project`, `type`, `spec` (the
     local spec filename), `created`.
   - Body: problem, chosen approach, code map (files to touch), test list. Keep
     it tight — the spec is the contract.

5. **Add a card for each** at the bottom of the board's **Todo** lane:
   `- [ ] [[UTILS-<n>-<slug>]] #<project> #<type>`. Re-read the board first and
   change nothing else in it.

6. **Report** each created issue's identifier (e.g. `UTILS-12`) and tell the
   user they can run `/task-implement UTILS-12 …` next.

## Guardrails

- Specs/plans are **local-only** (`docs/superpowers/` is gitignored). Never
  commit them; the issue note carries only a pointer (`spec:`).
- One issue ≈ one PR. Prefer several small independent issues over one large one
  so implementation can parallelize.
- Don't write production code here — `/task-init` only plans and files issues.
