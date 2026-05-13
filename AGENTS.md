# Agent workflow for this repo

This file captures how feature work is done in this repo by automated coding agents (Claude Code with the `superpowers` plugin). It's a recipe, not a rule.

## TL;DR

1. **Brainstorm and write a design** to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (gitignored, local-only).
2. **Create a worktree** under `.worktrees/<topic>/` on a new branch (gitignored).
3. **Dispatch a subagent** to implement inside that worktree.
4. **Run `/superpowers:requesting-code-review`** on the branch.
5. **Report findings, ask before fixing** (per the user's global rule).
6. **Open a PR** if no Important+ findings remain.

## Why worktrees

Subagents touch a lot of files. Doing implementation in a separate worktree on a feature branch keeps the main checkout clean and lets the parent agent inspect the diff without context pollution.

```bash
git worktree add -b feature/<topic> .worktrees/<topic> main
```

`.worktrees/` is gitignored.

## Why a separate spec workspace

`docs/superpowers/specs/` holds design docs the agent uses to align with the user before coding. They are local-only (gitignored) because they're scratch artifacts, not project documentation. The committed PR description and code are the durable record.

## Subagents

For an implementation task that's bigger than a single edit, dispatch a `general-purpose` subagent with:

- A pointer to the design doc.
- The exact worktree path and a "do not touch the main checkout" instruction.
- An explicit code map (files to touch).
- A "report back briefly" instruction (so the parent's context isn't flooded).

The parent verifies the diff and test results before moving on.

## Code review

Always run `/superpowers:requesting-code-review` before opening a PR. Report findings to the user grouped by severity. **Do not auto-fix** — the user decides which items are in scope.

## Layout summary

```
.worktrees/                              # gitignored, agent worktrees
docs/
  superpowers/                           # gitignored
    specs/YYYY-MM-DD-<topic>-design.md   # design docs
pdf_crop/                                # actual project
```
