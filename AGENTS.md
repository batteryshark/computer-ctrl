# computer-ctrl

Harness-agnostic computer-use toolkit (MCP + CLI + Agent Skill) for Claude Code, Codex CLI, opencode, pi and Gemini/Antigravity on Windows, macOS and Linux.

Several harnesses hand off phases of this project. Before working:

1. Read `.project/tracker.md` (current state, active phase, decisions, next action).
2. Read the "plan" and "architecture" sections of `reports/Harness agnostic computer use toolkit.md`. Sourced detail is in `research_notes/Harness agnostic computer use toolkit/`. Where the tracker and the report disagree, the tracker wins.
3. When you finish a work session, update `.project/tracker.md` (status, evidence, decisions, next action). Keep it compact; do not paste transcripts.

Rules:

- The tool contract (`contract/tools.json`, once it exists) is the source of truth, not any harness's memory.
- Run each phase's acceptance test from at least two different harnesses.
- Test VM: `ssh user@linux-vm` (Tailscale). It runs Debian 13 with XFCE on X11, DISPLAY=:0. It is a disposable sandbox the agent fully controls. Model inference runs elsewhere (the user's Mac or 96 GB desktop).
- Private project: licenses (AGPL, CC BY-NC) are not blockers.
- Never store credentials or tokens in the repo or tracker.
