# Development Harness (TDD)

The repeatable loop for shipping a change in this repo. It assumes Claude Code
with the `superpowers` plugin and the **Plane** MCP server (tracker coordinates
live in [`.claude/tracker.md`](.claude/tracker.md)). It complements
[`AGENTS.md`](AGENTS.md) (the *why* of worktrees/specs) with the *how* of TDD and
issue tracking.

Optimize for the **simplest approach that passes a test**, and **verify every
step with real output** before moving on. **Always use superpowers** — invoke
the relevant skill at each stage rather than improvising.

---

## The loop at a glance

```
brainstorm ─▶ spec ─▶ Plane issue(s) ─▶ worktree ─▶ TDD ─▶ verify ─▶ review ─▶ PR
  (skill)    (local)   (Plane UTILS)   (gitignored) (R/G/R)  (skill)  (skill)
└─────────── /task-init ───────────┘  └──────────── /task-implement ───────────┘
└────────── /issues-init ──────────┘  └───────────────── /task-run ─────────────┘
      (same, but one epic → many          (same, but reads the backlog and
        linked issues at once)             orders the batches for you)
```

Four slash commands drive the loop — two for planning, two for building, each
pair scaling from a single task to a whole epic/backlog:

- **`/task-init [description]`** — brainstorm → local spec → Plane issue(s).
- **`/issues-init [epic]`** — decompose an epic → many linked Plane issues
  (blocks relations + a parent epic), so `/task-run` can order them.
- **`/task-implement [UTILS-12 …]`** — worktree → TDD → verify → review → PR for
  the issues you name, with parallel agents when there are multiple.
- **`/task-run [ids|label]`** — read the backlog, plan a parallel/sequential order
  from blocks-relations + file-overlap, then drive `/task-implement`'s machinery
  batch by batch.

Issues live in **Plane** (project **Utils** / `UTILS`). Specs and plans stay
*local* and *gitignored* under `docs/superpowers/`; worktrees live under
`.worktrees/` (also gitignored). **Never commit either.** The durable record is
the code, the Plane issue, and the PR.

---

## Set up the tracker (once per repo)

This repo is already provisioned on Plane, so you rarely touch these. The
coordinates live in [`.claude/tracker.md`](.claude/tracker.md).

1. **`/harness-setup`** — choose the tracker (default Plane); (re)writes
   `.claude/tracker.md`. Only needed to change trackers.
2. **`/harness-bootstrap`** — create/top-up the project, the
   `Todo → In Progress → In Review → Done` states, the type labels, and the
   weekly (Mon→Sun) cycles. Idempotent — its day-to-day use is topping up
   future cycles.

---

## 0. Decide the size

- **Trivial** (one-line fix, typo, obvious tweak): skip straight to TDD on a
  worktree branch. No spec, no Plane issue.
- **Non-trivial** (new feature, behavior change, multi-file): run the full loop
  via `/task-init` then `/task-implement` (or `/issues-init` → `/task-run` for an
  epic).

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

`/task-init` files the work in **Plane**, project **Utils** (`UTILS`; read
`project_id` from `.claude/tracker.md`). One issue ≈ one PR-sized chunk. Each
issue gets:

- **State `Todo`** (resolve state ids at runtime via `list_states`).
- A **project label** (`pdf_crop`, `music-lyrics`, `thermal-qr`, `pxe-boot`)
  and a **type label** (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`) —
  resolve label ids at runtime via `list_labels`.
- The **current weekly cycle** (new UTILS issues always go into the current
  cycle — resolve it via `list_cycles`).
- A description carrying the problem, approach, code map, test list, and the
  local spec filename.

Use multiple independent issues to coordinate **parallel agents** — each agent
owns one issue in its own worktree. For epic-scale work, `/issues-init` files the
batch already linked so `/task-run` can order it.

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

Repeat per behavior. Commit at green points using conventional-commit messages —
the back half (verify → review → PR) needs the work committed and the tree clean.

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

## 8. PR & close out — automatic

Open a PR **automatically** as soon as a branch is **verified, green, committed,
and clean**: no Important+ findings outstanding, the full suite passing, and the
working tree clean. No need to ask first. Conventional-commit title with scope
(`feat(pdf_crop): …`). One feature per PR. Then move the Plane issue to
**In Review**; set it to **Done** when the PR merges.

Only the PR-open step is automatic — the review *fix* decision still waits for
the user (§7).

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
   independently, moving each Plane issue to `In Review` on PR-open (and to
   `Done` when it merges).

Keep agents on **disjoint files** — if two issues touch the same module,
sequence them instead.

**`/task-run` automates this triage.** Instead of you hand-picking the disjoint
set, it reads the backlog, derives the batches from Plane's blocks-relations +
file-overlap, and runs each batch through steps 2–4 above — parallel where safe,
sequential where two issues collide. Pair it with `/issues-init`, which files the
issues already linked so the ordering is explicit.

---

## Guardrails

- **Issues in Plane; specs/plans local.** `docs/superpowers/` and `.worktrees/`
  are gitignored — never `git add` them. The tracker is Plane (`UTILS`);
  coordinates live in `.claude/tracker.md`.
- **Always superpowers.** Use the named skill at each stage; don't improvise the
  workflow.
- **Worktrees always.** Implementation never happens in the main checkout.
- **Branch off `main`; never commit to `main`.** Commit at green points; open
  the PR **automatically** once the branch is verified, green, committed, and
  clean (§8). The review fix decision still waits for the user.
- **Conventional commits always.** `<type>(<scope>): <subject>`; scope is the
  sub-project. No `Co-Authored-By: Claude` trailer; no "Generated with Claude
  Code" footer.
- **Simplest first.** If a test passes without a new abstraction or dependency,
  don't add one.
- **No green claim without a run.** Paste/observe real output.
