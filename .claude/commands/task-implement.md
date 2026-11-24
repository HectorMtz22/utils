---
description: Implement UTILS issue(s) from the Obsidian Kanban board in worktrees with parallel agents, TDD, review, and PR
argument-hint: [UTILS-100 UTILS-101 …] (optional; lists Todo issues if omitted)
---

# /task-implement — implement UTILS issue(s)

Take one or more **UTILS** issues and drive them through the back half of the
harness (see `HARNESS.md`): `worktree → TDD → verify → review → PR`. Always use
worktrees, always use superpowers, always conventional commits. Multiple issues
run as **parallel agents**, one worktree each.

> To build the **whole backlog** in auto-planned dependency order instead of
> naming issues, use **`/task-run`** — it wraps this same machinery with an
> ordering layer.

Requested issues (may be empty): **$ARGUMENTS**

## Tracker

Read `.claude/tracker.md` — the single source of truth for the issues folder,
the board, the note/card format, and how to move a card. If that file is
missing, tell the user to run `/harness-setup` first.

- States are the board lanes: **Todo**, **In Progress**, **In Review**, **Done**.
  An issue's state is the lane its card is in — nothing else.

## Steps

0. **Sync merged PRs.** Per `.claude/tracker.md` ("Done ← merged"), move every
   **In Review** card whose PR has merged to **Done**.

1. **Resolve the work list.**
   - If issue identifiers were passed, open each `UTILS-<n>-*.md` note.
   - If none were passed, list the cards in the board's **Todo** lane, show
     them (title from each note), and ask the user which to implement.
   - For each issue read the note and open the linked local spec (`spec:`)
     under `docs/superpowers/specs/` — that's the contract.

2. **Move each card to In Progress** on the board (one edit of the re-read
   board for the whole set).

3. **One worktree per issue.** Use `superpowers:using-git-worktrees`. Branch
   name = `<type>/<scope>-<topic>` from the note's `type` + `project`, e.g.
   `feat/pdf_crop-range-presets`; record it in the note's `branch:`. Worktrees
   go under `.worktrees/` (gitignored).

4. **Dispatch implementation agents.**
   - Use `superpowers:subagent-driven-development`; each subagent follows
     `superpowers:test-driven-development` (red → green → refactor, full suite).
   - **More than one issue → `superpowers:dispatching-parallel-agents`**: dispatch
     all agents in a **single message** so they run concurrently, one per
     worktree. Only parallelize issues that touch **disjoint files**; if two
     issues overlap a module, sequence them instead.
   - Give each agent: its issue note + spec, its worktree path, the code map,
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
   - Set the note's `pr:` to the PR URL and move the card to **In Review** (the
     PR is open, not merged). It moves to **Done** when the PR merges — via the
     step-0 sync on the next run, or by hand.
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
- **The parent does every tracker write** (notes and board). Agents never edit
  the board — concurrent edits of one file would clobber each other.
