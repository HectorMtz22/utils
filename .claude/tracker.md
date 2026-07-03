# Tracker configuration

Single source of truth for this repo's issue tracker. Written by `/harness-setup`
and read by `/harness-bootstrap`, `/task-init`, `/issues-init`, `/task-implement`,
and `/task-run`. Committed on purpose — it's harness config, not a scratch spec.

```yaml
tracker:       plane                                   # plane | linear | github | other
mcp_prefix:    mcp__plane                              # MCP tool namespace, e.g. mcp__plane__create_cycle
project_code:  UTILS                                   # short id used in issue identifiers (UTILS-12)
project_id:    43bbc122-c9fe-469e-9379-db02d132a5c9    # Plane project id (the "Utils" project)
has_cycles:    true                                    # true → time-boxed cycles; false → milestones/none
cycle_length:  1w                                      # cycle duration (weekly)
cycle_anchor:  monday                                  # week runs Monday → Sunday
```

This repo is already provisioned on Plane (project **Utils** / `UTILS`). Run
`/harness-setup` to (re)generate this file if you switch trackers; run
`/harness-bootstrap` to top up future weekly cycles (or recreate any missing
project/states/labels) in the live tracker — both are idempotent.

New UTILS issues are always added to the **current weekly cycle** — see
`/task-init` and `/issues-init`.
