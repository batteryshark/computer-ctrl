# Installing cctl into harnesses

## On the machine being controlled

Linux X11 is supported for now. You need `cua-driver` 0.34.0 in `~/.local/bin`, plus `xdotool`, `ffmpeg` and `uv`.

```bash
uv tool install --editable ~/computer-ctrl     # puts `cctl` in ~/.local/bin
cctl doctor                                     # must report "status": "ok"
```

The Cua daemon starts on demand inside the logged-in desktop session; SSH sessions find it automatically. Screen lockers and DPMS blanking must be off, or captures come back black and `doctor` says so.

## Platform notes

- **macOS**: needs Cua's `CuaDriver.app` in /Applications (run `cua-driver permissions grant` once) and, for audio, `packaging/macos/build-audio-helper.sh`. That builds `~/Applications/cctl-audio.app`, a ScreenCaptureKit capture helper; allow it once under Screen & System Audio Recording (and Microphone for `source=mic`). The build signs with your Apple Development identity if you have one, so rebuilds keep those grants (ad-hoc signing loses them). With the lid closed, the built-in mic is off, so pick another input by name, e.g. `source="Webcam"`. Use the `personal` profile on someone's own Mac.
- **Windows**: needs Cua's `cua-driver.exe` (`~\.cua-driver\<ver>\…`) and `uv tool install --editable ".[audio,stt]"`. `cctl serve` runs in the logged-in desktop session (started on demand via a one-shot scheduled task); `cctl mcp` over SSH relays to it. Audio is WASAPI loopback/mic via `soundcard`.

## Remote targets for the CLI and MCP

Describe each remote machine once in `~/.config/cctl/config.toml` on the machine you run from:

```toml
[hosts."user@windows-pc"]          # Windows (OpenSSH, PowerShell default shell)
os = "windows"
ssh_args = ["-i", "~/.ssh/id_ed25519", "-o", "IdentitiesOnly=yes"]

[hosts."user@linux-vm"]            # Linux
remote_bin = "~/.local/bin/cctl"
```

Then use `cctl --host user@windows-pc <tool> …` (images, clip sheets and waveforms are copied back, and `path` points at the local copy) or `cctl --host user@windows-pc mcp`. On Windows the session-resident daemon keeps state between calls, so frame ids and element tokens survive across separate commands.

## Pointing a harness at it

Use `cctl mcp` when the harness runs on the same machine. From another machine, use `cctl --host USER@HOST mcp`, which needs cctl on both ends, or plain `ssh -T USER@HOST ~/.local/bin/cctl mcp`.

| Harness | MCP config | Skill location |
|---|---|---|
| Claude Code | `claude mcp add cctl -- cctl mcp`, or load the plugin: `claude --plugin-dir packaging/claude-plugin` (set `CCTL_HOST` for a remote machine) | `~/.claude/skills/computer-use` → symlink to `skills/computer-use` |
| Codex CLI | `~/.codex/config.toml`: `[mcp_servers.cctl]` with `command = "cctl"`, `args = ["mcp"]`, `tool_timeout_sec = 120`. `codex exec` needs MCP calls approved: per-tool `approval_mode`, or `--dangerously-bypass-approvals-and-sandbox` on a sandbox VM | `~/.agents/skills/computer-use` |
| opencode | `opencode.json`: `"mcp": {"cctl": {"type": "local", "command": ["cctl", "mcp"], "timeout": 120000}}`. opencode locates the project (and so this file) from `$PWD`, not the process working directory. When launching it from a script, set `PWD` or `cd` first | `~/.agents/skills/computer-use` (it also reads `~/.claude/skills`) |
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

| Harness / model | Media tasks (Phase 2) |
|---|---|
| Codex / gpt-6.1-sol | clip: read a 5-word cycle flashed on a canvas, PASS in 2 calls · audio: report a spoken secret word, PASS in 1 call |
| opencode / GLM-5V-Turbo (clip), GLM-5.3 (audio) | clip PASS in 2 calls · audio PASS in 1 call |
| `acceptance/phase2.py` | 12/12 |

## Eval baselines (16 natural-language tasks, `eval/run.py`, 2026-10-08)

| Harness / model | Score | Notes |
|---|---|---|
| Codex / gpt-6.1-sol (medium) | 16/16 | Median 22 s per task. Find-and-replace in Mousepad is the slowest (~37 calls); its dialog hides Replace buttons from accessibility until text is entered |
| opencode / GLM-5.3 (text-only) | 16/16 | 15/16 first run. The clip task passed after `record_clip --ocr` gained `text_changes`, and is now 2 calls |

`eval/results/*.md` has per-task seconds, calls, errors and tokens.

**`locate` with Holo4-35B-A3B** (llama.cpp on the M5 Max, over the tailnet): 36/36 on labeled controls, ~1.3 s per call (2.2 s with the refine pass). On `canvas_click_shape` (unlabeled shapes on a canvas), the text-only GLM-5.3 goes from 1/3 without `locate` to 3/3 with it. Codex, which can see, needs none (3/3 in 4 calls).

On the controlled machine, install with `uv tool install --editable '.[stt]'` to get local Whisper transcription (CPU, `small` by default). Without it, or with `stt_url` set, transcription goes to an OpenAI-compatible `/v1/audio/transcriptions` endpoint.

Re-run with `acceptance/phase1.py | phase1b.py | phase2.py [--cmd …]` and `TASK=editor|browser|audio|clip acceptance/harness_task.sh <harness> [args]`.
