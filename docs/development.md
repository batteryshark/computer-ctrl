# Development and test safety

The Python package is in `src/cctl/`; public schemas are in `contract/tools.json`.
`server.py` exposes MCP stdio, `cli.py` exposes the JSON CLI and SSH transport,
and `providers.py` selects host or isolated execution before desktop discovery.
`packaging/` contains harness templates and the optional macOS audio-helper build.

## Tests

`tests/` contains unit and mocked provider/executor coverage. The pytest `e2e`
marker excludes marked desktop cases by default, but unmarked tests can still
open sockets or start subprocesses. Inspect the selected fixtures and imports
before running them. In a deliberately prepared development environment with
dependencies installed, the suite command is:

```sh
python -m pytest tests
```

Use an isolated HOME/XDG/TMP environment, private state/cache, and denied native,
network and process access for offline work. A full suite may need an explicitly
approved environment for its loopback/process fixtures. Never weaken an effect
guard to turn a blocked fixture into a pass.

`acceptance/`, `eval/` and `phase0/` retain synthetic desktop fixtures and live
test drivers. These can control desktops, start models/services, write files or
manage processes. Read the selected driver and obtain target-specific approval
before use. Saved run results and transcripts aren't shipped in the working tree;
historical records remain in Git history. Native behavior needs independent
checks of actual files, frames, target identity and cleanup, beyond agent claims.

## Builds

`pyproject.toml` declares Python and optional dependencies; `uv.lock` records the
dependency resolution. A source install can build a wheel and download packages.
The CI workflow defines cross-platform checks; its existence doesn't establish
that a new checkout passed them.

The macOS audio build script reserves new app/build directories and refuses
existing destinations and symlink ancestors. It then invokes Swift and codesign.
It must be run deliberately with operator-controlled parents; its static path
checks don't protect against concurrent ancestor replacement. See
[the setup guide](../packaging/README.md) for destination and permission details.
