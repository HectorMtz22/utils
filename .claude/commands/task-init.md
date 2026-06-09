---
description: Brainstorm a new task, write a local spec, and file Plane issue(s) in UTILS
argument-hint: [short description of the task]
---

# /task-init — start a new task

Turn an idea into a local spec and one or more **Plane** issues, ready for
`/task-implement`. This is the front half of the harness (see `HARNESS.md`):
`brainstorm → spec → Plane issue(s)`. Issues live in Plane; specs/plans stay
local and gitignored.

Task description (may be empty — ask if so): **$ARGUMENTS**

## Plane coordinates

- Project **Utils**, identifier `UTILS`, `project_id`
  `43bbc122-c9fe-469e-9379-db02d132a5c9`.
- Resolve states and labels **by name at runtime** — don't hardcode UUIDs:
  - `mcp__plane__list_states` → pick the state named **"Todo"**.
  - `mcp__plane__list_labels` → map label names to IDs.

## Steps

1. **Brainstorm.** Invoke `superpowers:brainstorming` and design the change with
   the user. Do not skip this even if the task seems small — the spec can be
   short. The brainstorming skill writes the spec to
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (local, gitignored) and
   gets the user's approval. Let it run its full flow.

2. **Plan into PR-sized chunks.** If the spec is bigger than one PR, use
   `superpowers:writing-plans` and split it into independent, PR-sized chunks —
   one Plane issue each (this is what lets `/task-implement` run them in
   parallel). A single-PR task is just one issue.

3. **Determine labels per issue:**
   - **Project label** = the sub-project the work touches (`pdf_crop`,
     `music-lyrics`, `thermal-qr`, `pxe-boot`). If the right project label does
     not exist yet (new sub-project), create it with
     `mcp__plane__create_label`. If the work spans projects, ask the user which
     project the issue belongs to.
   - **Type label** = the conventional-commit type the chunk will land as
     (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`).

4. **Create the Plane issue(s)** with `mcp__plane__create_work_item`:
   - `project_id`: the UTILS id above.
   - `name`: imperative, conventional-commit-style summary, e.g.
     `feat(pdf_crop): add page-range presets`.
   - `state`: the **Todo** state id.
   - `labels`: `[project label id, type label id]`.
   - `description_html`: problem, chosen approach, code map (files to touch),
     test list, and the local spec filename
     (`docs/superpowers/specs/...`). Keep it tight — the spec is the contract.

5. **Report** each created issue's identifier (e.g. `UTILS-12`) and tell the
   user they can run `/task-implement UTILS-12 …` next.

## Guardrails

- Specs/plans are **local-only** (`docs/superpowers/` is gitignored). Never
  commit them and never put them anywhere but Plane's issue description as a
  pointer.
- One issue ≈ one PR. Prefer several small independent issues over one large one
  so implementation can parallelize.
- Don't write production code here — `/task-init` only plans and files issues.
