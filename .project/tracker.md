# Project Tracker: computer-ctrl: harness-agnostic computer-use toolkit

Updated: 2026-10-07

## Current state

- Objective: Build a harness-agnostic computer-use toolkit (MCP + CLI + Agent Skill) that lets Claude Code, Codex CLI, opencode, pi (and Gemini/Antigravity) control Windows, macOS and Linux desktops: screenshots + zoom, mouse/keyboard, windows, processes, browser, a11y, OCR, audio and short video clips for capable models.
- Status: **Phase 1 core done on Linux X11.** `cctl` (Python, uv) serves the 17-tool contract over MCP and a CLI. Acceptance passes 14/14. The same GUI task passed from 3 harnesses (Codex/gpt-6.1-sol MCP, opencode/GLM-5.3 MCP, Claude Code via CLI `--host`). Phase 1b (browser) done. **Phase 2 (media) done**: record_clip, audio_capture and ocr; acceptance 12/12; clip and audio tasks PASS in Codex and opencode.
- Main constraint: Harnesses disagree on what tool media reaches the model (see report, "Harness quirks" table). The output layer must target the lowest common denominator.
- Environment roles: `user@linux-vm` is a disposable sandbox the agent fully controls (not an inference host). The user's own windows there (e.g. Mousepad `~/private.env`, OpenChamber, a terminal in ~/Projects) are off-limits for tests. Model inference (Holo4, grounders, omni) runs on the user's Mac or desktop (Windows, RTX 4090, 96 GB RAM), reached over Tailscale.
- Where this tracker and the report disagree, this tracker wins (see Decisions: "2026-10-07 corrections").
- Harness credentials (VM): Codex works via ChatGPT login (gpt-6.1-sol). opencode works with Z.AI (GLM-5.3); other providers are not configured. Claude Code's OAuth is expired. pi 0.85 has no models and predates MCP. Harness CLIs live in `~/.nvm/versions/node/v24.20.0/bin`, which is not on the non-interactive PATH.
- Pending user action: `gh auth login` on the Mac so the two upstream reports in `upstream/` can be filed (approved by user); re-login Claude Code on the VM.
- Next action: Phase 3: grounding + reliability. Holo4 `locate`/`delegate` via an OpenAI-compatible sidecar on the 4090 desktop (llama.cpp CUDA), verify-after-act, and a 20–30-task eval with a Holo baseline. In parallel: Phase 4 cross-platform engine adapters (Windows first: the desktop is Windows).

## Active workstreams

### Phase 0 — Validate on VM (1–2 days)

- Status: done for what is measurable now. Engine: go. Media matrix measured for Codex (`phase0/media-probe/RESULTS.md`). Claude/opencode/pi rows wait on credentials.
- Owner: unassigned (any harness)
- Current evidence: `phase0/cua-smoke/results/20261007-194215.json`; details in `.project/sessions/2026-10-07-1942-phase-0-cua-smoke-on-linux-vm.md`.
- Completion evidence: smoke script + log; measured harness media matrix from a probe MCP server; Holo4 serving check on the desktop (or Mac) reachable from the VM; go/no-go on Cua as Linux engine.
- Next action: run the media probe in ≥2 harnesses. Optional: Holo4 serving check on the desktop (deferred to Phase 3 by decision).
- Re-run engine smoke any time: `uv run --script phase0/cua-smoke/smoke.py`.
- Stop condition: type/click reliable on Mousepad, Thunar, Chromium → Cua is the Linux engine; otherwise switch Linux adapter to agent-sh/computer-use-linux and file upstream bugs.

### Phase 1 — Contract + Linux wrapper (1–2 weeks)

