# Agent workflow for this repo

This file captures how feature work is done in this repo by automated coding
agents (Claude Code with the `superpowers` plugin, tracking issues on an
**Obsidian Kanban** board of Markdown files). It's a recipe, not a rule. Tracker
location and format live in
[`.claude/tracker.md`](.claude/tracker.md). **Always use superpowers** — invoke
the named skill at each stage. See [`HARNESS.md`](HARNESS.md) for the full TDD
detail.

Four slash commands wrap the loop — a planning pair and a building pair, each
scaling from a single task to a whole epic/backlog: **`/task-init`** /
**`/issues-init`** (front half) and **`/task-implement`** / **`/task-run`**
(back half).

## TL;DR

1. **`/task-init`** runs `superpowers:brainstorming` → a design at
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (gitignored, local-only)
   → files **UTILS issue(s)**: a note per issue (project + type in frontmatter)
   and a card in the board's `Todo` lane. For a broad goal, **`/issues-init`**
   does the same at epic scale: it decomposes into many PR-sized issues, files
   them under a parent epic note, and records **`blocked_by`** links so the
   backlog is pre-ordered.
2. **`/task-implement [UTILS-…]`** picks up the issue(s) and, for each, moves it
   to `In Progress` and **creates a worktree** under `.worktrees/<topic>/` on a
   new branch (gitignored) via `superpowers:using-git-worktrees`. To run the
   backlog instead of naming issues, **`/task-run`** derives parallel/sequential
   batches (from those `blocked_by` links + file-overlap), then drives this same machinery
   batch by batch.
3. **Dispatch a subagent** to implement inside that worktree, following TDD.
   Multiple issues → `superpowers:dispatching-parallel-agents`, one agent per
   worktree, in a single message.
4. **Run `superpowers:requesting-code-review`** on each branch.
5. **Report findings, ask before fixing** (per the user's global rule).
6. **Open a PR automatically** once the branch is verified, green, committed, and
   clean (no Important+ findings remain), then move the card to **In Review**
   (and to **Done** when the PR merges). Only the fix decision in
   step 5 waits for the user.

## Why worktrees

Subagents touch a lot of files. Doing implementation in a separate worktree on a
feature branch keeps the main checkout clean and lets the parent agent inspect
the diff without context pollution.

When two or more independent tasks are dispatched in parallel, each gets its own
worktree, branch, and PR, so the diffs never tangle. Worktree setup goes through
`superpowers:using-git-worktrees`; implementation **always** happens in a
worktree, never in the main checkout.

```bash
git worktree add -b <type>/<scope>-<topic> .worktrees/<topic> main
```

`.worktrees/` is gitignored.

## Issue tracking — Obsidian Kanban

Issues live **outside the repo** in `~/tracker/issues/utils` (an Obsidian vault
synced with Syncthing): one `UTILS-<n>-<slug>.md` note per issue plus the
`Utils.md` Kanban board. The exact format is in `.claude/tracker.md`.
`/task-init` / `/issues-init` file them; `/task-implement` / `/task-run` read and
advance them.

- **States** are the board lanes: `Todo` → `In Progress` → `In Review` (PR
  open) → `Done` (merged). The lane a card sits in is the only record of state.
- **Tags:** one **project** (`pdf_crop`, `music-lyrics`, `thermal-qr`,
  `pxe-boot`) plus one **type** (`feat`, `fix`, `refactor`, `test`, `docs`,
  `chore`) per issue — in the note's frontmatter and as `#tags` on the card.
- **No cycles.**
- One issue ≈ one PR-sized chunk; independent issues enable parallel agents.
- The note carries the problem/approach/code-map/test-list and a pointer to the
  local spec filename.
- **Only the parent agent edits the board**; subagents never touch it.

## Why a separate spec workspace

`docs/superpowers/specs/` holds design docs the agent uses to align with the user
before coding. They are local-only (gitignored) because they're scratch
artifacts, not project documentation. The committed PR description and code are
the durable record.

## Subagents

For an implementation task that's bigger than a single edit, use
`superpowers:subagent-driven-development` to dispatch a subagent with:

- A pointer to its **issue note** and the linked design doc.
- The exact worktree path and a "do not touch the main checkout or sibling
  worktrees" instruction.
- An explicit code map (files to touch).
- A "report back briefly" instruction (so the parent's context isn't flooded).

When tasks run in parallel, use `superpowers:dispatching-parallel-agents`:
dispatch one subagent per worktree in a single message. Keep them on disjoint
files; sequence anything that overlaps. `/task-run` derives that disjoint set
from the backlog for you.

The parent verifies the diff and test results
(`superpowers:verification-before-completion`) before moving on.

## Code review

Always run `/superpowers:requesting-code-review` before opening a PR. Report
findings to the user grouped by severity. **Do not auto-fix** — the user decides
which items are in scope.

## Commit messages

Agent commits in this repo skip the `Co-Authored-By: Claude <...>` trailer, and
PR bodies skip the "Generated with Claude Code" footer. Keep the subject and
body, drop the attribution — the PR already signals the author.

Use [Conventional Commits](https://www.conventionalcommits.org/):
`<type>(<scope>): <subject>`. Common types: `feat`, `fix`, `refactor`, `test`,
`docs`, `chore`. The scope is usually the top-level project directory (e.g.
`pdf_crop`, `music-lyrics`).

## Tests first

Implementation follows TDD: write the failing test, watch it fail, make it pass,
refactor. Subagents dispatched for non-trivial work should be told to
red/green/refactor and to include the failing-test commit in the diff (or at
minimum show the failing run in their report).

## Layout summary

```
.worktrees/                              # gitignored, agent worktrees
.claude/tracker.md                       # tracker config, single source of truth (committed)
.claude/commands/                        # /task-init, /issues-init, /task-implement,
                                         #   /task-run, /harness-setup, /harness-bootstrap (committed)
docs/
  superpowers/                           # gitignored
    specs/YYYY-MM-DD-<topic>-design.md   # design docs (issues live in ~/tracker, not the repo)
pdf_crop/                                # actual project
```
