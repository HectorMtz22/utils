---
description: Implement Plane issue(s) from UTILS in worktrees with parallel agents, TDD, review, and PR
argument-hint: [UTILS-12 UTILS-13 …] (optional; lists Todo issues if omitted)
---

# /task-implement — implement Plane issue(s)

Take one or more **Plane** issues and drive them through the back half of the
harness (see `HARNESS.md`): `worktree → TDD → verify → review → PR`. Always use
worktrees, always use superpowers, always conventional commits. Multiple issues
run as **parallel agents**, one worktree each.

> To build the **whole backlog** in auto-planned dependency order instead of
> naming issues, use **`/task-run`** — it wraps this same machinery with an
> ordering layer.

Requested issues (may be empty): **$ARGUMENTS**

## Plane coordinates

Read `project_code` (`UTILS`) and `project_id` from `.claude/tracker.md` — the
single source of truth for tracker config. If that file is missing, tell the user
to run `/harness-setup` first.

- Resolve states **by name at runtime** via `mcp__plane__list_states`:
  **"Todo"**, **"In Progress"**, **"In Review"**, **"Done"**. Plane ships without
  **In Review** — `/harness-bootstrap` creates it (or create it once by hand).

## Steps

1. **Resolve the work list.**
   - If issue identifiers were passed, fetch each with
     `mcp__plane__retrieve_work_item_by_identifier`.
   - If none were passed, `mcp__plane__list_work_items` filtered to the **Todo**
     state, show them, and ask the user which to implement.
   - For each issue read the description and open the linked local spec under
     `docs/superpowers/specs/` — that's the contract.

2. **Move each issue to In Progress** with `mcp__plane__update_work_item`
   (`state` = the In Progress id).

3. **One worktree per issue.** Use `superpowers:using-git-worktrees`. Branch
   name = `<type>/<scope>-<topic>` from the issue's type + project labels, e.g.
   `feat/pdf_crop-range-presets`. Worktrees go under `.worktrees/` (gitignored).

4. **Dispatch implementation agents.**
   - Use `superpowers:subagent-driven-development`; each subagent follows
     `superpowers:test-driven-development` (red → green → refactor, full suite).
   - **More than one issue → `superpowers:dispatching-parallel-agents`**: dispatch
     all agents in a **single message** so they run concurrently, one per
     worktree. Only parallelize issues that touch **disjoint files**; if two
     issues overlap a module, sequence them instead.
   - Give each agent: its Plane issue + spec, its worktree path, the code map,
     "do not touch the main checkout or sibling worktrees", and "report back
     briefly".

5. **Verify (parent).** For each branch run
   `superpowers:verification-before-completion`: inspect the diff and run the
   full project suite. Confirm real green output before continuing.

6. **Code review (parent).** Run `superpowers:requesting-code-review` per branch.
   **Report findings to the user grouped by severity (Critical / Important /
   Minor) and ask which to fix — do NOT auto-fix.** Apply only what the user
   approves, then re-review.

7. **PR + close out — automatic.** As soon as a branch is **verified, green,
   committed, and clean** (no Important+ findings outstanding, full suite
   passing, working tree clean), **open its PR without waiting to be asked**:
   - Push the branch and open a PR with a conventional-commit title
     (`<type>(<scope>): …`), one feature per PR. Commits drop the
     `Co-Authored-By: Claude` trailer; PR body has no "Generated with Claude
     Code" footer.
   - Move the Plane issue to **In Review** (the PR is open, not merged) with
     `mcp__plane__update_work_item`; set it to **Done** when the PR merges.
   - The auto-open gate is the *only* thing that's hands-off: you still
     **report review findings and wait for the user to choose fixes** (step 6)
     before a branch counts as verified.

## Guardrails

- **Branch off `main`; never commit to `main`.** Commit at green points so the
  branch is PR-ready, then **open the PR automatically** once it's verified,
  green, committed, and clean (step 7) — no need to ask. (Fix decisions in
  step 6 still wait for the user.)
- **Worktrees always** — implementation never happens in the main checkout.
- `.worktrees/` and `docs/superpowers/` are gitignored; never `git add` them.
- Keep parallel agents on disjoint files; sequence anything that overlaps.
