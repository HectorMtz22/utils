# Tracker configuration

Single source of truth for this repo's issue tracker. Written by `/harness-setup`
and read by `/harness-bootstrap`, `/task-init`, `/issues-init`, `/task-implement`,
and `/task-run`. Committed on purpose — it's harness config, not a scratch spec.

```yaml
tracker:       obsidian-kanban                         # obsidian-kanban | plane | linear | github | other
mcp_prefix:    none                                    # plain files — no MCP server
project_code:  UTILS                                   # short id used in issue identifiers (UTILS-100)
project_id:    ~/tracker/issues/utils                  # issues folder (outside the repo, Syncthing-synced)
board:         Utils.md                                # Kanban board file inside project_id
vault_root:    ~/tracker                               # Obsidian vault root (.obsidian/ lives here)
id_start:      100                                     # first id; Plane used UTILS-1…~32, so no collisions
has_cycles:    false                                   # no cycles — the board lanes are the workflow
cycle_length:  none
cycle_anchor:  none
```

Issues are plain Markdown in an [Obsidian Kanban](https://github.com/mgmeyers/obsidian-kanban)
board, synced between machines with Syncthing. Every worktree reaches the folder
by the same absolute path, so state changes are visible to all agents at once.
Run `/harness-bootstrap` to create the folder and board if they're missing.

## Issue notes

One note per issue: `<project_id>/UTILS-<n>-<slug>.md` (slug = short kebab-case
topic, e.g. `UTILS-100-range-presets.md`).

- **Next id** = highest `UTILS-<n>` among the folder's filenames + 1, or
  `id_start` if there are none. Never keep a counter file — two offline machines
  would both bump it and Syncthing would conflict.
- The note does **not** record state — the board does (below).

```markdown
---
id: UTILS-100
title: "feat(pdf_crop): add page-range presets"
project: pdf_crop            # pdf_crop | music-lyrics | thermal-qr | pxe-boot | <new sub-project>
type: feat                   # feat | fix | refactor | test | docs | chore | epic
epic: UTILS-99               # optional: parent epic note id
blocked_by: [UTILS-98]       # optional: ids that must be merged first
spec: docs/superpowers/specs/2026-11-24-range-presets-design.md
branch:                      # set by /task-implement
pr:                          # PR URL, set when opened
created: 2026-11-24
---

## Problem
## Approach
## Code map
## Tests
```

An **epic** is a note with `type: epic` whose body links its children
(`[[UTILS-101-…]]`); it gets no card on the board.

## The board — `<project_id>/Utils.md`

**The lane a card sits in is the issue's state — the only place state lives.**
Dragging a card in Obsidian and an agent editing the file are the same operation.
Lanes, in order: `Todo`, `In Progress`, `In Review`, `Done`. Format (Kanban plugin
v2 serializer — keep it byte-compatible):

~~~~markdown
---

kanban-plugin: board

---

## Todo

- [ ] [[UTILS-101-range-presets]] #pdf_crop #feat


## In Progress



## In Review

- [ ] [[UTILS-100-tounicode]] #pdf_crop #fix


## Done

**Complete**
- [x] [[UTILS-99-uv-tool-docs]] #pdf_crop #docs




%% kanban:settings
```
{"kanban-plugin":"board","new-note-folder":"issues/utils"}
```
%%
~~~~

- **Card** = `- [ ] [[<note filename without .md>]] #<project> #<type>`; cards in
  `Done` use `- [x]`. New cards go at the bottom of `Todo`.
- **Move a card** = delete its line from the current lane and append it to the
  end of the target lane's list (flip `[ ]`/`[x]` when entering/leaving `Done`).
  Change only that line; leave the frontmatter, headings, blank lines, and the
  `%% kanban:settings %%` block untouched.
- Cards under an `## Archive` heading (after a `***` line) count as `Done`.
- Re-read the board right before each edit — the user may have dragged cards in
  Obsidian, or Syncthing may have synced a change, since the last read.
- If a `Utils.sync-conflict-*.md` file appears, stop and ask the user to merge
  it; don't guess.

## Done ← merged

Nothing closes issues on merge automatically. `/task-implement` and `/task-run`
start by syncing: for every `In Review` card whose note has a `pr:`, run
`gh pr view <pr> --json state -q .state`; `MERGED` → move the card to `Done`.