- Status: done (2026-10-07), including 1b (browser).
- Owner: unassigned
- Evidence:
  - `contract/tools.json` (17 tools) and `contract/engine/cua-0.34.0-linux-tools.json` (engine snapshot).
  - `src/cctl/`: engine, MCP server, CLI + daemon, remote `--host`.
  - `tests/test_unit.py`: 28 pass.
  - `acceptance/phase1.py`: 14/14 over local stdio, SSH stdio and `--host` passthrough.
  - `acceptance/harness_task.sh`: PASS for codex and opencode; Claude Code passed via CLI.
  - `skills/computer-use/SKILL.md`; `packaging/` (Claude plugin scaffold + per-harness snippets).
- 1b evidence: `src/cctl/browser.py`; `acceptance/phase1b.py` 10/10 against `acceptance/web/form.html`; `TASK=browser acceptance/harness_task.sh` PASS for codex (7 calls) and opencode (8 calls).
- Carried forward (small): event-log rotation; `run` output streaming; an Electron a11y launch helper (`--force-renderer-accessibility`); attaching to the user's own browser (`existing_profile` needs a Cua launch grant).
- Next action: none; Phase 2 is next.

### Phase 2 — Media (done 2026-10-08)

- Evidence:
  - `src/cctl/media.py` (ffmpeg x11grab clips → annotated contact sheet + MP4; PulseAudio capture → levels, sound ranges, waveform, faster-whisper transcript with uncertain words, inline WAV; RapidOCR PP-OCRv6 with line and word boxes).
  - `acceptance/phase2.py`: 12/12.
  - `TASK=clip|audio acceptance/harness_task.sh`: PASS in Codex (gpt-6.1-sol) and opencode (GLM-5V-Turbo clip, GLM-5.3 audio).
- Lessons:
  - Contact-sheet captions must sit below the tiles, never over content.
  - Change detection needs a 640-px thumbnail to register typing.
  - faster-whisper 1.2.1 breaks with current PyAV; feed it PCM directly.
  - Whisper base/small mishear invented words in espeak, so the test uses real nouns and transcripts flag uncertain words.
  - Cua ends idle sessions; revive them with `start_session`.
  - Harness runs over SSH need stdin from /dev/null (`codex exec` waits on a piped stdin).

### Phase 3 — Grounding + reliability (active, started 2026-10-08)

- Evidence so far:
  - `eval/tasks.py` and `eval/run.py`: 16 natural-language tasks across editor, windows, processes, apps, dialogs, OCR, browser, mixed and media. Each uses random values and is checked in code (files, process state, window geometry, answers, event log); GUI-only tasks fail if `run` was used. Results go to `eval/results/<ts>-<label>.{jsonl,md}`.
  - `locate` (`src/cctl/grounding.py`): an OpenAI-compatible grounding sidecar using H's element-localization contract (JSON x/y in 0–1000 of the exact image sent), with zoom-refinement second pass and a marked image back. Hidden until `grounder_url`/`grounder_model` are set. Unit-tested against a fake server; setup guide in `docs/grounder-setup.md`.
  - `then=screenshot|observe|wait_stable|browser_snapshot` on input tools returns the after-state in the same call.
  - `apps launch --a11y` adds `--force-renderer-accessibility` for Electron/Chromium; events.jsonl rotates at 20 MB.
- Blocked on (user): an endpoint for Holo4 (llama.cpp on the 4090 desktop over tailnet, or an H API key) to measure `locate`.
- Baselines (2026-10-08):
  - Codex/gpt-6.1-sol medium: 16/16 (`eval/results/20261008-040631-codex-sol-medium-v2.md`).
  - opencode/GLM-5.3 (text-only): 15/16, then 16/16 after `record_clip ocr` + `text_changes` (`20261008-043652-opencode-glm53.md`, `…051059-opencode-glm53-clip-ocr2.md`).
- Fixes the eval forced:
  - xdotool `mousemove --sync` hung ~15 s with Cua's XInput2 pointers; removed.
  - windows move offsets by `_NET_FRAME_EXTENTS` (the WM places the frame, callers speak client coordinates).
  - type_text verification is best-effort when a dialog closes.
  - Eval runner: free ports, UTF-8 pages, session env for checks, `PWD` for opencode (it resolves the project and `opencode.json` from `$PWD`), harness-shell detection (shell `cctl …` counts as toolkit use).
  - Text-only guidance in MCP instructions and the skill.
