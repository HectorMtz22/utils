# Development Harness (TDD)

The repeatable loop for shipping a change in this repo. It assumes Claude Code
with the `superpowers` plugin and the **Plane** MCP server. It complements
[`AGENTS.md`](AGENTS.md) (the *why* of worktrees/specs) with the *how* of TDD
and issue tracking.

Optimize for the **simplest approach that passes a test**, and **verify every
step with real output** before moving on. **Always use superpowers** — invoke
the relevant skill at each stage rather than improvising.

---

## The loop at a glance

```
brainstorm ─▶ spec ─▶ Plane issue(s) ─▶ worktree ─▶ TDD ─▶ verify ─▶ review ─▶ PR
  (skill)    (local)   (Plane UTILS)   (gitignored) (R/G/R)  (skill)  (skill)
└─────────── /task-init ───────────┘  └──────────── /task-implement ───────────┘
```

Two slash commands drive the loop:

- **`/task-init [description]`** — brainstorm → local spec → Plane issue(s).
- **`/task-implement [UTILS-12 …]`** — worktree → TDD → verify → review → PR,
  with parallel agents when there are multiple issues.

Issues live in **Plane** (project **Utils** / `UTILS`). Specs and plans stay
*local* and *gitignored* under `docs/superpowers/`; worktrees live under
`.worktrees/` (also gitignored). **Never commit either.** The durable record is
the code, the Plane issue, and the PR.

---

## 0. Decide the size

- **Trivial** (one-line fix, typo, obvious tweak): skip straight to TDD on a
  worktree branch. No spec, no Plane issue.
- **Non-trivial** (new feature, behavior change, multi-file): run the full loop
  via `/task-init` then `/task-implement`.

When unsure, treat it as non-trivial — a 10-line spec is cheap.

---

## 1. Brainstorm (non-trivial only) — `superpowers:brainstorming`

Run `/task-init`, which invokes `superpowers:brainstorming` to pressure-test the
idea before any code. Goal: agree on the **simplest** approach and surface
unknowns. The skill writes the spec and gets your approval.

## 2. The spec — local only

The brainstorming skill writes to:

```
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

Gitignored. Keep it short: problem, chosen approach, the code map (files to
touch), and the test list (what proves it works). This is the contract the
implementation agent works against.

## 3. Plane issue(s) — the tracker

`/task-init` files the work in **Plane**, project **Utils** (`UTILS`,
`project_id 43bbc122-c9fe-469e-9379-db02d132a5c9`). One issue ≈ one PR-sized
chunk. Each issue gets:

- **State `Todo`** (resolve state ids at runtime via `list_states`).
- A **project label** (`pdf_crop`, `music-lyrics`, `thermal-qr`, `pxe-boot`)
  and a **type label** (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`) —
  resolve label ids at runtime via `list_labels`.
- A description carrying the problem, approach, code map, test list, and the
  local spec filename.

Use multiple independent issues to coordinate **parallel agents** — each agent
owns one issue in its own worktree.

## 4. Worktree — `superpowers:using-git-worktrees`

Implementation always happens in an isolated worktree so the main checkout stays
clean. `/task-implement` uses `superpowers:using-git-worktrees`:

```bash
git worktree add -b <type>/<scope>-<topic> .worktrees/<topic> main
```

`.worktrees/` is gitignored. One worktree per issue/branch. For independent
issues, create multiple worktrees and dispatch one agent each — they won't
collide.

## 5. TDD: Red → Green → Refactor — `superpowers:test-driven-development`

This is the core. **Never write production code without a failing test first.**

1. **Red** — write the smallest test that captures the next behavior. Run it,
   **watch it fail for the right reason** (assertion, not import error).
   ```bash
   cd pdf_crop && uv run pytest tests/features/crop/test_service.py -k new_case
   ```
2. **Green** — write the *minimum* code to pass. No extra cases, no speculative
   options. Run the test, watch it pass.
3. **Refactor** — clean up names/duplication with the test green. Re-run.
4. **Widen** — run the **full project suite** before considering the step done:
   ```bash
   cd pdf_crop && uv run pytest
   ```

Repeat per behavior. Commit at green points (only when the user asks to commit),
using conventional-commit messages.

### Test conventions (from `pdf_crop`)

- Tests mirror the source tree: `src/.../features/crop/service.py` →
  `tests/features/crop/test_service.py`.
- Pure helpers (`shared/`) get class-grouped happy-path + error tests
  (see `tests/shared/test_ranges.py`); use `pytest.raises` for typed errors.
- Shared fixtures live in `conftest.py` (e.g. `ten_page_pdf`, `tmp_path`).
- One assert-able behavior per test; name it `test_<does_what>`.

### Projects without a test harness yet

`music-lyrics` and `thermal-qr` have no pytest suite. If you change their
behavior, **add a test harness first** (the simplest one that fits):

- A Python script → add `pytest` and a `tests/` dir, or extract the logic into
  an importable function and test that.
- A bash script → a `bats` test or a small `test.sh` asserting on output
  (`thermal-qr` already has `cd thermal-qr && ./tests/run.sh`).

Don't expand untested scripts further without this.

## 6. Verify for real — `superpowers:verification-before-completion`

Beyond green tests, run the actual command once to confirm end-to-end behavior.
Report what you observed.

## 7. Code review — always — `superpowers:requesting-code-review`

Run `superpowers:requesting-code-review` on the branch before any PR.

- Report findings to the user **grouped by severity** (Critical / Important /
  Minor).
- **Do not auto-fix.** The user decides scope. Re-review after agreed fixes.

## 8. PR & close out

Open a PR only when no Important+ findings remain and the suite is green — and
only when the user asks. Conventional-commit title with scope
(`feat(pdf_crop): …`). One feature per PR. Then set the Plane issue to **Done**.

---

## Parallel agents — `superpowers:dispatching-parallel-agents`

For work that splits cleanly, `/task-implement` runs issues concurrently:

1. `/task-init` files N independent Plane issues (disjoint files).
2. Create N worktrees (one per issue) via `superpowers:using-git-worktrees`.
3. Dispatch one subagent per worktree in a **single message** so they run
   concurrently (`superpowers:dispatching-parallel-agents` +
   `subagent-driven-development`). Each agent gets: its Plane issue + spec, its
   worktree path, a "don't touch the main checkout or other worktrees"
   instruction, the code map, and a "report back briefly" instruction.
4. The parent verifies each diff + test run, then reviews and PRs them
   independently, marking each Plane issue `Done`.

Keep agents on **disjoint files** — if two issues touch the same module,
sequence them instead.

---

## Guardrails

- **Issues in Plane; specs/plans local.** `docs/superpowers/` and `.worktrees/`
  are gitignored — never `git add` them. The tracker is Plane (`UTILS`).
- **Always superpowers.** Use the named skill at each stage; don't improvise the
  workflow.
- **Worktrees always.** Implementation never happens in the main checkout.
- **Branch off `main`; never commit to `main`.** Commit/push/PR only when asked.
- **Conventional commits always.** `<type>(<scope>): <subject>`; scope is the
  sub-project. No `Co-Authored-By: Claude` trailer; no "Generated with Claude
  Code" footer.
- **Simplest first.** If a test passes without a new abstraction or dependency,
  don't add one.
- **No green claim without a run.** Paste/observe real output.
