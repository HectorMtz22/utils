---
description: Decompose an epic into many linked Plane issues in UTILS, ready for /task-run
argument-hint: [short description of the epic / broad goal]
---

# /issues-init — decompose an epic into issues

Take a broad goal and fan it out into several **PR-sized Plane issues** in the
`UTILS` project, linked by dependency, ready for `/task-run`. This is `/task-init`
at _epic_ scale: where `/task-init` brainstorms one task, `/issues-init`
brainstorms the whole thing and files the batch. Specs stay local and gitignored;
issues (and their links) live in Plane.

Epic description (may be empty — ask if so): **$ARGUMENTS**

## Plane coordinates

Read `project_code` (`UTILS`) and `project_id` from `.claude/tracker.md`. If that
file is missing, tell the user to run `/harness-setup` first.

- Resolve states, labels, and the current cycle **by name at runtime** — don't
  hardcode UUIDs:
  - `mcp__plane__list_states` → pick the state named **"Todo"**.
  - `mcp__plane__list_labels` → map label names to IDs.
  - `mcp__plane__list_cycles` → pick the cycle whose date range contains today.
- **Grouping:** a parent **epic** via `mcp__plane__create_epic`.
- **Dependency links:** **blocks / blocked-by** relations via
  `mcp__plane__create_work_item_relation`.

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
   Plane. For **≤2 chunks**, draft inline; don't spin up agents for that.

4. **File the batch (you, the parent, do every Plane write):**
   - Create the parent **epic** (`mcp__plane__create_epic`) named for the goal.
   - One work item per chunk with `mcp__plane__create_work_item`: `project_id` =
     the UTILS id; `state` = **Todo**; `labels` = `[project label id, type label
     id]`; `name` = conventional-commit-style summary; `description_html` = the
     drafted body plus a pointer to the epic spec section. Link each to the parent
     epic. If a project label doesn't exist yet, create it with
     `mcp__plane__create_label`.
   - **Add every issue to the current weekly cycle** with
     `mcp__plane__add_work_items_to_cycle`.
   - Set **blocks / blocked-by** relations between chunks per the decomposition's
     dependency order (`mcp__plane__create_work_item_relation`).

5. **Report** the parent epic and every issue identifier (e.g. `UTILS-31 …`), the
   dependency graph (what blocks what, what's parallel), and tell the user to run
   **`/task-run`** next (or `/task-implement <ids>` to hand-pick).

## Guardrails

- **Specs/plans are local-only** (`docs/superpowers/` is gitignored). Never commit
  them; the issue description carries a pointer, nothing more.
- **One chunk ≈ one PR.** Bias toward several small, disjoint issues over one big
  one — that's what makes `/task-run`'s parallel batches possible.
- **The parent centralizes Plane writes.** Drafting agents return text only; you
  create the epic, issues, relations, and cycle assignments.
- **Don't write production code here** — `/issues-init` only plans and files.
- **If the Plane MCP server is unreachable**, say so and offer to proceed
  untracked: write the epic spec now and file the issues later.