- Model observations:
  - GLM-5V-Turbo ignored the connected MCP tools and went through the shell instead.
  - GLM-5.3 is slow (20–60 s per step) but follows tool guidance.
  - Mousepad's Find and Replace dialog hides its buttons from AT-SPI until text is entered, so it remains the hardest task.
- Grounder live (2026-10-08): Holo4-35B-A3B q4_k_m + mmproj on this Mac via llama.cpp 0.6.0, `llama-server --host <tailnet-ip> --port 8080 --alias holo4 -ngl 999 -fa on -c 32768 -np 2 --image-min-tokens 1024`, run with nohup (log `~/models/holo4/server.log`). The VM's `~/.config/cctl/config.toml` points `grounder_url` at it. Requests must send `chat_template_kwargs.enable_thinking=false`; with thinking on, the model spends its token budget thinking and returns empty content.
- Grounding bench (`eval/grounding_bench.py`, labeled menus/buttons in Mousepad + galculator, a11y bounds as truth): 36/36 hits with and without the refine pass. Median latency 1.26 s single pass, 2.21 s with refine.
- **Decision: keep `locate` as an optional sidecar, recommended for hosts without vision.**
  - `canvas_click_shape` (unlabeled shapes on a canvas), 3 reps each:
    - GLM-5.3 text-only without locate: 1/3 (timeouts, 26–34 calls).
    - GLM-5.3 with locate: 3/3 (6–22 calls).
    - Codex/gpt-6.1-sol (vision) without locate: 3/3 (4 calls).
  - Vision hosts don't need it; text-only hosts go from failing to passing.
- Next action: run the full suite with a text-only host + locate to check for regressions; add harder tasks (dense icon toolbars, drag-and-drop, multi-app workflows); measure Holo4 on unlabeled icon targets where refine may matter.

### Phase 4 — Cross-platform + transport (active, 2026-10-08)

