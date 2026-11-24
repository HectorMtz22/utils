---
description: Read the UTILS backlog, plan a parallel/sequential order, and drive it through /task-implement
argument-hint: [UTILS-100 …] or a project/type tag (optional; defaults to all Todo issues)
---

# /task-run — run the backlog, auto-ordered

`/task-implement` scaled to the whole backlog. Where `/task-implement` builds the
issues **you** name in the order you give, `/task-run` reads the Kanban board,
works out which issues can build **in parallel** and which must go **in
sequence**, shows you that plan, then runs the same worktree → TDD → verify →
review → PR machinery batch by batch. Same engine, plus an ordering layer.

Requested scope (may be empty): **$ARGUMENTS**

## Tracker

Read `.claude/tracker.md` for the issues folder, board, note/card format, and how
to move a card. If it's missing, tell the user to run `/harness-setup` first.

- States are the board lanes: **Todo**, **In Progress**, **In Review**, **Done**.
- Dependency links are each note's `blocked_by: [...]`.

## Steps

0. **Sync merged PRs.** Per `.claude/tracker.md` ("Done ← merged"), move every
   **In Review** card whose PR has merged to **Done** — this is what unblocks
   dependents.

1. **Resolve the work list.**
   - No args → every card in the board's **Todo** lane.
   - Args that look like identifiers (`UTILS-…`) → those notes.
   - An arg that names a tag (`pdf_crop`, `fix`, …) → Todo cards carrying it.
   - For each issue, read the note and open the linked local spec under
     `docs/superpowers/specs/` to extract its **code map** (the files it touches).

2. **Build the execution plan from two signals.**
   - **`blocked_by`** — if B lists A, B waits for A (a blocker already in
     **Done** is satisfied).
   - **File-overlap** — if two issues' code maps share any file, they can't run
     concurrently.
   - Sequence a pair if **either** signal says they collide; otherwise they can
     share a batch. Topologically sort into ordered **batches**: a batch is a set
     of issues with no unmet blocker and no pairwise file-overlap. Batches run in
     order; issues **within** a batch run in parallel.

3. **Show the plan and get approval.** Lay out the batches, what runs in parallel,
   and **why** each sequenced pair is sequenced (`blocked_by` vs. file-overlap).
   Wait for the user to approve or adjust before dispatching anything.

4. **Execute batch by batch** — reuse `/task-implement`'s mechanics per issue:
   - Move each card in the batch to **In Progress** (one board edit); create one
     worktree each
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
     and no "Generated with Claude Code" footer.** Set the note's `pr:` and move
     the card to **In Review** (→ **Done** when the PR merges; re-run the step-0
     sync before each batch).
   - **Advance to the next batch — mind what "blocker resolved" means.** Every
     worktree branches off `main` (step 4), so an issue can only build on top of
     a blocker whose code is actually on `main`. Therefore a later-batch issue
     that is **blocked** (`blocked_by`) must wait until its blocker's PR is
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
- **The parent does all commits/PRs and tracker writes** — worktree agents only
  implement and report back.
- **Worktrees always; never commit to `main`.** Keep a batch's parallel agents on
  **disjoint files** — that's exactly what the plan guarantees.
- **If the issues folder or board is missing** (e.g. not synced to this machine
  yet), say so and offer to run `/harness-bootstrap`, proceed with issue IDs
  the user names (file-overlap-only ordering), or stop.
