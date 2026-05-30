# CLAUDE.md

Guidance for Claude Code working in this repo. Read this first, then
[`HARNESS.md`](HARNESS.md) for the day-to-day TDD + agent workflow.

## What this is

`utils` is a **multi-project monorepo**. Each top-level directory is a
self-contained project with its own dependencies, README, and (ideally) tests.
There is no shared package — keep projects independent.

| Project | What | Stack | Tests |
|---|---|---|---|
| [`pdf_crop/`](pdf_crop/) | CLI + TUI to extract page ranges from PDFs | Python 3.12, `uv`, pytest, textual, pypdf | `uv run pytest` (reference example) |
| [`music-lyrics/`](music-lyrics/) | Script: fetch synced/plain lyrics from lrclib.net for a local library | Python 3.9, local `lyrics-env` venv | none yet |
| [`thermal-qr/`](thermal-qr/) | Shell script: print a QR to a macOS ESC/POS thermal printer | bash + inline `python3` | none yet |

`pdf_crop/` is the **gold-standard layout** — mirror it when a project grows
past a single script:

```
src/<pkg>/
  features/<feature>/{service,command,screen}.py   # one folder per feature
  shared/{ranges,pdf_io,output_path,errors}.py     # cross-feature helpers
tests/
  features/<feature>/test_*.py                     # mirrors src tree
  shared/test_*.py
  conftest.py                                       # fixtures
```

## Core principles

1. **Simplest thing that works.** Prefer the smallest change that satisfies the
   test. No speculative abstraction, no new dependency without a reason. A shell
   script or single `.py` file is a valid project — don't "promote" it to a
   package until it earns it.
2. **TDD, always.** Red → green → refactor. New behavior starts with a failing
   test. See [`HARNESS.md`](HARNESS.md).
3. **Verify before claiming done.** Run the tests (or the actual command) and
   report real output. Never say "done" on an unrun change.
4. **Keep projects isolated.** Don't reach across project boundaries or add a
   root-level dependency.
5. **Match the surrounding code** — naming, comment density, idioms.

## Per-project commands

```bash
# pdf_crop
cd pdf_crop && uv sync && uv run pytest        # test
uv run pdfcrop Document.pdf 1-5,8              # run

# music-lyrics  (uses its own venv, not uv)
music-lyrics/lyrics-env/bin/python music-lyrics/lyrics_on_nas.py

# thermal-qr
./thermal-qr/print-qr.sh "https://example.com" "caption"
```

## Conventions

- **Commits:** Conventional Commits, scoped per project:
  `feat(pdf_crop): …`, `fix(thermal-qr): …`, `test(pdf_crop): …`,
  `chore: …`. One project per commit where possible.
- **PRs:** one feature per PR; open only after code review is clean (see harness).
- **Commit/push only when asked.** Branch off `main` first — never commit to
  `main` directly.

## Workflow & agents

The full loop (brainstorm → spec → worktree → TDD → review → PR) lives in
[`HARNESS.md`](HARNESS.md) and [`AGENTS.md`](AGENTS.md). Key rules:

- **Specs, plans, and issues are local-only** under `docs/superpowers/`
  (gitignored). **Never commit them.** The committed record is the code + PR.
- **Use worktrees** under `.worktrees/` (gitignored) for implementation work.
- **Use the issue tracker** at `docs/superpowers/issues/` to plan multi-step work.
- Use the `superpowers` plugin: `brainstorm` before non-trivial work,
  `requesting-code-review` before every PR. **Report findings, don't auto-fix.**
