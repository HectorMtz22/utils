---
description: Read the UTILS backlog, plan a parallel/sequential order, and drive it through /task-implement
argument-hint: [UTILS-12 …] or a label (optional; defaults to all Todo issues)
---

# /task-run — run the backlog, auto-ordered

`/task-implement` scaled to the whole backlog. Where `/task-implement` builds the
issues **you** name in the order you give, `/task-run` reads the Plane board,
works out which issues can build **in parallel** and which must go **in
sequence**, shows you that plan, then runs the same worktree → TDD → verify →
review → PR machinery batch by batch. Same engine, plus an ordering layer.

Requested scope (may be empty): **$ARGUMENTS**

## Plane coordinates

Read `project_code` (`UTILS`) and `project_id` from `.claude/tracker.md`. If that
file is missing, tell the user to run `/harness-setup` first.

- Resolve states **by name at runtime** via `mcp__plane__list_states`:
  **"Todo"**, **"In Progress"**, **"In Review"**, **"Done"**.
- Read dependency links via `mcp__plane__list_work_item_relations`
  (**blocks / blocked-by**).

## Steps

1. **Resolve the work list.**
   - No args → `mcp__plane__list_work_items` filtered to the **Todo** state.
   - Args that look like identifiers (`UTILS-…`) →
     `mcp__plane__retrieve_work_item_by_identifier` for each.
   - An arg that names a label → filter Todo issues to it.
   - For each issue, read the description and open the linked local spec under
     `docs/superpowers/specs/` to extract its **code map** (the files it touches).

2. **Build the execution plan from two signals.**
   - **Plane relations** — if A **blocks** B, B waits for A.
   - **File-overlap** — if two issues' code maps share any file, they can't run
     concurrently.
   - Sequence a pair if **either** signal says they collide; otherwise they can
     share a batch. Topologically sort into ordered **batches**: a batch is a set
     of issues with no unmet blocker and no pairwise file-overlap. Batches run in
     order; issues **within** a batch run in parallel.

3. **Show the plan and get approval.** Lay out the batches, what runs in parallel,
   and **why** each sequenced pair is sequenced (blocks-relation vs. file-overlap).
   Wait for the user to approve or adjust before dispatching anything.

4. **Execute batch by batch** — reuse `/task-implement`'s mechanics per issue:
   - Move each issue in the batch to **In Progress**
     (`mcp__plane__update_work_item`); create one worktree each
     (`superpowers:using-git-worktrees`, `<type>/<scope>-<topic>` under
     `.worktrees/`).
   - Dispatch the batch's implementation agents in a **single message**
     (`superpowers:dispatching-parallel-agents` + `subagent-driven-development`),
     each following TDD (red → green → refactor, full suite). Give each its issue +
     spec, worktree path, code map, and "don't touch the main checkout or sibling
     worktrees".
   - **Verify (parent):** inspect each diff and run the full project suite
     (`superpowers:verification-before-completion`).
   - **Code review (parent):** run `superpowers:requesting-code-review` per branch.
     **Report findings grouped by severity (Critical / Important / Minor) and ask
     which to fix — do NOT auto-fix.** Apply only what the user approves, re-review.
   - **Commit + PR (parent):** worktree agents run from the main checkout, so the
     **parent** commits at green points, pushes, and **opens the PR automatically**
     once a branch is verified, green, committed, and clean (no Important+
     findings). Conventional-commit title; **no `Co-Authored-By: Claude` trailer
     and no "Generated with Claude Code" footer.** Move the issue to **In Review**
     (→ **Done** when the PR merges).
   - **Advance to the next batch — mind what "blocker resolved" means.** Every
     worktree branches off `main` (step 4), so an issue can only build on top of
     a blocker whose code is actually on `main`. Therefore a later-batch issue
     that is **blocked** (blocks-relation) must wait until its blocker's PR is
     **merged into `main`**, not merely PR-open — building on a PR-open blocker
     would defeat the ordering. Batches separated only by **file-overlap** (no
     dependency) may start as soon as the prior batch is PR-open. If merges lag
     behind the batches, pause and tell the user which issues are waiting on a
     merge.

5. **Report a run summary** — issues built, PRs opened, and anything left blocked
   or skipped.

## Guardrails

- **Report review findings; don't auto-fix.** The auto-open-PR gate is the only
  hands-off step; the fix decision always waits for the user.
- **The parent does all commits/PRs and Plane writes** — worktree agents only
  implement and report back.
- **Worktrees always; never commit to `main`.** Keep a batch's parallel agents on
  **disjoint files** — that's exactly what the plan guarantees.
- **If the Plane MCP server is unreachable**, say so and offer to proceed with
  issue IDs the user names (file-overlap-only ordering) or to stop.
