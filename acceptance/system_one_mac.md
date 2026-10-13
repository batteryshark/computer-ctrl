# Native executor acceptance

Start the optional local d3-mini sidecar using [the pinned Mac experiment setup](../eval/system_one_mac/README.md). Then, from the repository root:

```sh
CCTL_EXECUTOR_ENABLED=true CCTL_DECISION_PROTOCOL=d3 \
  CCTL_DECISION_MODEL=d3-mini CCTL_DECISION_URL=http://127.0.0.1:18761 \
  .venv/bin/python acceptance/system_one_mac.py \
  --harness ACTUAL_HARNESS --output /tmp/delegate-results.json
```

Ask each of two configured harnesses to execute this command, changing the harness label and output path. The label records provenance; it does not invoke a harness. Both runs must execute the native suite, rather than replay decisions. Run sequentially to avoid contention on the desktop and inference host.

The suite builds its own Swift fixture under a temporary directory and starts an isolated personal-profile MCP server. Every trial calls the public `delegate` tool against a newly created window. Successful trials require exact independently read output files and an accessible save confirmation. It checks field preservation, explicit false checkbox states, a two-page wizard, missing and ambiguous controls, controls swapping during a real inference request, and a deliberately unavailable model. Blocked cases require zero input attempts and no saved artifact. The reflow case requires a rejected stale choice and exact final data.

Only synthetic local windows and files are used. The fixture's Send/Discard controls record local test outcomes. Every trial closes its own window and verifies that its id disappears from a fresh window list; cleanup failure fails the run. Results record `cleanup_verified`. Settings and authentication for personal apps are untouched. `--cmd` selects the MCP command; `--app` can reuse an existing fixture bundle built from `SystemOneFixture.swift`. This suite validates macOS; other platforms still need live executor acceptance.
