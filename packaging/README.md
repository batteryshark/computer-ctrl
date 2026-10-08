# Installing cctl into harnesses

## On the machine being controlled

Linux X11 is supported for now. You need `cua-driver` 0.34.0 in `~/.local/bin`, plus `xdotool`, `ffmpeg` and `uv`.

```bash
uv tool install --editable ~/computer-ctrl     # puts `cctl` in ~/.local/bin
cctl doctor                                     # must report "status": "ok"
```

The Cua daemon starts on demand inside the logged-in desktop session; SSH sessions find it automatically. Screen lockers and DPMS blanking must be off, or captures come back black and `doctor` says so.

## Pointing a harness at it

Use `cctl mcp` when the harness runs on the same machine. From another machine, use `cctl --host USER@HOST mcp`, which needs cctl on both ends, or plain `ssh -T USER@HOST ~/.local/bin/cctl mcp`.

| Harness | MCP config | Skill location |
|---|---|---|
| Claude Code | `claude mcp add cctl -- cctl mcp`, or load the plugin: `claude --plugin-dir packaging/claude-plugin` (set `CCTL_HOST` for a remote machine) | `~/.claude/skills/computer-use` → symlink to `skills/computer-use` |
| Codex CLI | `~/.codex/config.toml`: `[mcp_servers.cctl]` with `command = "cctl"`, `args = ["mcp"]`, `tool_timeout_sec = 120`. `codex exec` needs MCP calls approved: per-tool `approval_mode`, or `--dangerously-bypass-approvals-and-sandbox` on a sandbox VM | `~/.agents/skills/computer-use` |
| opencode | `opencode.json`: `"mcp": {"cctl": {"type": "local", "command": ["cctl", "mcp"], "timeout": 120000}}` | `~/.agents/skills/computer-use` (it also reads `~/.claude/skills`) |
| pi ≥ 1.0 | `pi mcp add cctl -- cctl mcp`, then set `"exposure": "direct"` for `cctl` in `~/.pi/agent/mcp.json`. The default "codemode" exposure hides the tools behind scripts | `~/.agents/skills/computer-use` |
| pi < 1.0, or any shell-only harness | none: the agent runs `cctl <tool> …` and opens the image at `path` | `~/.agents/skills/computer-use` |

## Verified (2026-10-07, Debian 13 XFCE VM)

| Harness / model | Path | GUI edit-and-save task |
|---|---|---|
| Codex CLI 0.161 / gpt-6.1-sol (medium) | MCP | PASS: 6 calls, 0 errors, ~11k tokens |
| opencode 1.18.35 / GLM-5.3 | MCP | PASS: 7 calls, 0 errors |
| Claude Code (Opus 5.5) | CLI `--host`, images copied back | PASS: 7 calls, 0 errors |
| acceptance script | MCP (local stdio, SSH stdio, `--host` passthrough) | 14/14 |

| Harness / model | Browser task: fill a local form with a Unicode code word, submit, report the confirmation |
|---|---|
| Codex / gpt-6.1-sol (medium) | PASS: 7 calls, 0 errors |
| opencode / GLM-5.3 | PASS: 8 calls, 0 errors |
| `acceptance/phase1b.py` | 10/10 |

Re-run with `acceptance/phase1.py [--cmd …]` and `acceptance/harness_task.sh <harness> [args]`.