- Targets (user approved, "be cautious"):
  - this Mac: M5 Max, 128 GB, macOS 27.0.1;
  - Windows `windows-pc` (tailnet <tailnet-ip>, a local user, OpenSSH on 22). Key auth uses `~/.ssh/id_ed25519` (the user's general key); the user still has to authorize it on Windows (encoded PowerShell command given).
- Done:
  - `src/cctl/cua_input.py`: Cua desktop-coordinate input backend (click/scroll/drag/keys/windows) with the same interface as X11. The engine now uses `self.input` (xdotool on X11, Cua elsewhere).
  - On non-Linux, the engine skips session discovery and runs `cua-driver mcp` without `--socket`; on macOS that proxies to CuaDriver.app, so TCC stays with Cua's signed identity.
  - Clips on non-X11 use Cua start/stop_recording, then ffmpeg crop.
  - VM run with `CCTL_INPUT_BACKEND=cua`: phase1 acceptance 13/14. The one failure was a quit blocked by a save prompt (the editor had unsaved changes); input itself works.
  - Mac: CuaDriver.app 0.34.0 installed in /Applications (signature verified, team YCK386LBJ7), CLI symlinked to `~/.local/bin/cua-driver`, telemetry off. `cctl` installed with `uv tool install --editable`. llama.cpp 0.6.0 via brew. Holo4-35B-A3B GGUF (q4_k_m 19.8 GB + mmproj 0.84 GB) downloading to `~/models/holo4`.
- Pending (user):
  - `cua-driver permissions grant` on the Mac (Accessibility + Screen Recording approval).
  - Authorize the SSH key on windows-pc.
- Windows (2026-10-08): `acceptance/windows_smoke.py` 8/8 from the Mac over SSH (`cctl mcp` on windows-pc): doctor, windows, 5120×1440 desktop screenshot, Calculator 123×456 via UIA element clicks, display read back ("56,088"), window closed.
  - Architecture: SSH sessions are not the desktop session. Cua's named pipe only serves its own logon session, and its loopback HTTP MCP makes every request a separate session (element tokens die between calls).
  - So `cctl serve` runs **in the desktop session**, started by a one-shot scheduled task that is removed immediately; no autostart is left behind. It talks stdio to `cua-driver mcp`.
  - SSH-side `cctl mcp` (default on win32; `--direct` opts out) and the CLI proxy to it over loopback TCP with a token file, carrying images and audio inline.
  - Window close/minimize/maximize use Win32 messages, because Cua's alt+F4 does a UIA accelerator scan that timed out on Calculator. CLI forces UTF-8 stdout (cp1252 console).
  - Tooling: `phase4/winps.py` runs PowerShell on windows-pc via -EncodedCommand. Cua 0.34.0 is at `~\.cua-driver\0.34.0\…\cua-driver.exe` (Authenticode: Cua AI, Inc.); cctl is at `~\computer-ctrl` (uv tool, editable).
- Open questions:
  - (resolved, see above) Windows OpenSSH sessions can't see the interactive desktop. Cua's daemon must run in the logged-in session (`cua-driver autostart enable` logon task), and `cua-driver mcp` from SSH must reach it via its named pipe. To verify.
  - macOS audio capture (needs ScreenCaptureKit audio or a loopback device) and Windows audio (WASAPI loopback): not implemented.
  - Hover (`move`) has no Cua equivalent; not implemented.
- Owner: unassigned
- Completion evidence: per-phase exit criteria in the report's phase table.

## Important paths and artifacts

- `reports/Harness agnostic computer use toolkit.md`: synthesized research report; decision, architecture, tool surface, phase plan.
- `research_notes/Harness agnostic computer use toolkit/`: seven sourced research notes (vendor APIs, OS plumbing, existing toolkits, Cua Driver deep dive, harness integration, browser automation, Holo4 + grounders).
- `AGENTS.md`: handoff entry point for any harness working on this project.
- `src/cctl/`: the toolkit. `engine.py` holds the tools, `server.py` MCP, `cli.py` and `daemon.py` the CLI, `frames.py` coordinate mapping, `textentry.py` typing routes, `session_env.py` session discovery and the Cua daemon, `x11.py` xdotool/EWMH/health.
- `contract/tools.json`: the tool contract, the source of truth for names, schemas and descriptions.
- `acceptance/`: `phase1.py` (scripted MCP acceptance) and `harness_task.sh` (natural-language GUI task per harness, verified in code + event log).
- `upstream/`: drafted trycua/cua reports (comment for #4754; new issue for key-route Unicode corruption).
- VM: `~/computer-ctrl` (rsync of the repo) installed with `uv tool install --editable`, giving `~/.local/bin/cctl`. Event log: `~/.local/state/cctl/events.jsonl`. Artifacts: `~/.cache/cctl/artifacts/<run>/`.
- `phase0/media-probe/server.py`: MCP server (Python, mcp SDK 2.x) that hides random codes in image, image+structuredContent, audio, video blob, resource_link and file-path results.
- `phase0/media-probe/run.sh`: runs the probe headless in claude/opencode/pi/codex and grades what reached the model (`runs/<harness>-<ts>/grade.json`).
- VM: Cua Driver 0.34.0 at `~/opt/cua-0.34.0/`, symlinked to `~/.local/bin/cua-driver`. Daemon started with `serve --no-overlay`; log at `~/.cache/cua-driver/serve.log`. Telemetry disabled.

## Recent attempts and results

### 2026-10-07 — VM probe (`ssh user@linux-vm`)

- Intent: Establish the test target's real environment.
- Method: Read-only SSH probe (os-release, loginctl, ps, lspci, tool lookup).
- Result: Debian 13, kernel 6.12, **XFCE on X11 via lightdm (not Wayland)**, DISPLAY=:0, XAUTHORITY=~/.Xauthority, admin owns seat0 session. Ryzen 7 8745HS / Radeon 780M passed through (`/dev/dri`, `/dev/kfd`), 6 vCPU, ~11 GiB RAM, ~164 GB free. Present: python3, uv, docker, xdotool, chromium, firefox. Missing: node/bun, ffmpeg, claude/codex/opencode/pi (only `agy`, `cairn` in ~/.local/bin).
- Evidence: this session's probe output.
- Follow-up: install ffmpeg, libxi6, at-spi2-core, vulkan-tools; determine PipeWire vs PulseAudio.

### 2026-10-07 — Phase 0 start

- Intent: Install Cua on the VM and smoke-test it; measure what each harness forwards.
- Method: apt install of ffmpeg, vulkan-tools and wmctrl (passwordless sudo works). Downloaded the pinned 0.34.0 linux-x86_64 tarball and verified it against SHA256SUMS. Ran `doctor`, `list-tools` and `serve --no-overlay`, then `call get_desktop_state`.
- Result:
  - `doctor` OK: X11 on :0, 11 windows, AT-SPI bus reachable, telemetry off. 64 tools listed. Screen is 1920×1080, scale 1.0.
  - `get_desktop_state` with `max_image_dimension:1568` took 71 ms and returned a 1568×882 PNG with `frame_scale` 1.2245.
  - **The image was all black.** light-locker had locked the session and switched seat0 to the lightdm greeter (VT8, :1), leaving admin's :0 on VT7 inactive. DPMS also reports "Monitor is Off". Cua's `doctor` did not flag either condition.
  - Audio stack is PulseAudio 17, not PipeWire. at-spi2-core, libxi6 and mesa-vulkan are already installed.
  - Media probe: the server works over raw stdio (all six result types emitted). No harness run could complete yet (see Blocked on).
- Fix the user must apply (the agent may not change lock settings):
  `ssh user@linux-vm 'export DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; mkdir -p ~/.config/autostart && printf "[Desktop Entry]\nHidden=true\n" > ~/.config/autostart/light-locker.desktop; pkill light-locker; P=/xfce4-power-manager; xfconf-query -c xfce4-power-manager -p $P/dpms-enabled -n -t bool -s false; xfconf-query -c xfce4-power-manager -p $P/blank-on-ac -n -t int -s 0; xfconf-query -c xfce4-power-manager -p $P/lock-screen-suspend-hibernate -n -t bool -s false; xset s off -dpms; sudo chvt 7'`
- Follow-up (toolkit requirement): our `doctor`/`observe` must detect an inactive or locked session (loginctl Active=no, a light-locker/greeter window, DPMS off) and an all-black frame. It should return an explicit `display_unavailable` error, never a black screenshot.

### 2026-10-07 — Deep research (7 tracks)

- Intent: Decide build-on vs fork vs fresh; learn state of the art.
- Result: Recommendation to wrap pinned Cua Driver; Holo4 does not fit the VM (Q4 ≈21 GB vs 11 GiB); a 2–4B grounder on llama.cpp Vulkan is feasible.
- Evidence: report + notes above. Nothing tested hands-on yet.

## Decisions

### Phase 1 implementation choices (2026-10-07)

- Language: Python 3.11+ via uv, MCP SDK 2.x lowlevel server. The contract is language-neutral JSON so a later Rust port stays mechanical.
- Input on X11: pixel actions use xdotool, which sends real pointer/keyboard events and reaches canvases, Electron and games. Element actions, capture, the a11y tree, set_value and the clipboard use Cua. Pixel actions on a window frame raise that window first, because window captures show occluded content but real clicks hit the top window.
- Element identity: tokens are refreshed by role + identical bounds, falling back to index + label. Indices shift when toolbars change, and GtkTextView's label is its content.
- Zoom: fresh native capture, cropped and enlarged up to 4× (default long edge 1024), with its own frame id usable for clicks.
- Statefulness: one long-lived Cua connection per MCP session; the CLI shares state through `cctl serve` (auto-started, 30 min idle exit).
- Name: `cctl` (renameable).
- OCR backend: RapidOCR (Apache-2.0, ~30 MB, works on any frame including zoom and browser viewport, cross-platform) over Cua's perception extension (~405 MB per platform, catalog env at daemon launch, Cua captures only). Perception remains an option for icon detection later.
- Speech-to-text: local faster-whisper `small` on CPU (optional `stt` extra), or any OpenAI-compatible `/audio/transcriptions` endpoint (e.g. the 4090 desktop) via `stt_url`.
- Media results: the contact sheet or waveform is the inline image; raw MP4/WAV paths are always returned; WAV is attached inline only on request (Codex didn't pass audio to gpt-6.1-sol in the probe).
- Browser (1b): isolated Chromium via Cua `browser_prepare` (throwaway or named profile). Sandbox profile uses foreground trusted input; personal profile stays background and falls back to `dom_event` for ref clicks. `browser_act` never reads CDP state afterwards, because any snapshot or re-bind invalidates the caller's refs; the page title comes from the X11 window title. Cua browser refusals (`effect: refused` + `error{}`) are errors.

### Phase 0 wrapper requirements (2026-10-07, from smoke evidence)

- Text entry: never trust `type_text` for non-ASCII. It silently drops (a11y route) or corrupts (key route) while reporting success. Route non-ASCII through `set_value` (editable a11y element) or clipboard + paste, restore the clipboard, and verify by readback where an a11y value exists.
- Zoom: own it. Crop from a native-resolution capture and upscale to the image budget. Cua's `zoom` is window-only, a crop with no magnification, and ≤500 px.
- Display availability: `doctor`/`observe` must detect an inactive/locked session or DPMS-off and an all-black frame, and return `display_unavailable`. Cua's `doctor` misses this.
- Tool surface: expose ~20 tools. Cua's raw `tools/list` is 199 KB (~50k tokens).
- Result shape: mirror `structuredContent` into a compact text block. Cua's browser snapshot and window state put the payload only in `structuredContent`.
- Statefulness: the wrapper must hold one long-lived Cua connection (daemon socket) per agent session. Cua session labels end on disconnect, browser ids are per-bind, and `kill_app` is per-connection in standard mode. The CLI front-end goes through the wrapper's daemon, not one-shot `cua-driver call`.
- Electron/Chromium apps: launch with `--force-renderer-accessibility` (or `ACCESSIBILITY_ENABLED=1`) when the a11y tree is needed. OpenChamber exposed 1 element without it.
- Batching: `run_actions` is absent in Linux 0.34.0, so `batch` is implemented in the wrapper.
- App isolation for tests: launch test apps with throwaway XDG dirs (Mousepad crash-restore prompts otherwise).

### 2026-10-07 corrections from user (override the report)

- Licensing is a non-issue (private, undistributed project). Use Cua's perception extension (OmniParser icon detection + OCR) as-is; "non-AGPL OCR" is no longer a gap. Holo4-27B's CC BY-NC license is also fine.
- Policy is per target profile. `sandbox` (the VM): Cua `unrestricted` mode, shell tool on, no app tiers. `personal` (Mac/desktop): bounded mode + tiers. Default profile for this project is `sandbox`.
- Holo4 role: optional, not core. The only architectural commitment now is a generic "sidecar model" setting: one OpenAI-compatible endpoint, used by `locate`, `delegate` and `describe_media`. Defer real work to Phase 3 and keep or drop it on eval evidence. Candidate roles, in order of expected value:
  1. Eyes for text-only local models: a11y tree + `locate`/`describe`. The user's pi local models (Qwen3.8-27B via mtplx) have no image input.
  2. `delegate(task)`: offload long GUI chores so the frontier model doesn't pay for every screenshot.
  3. Eval baseline: HoloDesktop CLI in the VM with `--base-url` pointed at the local server.
- Inference host: desktop with an RTX 4090 (24 GB) and 96 GB RAM, running Windows. vLLM needs WSL2, so use llama.cpp CUDA (or LM Studio) natively. Holo4-27B Q4 (~16–17 GB) fits in VRAM. Holo4-35B-A3B Q4 (~21 GB) is tight, so offload experts with `--n-cpu-moe`; only 3B parameters are active, so it should stay fast. The "time a 2B grounder on the VM's 780M" experiment is dropped.

### Engine: build on Cua Driver behind an owned wrapper (provisional)

- Choice: Pin trycua/cua `cua-driver` 0.34.0 (MIT, Rust) as engine; own a thin wrapper (Python + uv) for contract, output normalization, policy profiles, media broker (desktop zoom, clips, audio), artifacts.
- Rationale: only active engine covering Win/macOS/X11/Wayland with MCP + CLI + skill already; gaps (audio, on-demand clips, desktop zoom, Codex image-drop with `structuredContent`) fit outside it.
- Alternatives rejected: fork (368k LOC, 113 releases since May, 9 breaking, one lead dev); fresh build (months for UIA/TCC/SCK/Wayland); per-OS server assembly (incompatible contracts).
- Reconsider when: Phase 0 shows unreliable X11 input; Cua licensing/telemetry changes; Wayland becomes primary target and Cua stays weak there.

### Output shape for image tools

- Choice: one text block (JSON: path, dims, scale, frame, capture_id) + at most one image; no `structuredContent`/`outputSchema`; long edge ≤ ~2000 px default.
- Rationale: Codex drops all images when `structuredContent` is present (codex#10334); pi resizes to 2000; Codex caps 2048.
- Reconsider when: Phase 0 media probe measures different behavior.

### Remote transport: SSH stdio first

- Choice: `ssh -T user@linux-vm 'toolkit mcp'` over Tailscale; CLI gets `--remote` that pulls artifacts back locally. Tailnet HTTP + bearer token later.

## Open questions and theories

### Does Cua Driver type/click reliably on XFCE/xfwm4?

- Type: question
- Status: open
- Evidence needed: Phase 0 smoke (cua#3774, #3237, #3871, #4754).
- Next validation: Phase 0.

### What does each harness actually forward (image / image+structuredContent / audio / video)?

- Type: question
- Status: open (current matrix is from source reading, not measurement)
- Next validation: 50-line probe MCP server run in Claude Code, Codex, opencode, pi, `agy`.

### Is a Holo4 grounder / sub-agent worth it?

- Type: theory. Useful for open or cheap host models and dense UIs. Frontier hosts already ground at ~85–88% on ScreenSpot-Pro.
- Status: open
- Next validation: serve Holo4-35B-A3B on the desktop; measure locate latency and accuracy from the VM; Phase 3 eval vs the host model's own grounding.

### Unknowns

- Desktop GPU and OS (decides vLLM vs llama.cpp for Holo4); Mac unified memory size.
- What `agy` and `cairn` on the VM are (agy presumed Antigravity CLI); audio stack on the VM; lightdm XAUTHORITY path conventions on Debian 13.

## Completed or resolved

- 2026-10-07: Project scaffolded; research complete; report delivered.
- 2026-10-07: User disabled light-locker/DPMS on the VM; seat0 switched back to the admin session with `loginctl activate 2`.
- 2026-10-07: Phase 0 engine smoke: 10 PASS / 1 KNOWN; go on Cua for Linux (see session note).
- 2026-10-07: Media probe measured in Codex 0.161/gpt-6.1-sol: image native; image+structuredContent native (codex#10334 not reproduced); audio no; video only via an agent ffmpeg workaround; file path yes; structured-only yes.
- 2026-10-07: Phase 1 core: cctl built; 3-harness GUI task PASS.
- 2026-10-07: Phase 1b browser tools; browser task PASS in Codex and opencode.
- 2026-10-08: Phase 2 media tools; clip + audio tasks PASS in Codex and opencode; regression 14/14, 10/10, 12/12.
