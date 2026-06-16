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
| [`thermal-qr/`](thermal-qr/) | Shell script: print a QR to a macOS ESC/POS thermal printer | bash + inline `python3` | `cd thermal-qr && ./tests/run.sh` |
| [`pxe-boot/`](pxe-boot/) | macOS CLI to PXE-boot a PC on the LAN (netboot.xyz or local ISO) | Python 3.12, `uv`, pytest | `cd pxe-boot && uv run pytest` |

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
./thermal-qr/print-qr.sh "https://example.com" "caption"   # CLI
./thermal-qr/print-qr.sh                                    # TUI
cd thermal-qr && ./tests/run.sh                             # test
```

## Conventions

- **Commits:** Conventional Commits, scoped per project:
  `feat(pdf_crop): …`, `fix(thermal-qr): …`, `test(pdf_crop): …`,
  `chore: …`. One project per commit where possible.
- **PRs:** one feature per PR; **opened automatically** once the branch is
  verified, green, committed, and clean (see harness). Code-review *fixes* still
  wait for the user.
- **Branch off `main` first — never commit to `main` directly.** Commit at green
  points so the branch is PR-ready.
- **No Claude attribution.** Don't add `Co-Authored-By: Claude …` to commit
  messages or `🤖 Generated with Claude Code` to PR bodies.

### Releasing / versioning

Releases are **git tags** named `<project-dir>-vX.Y.Z` (e.g. `pdf_crop-v0.2.0`,
`pxe-boot-v0.1.9`). The `uv`/hatchling projects (`pdf_crop`, `pxe-boot`) derive
their version automatically from those tags via `hatch-vcs` at build time — in a
tag-versioned project, **never edit a `version =` field by hand** (its
`pyproject.toml` declares `dynamic = ["version"]`). The script projects
(`thermal-qr`, `music-lyrics`) aren't packaged this way and carry no version field.

- After tagging a release, refresh the global tool:
  `cd <project> && uv tool install --force .`. The new version busts uv's wheel
  cache, so `--no-cache` isn't needed.
- For live dev iteration just use `uv run` — it rebuilds against the working tree.
- Between tags, builds report a dev version like `0.1.1.devN+g<hash>` (and a
  `.dYYYYMMDD` suffix when the tree is dirty). That's expected, not a bug.
- Each project's package lives one level below the git root, so its
  `[tool.hatch.version.raw-options]` sets `root = ".."` and a
  `--match <project-dir>-v*` describe command to ignore other projects' tags.

## Workflow & agents

The full loop (brainstorm → spec → Plane issue(s) → worktree → TDD → verify →
review → PR) lives in [`HARNESS.md`](HARNESS.md) and [`AGENTS.md`](AGENTS.md),
wrapped by two commands: **`/task-init`** (brainstorm → spec → file issues) and
**`/task-implement`** (worktree → TDD → review → PR). Key rules:

- **Always use superpowers.** Invoke the named skill at each stage
  (`brainstorming`, `using-git-worktrees`, `test-driven-development`,
  `dispatching-parallel-agents`, `verification-before-completion`,
  `requesting-code-review`). **Report findings, don't auto-fix.**
- **Specs and plans are local-only** under `docs/superpowers/` (gitignored).
  **Never commit them.** The committed record is the code + PR.
- **Issues live in Plane** — project **Utils** (`UTILS`). Each issue gets a
  project label (`pdf_crop`/`music-lyrics`/`thermal-qr`/`pxe-boot`) and a type
  label (`feat`/`fix`/`refactor`/`test`/`docs`/`chore`); states go
  `Todo → In Progress → In Review (PR open) → Done (merged)`. Not in local files.
- **Always use worktrees** under `.worktrees/` (gitignored) for implementation;
  never work in the main checkout. Multiple issues run as parallel agents, one
  worktree each.
- **Conventional commits always**, scoped per sub-project.
