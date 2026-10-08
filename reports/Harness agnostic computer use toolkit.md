# Wrap Cua Driver, Then Own the Gaps

Don't build this from scratch. As of October 2026, **Cua Driver** (trycua/cua, MIT, Rust, v0.34.0 released 2026-10-05) is the only actively released engine that drives Windows, macOS, Linux X11 and, with limits, Wayland through native accessibility APIs. It exposes the same 64 tools over MCP stdio, a shell CLI and Agent Skills, and it already handles SSH-remote operation, window zoom, Chromium control over CDP, and trajectory video. Use it as a **pinned, unforked engine behind a thin wrapper you own**. Cua cut 113 tagged releases in under five months, nine of them breaking. The pieces you most want are exactly the ones it lacks: audio capture (absent from the driver entirely), short clips returned to the model on demand, desktop-scope zoom, MIT-clean OCR, restrictive defaults (its default mode needs no prompts and telemetry is on), and output shaped around harness quirks such as Codex silently dropping images whenever `structuredContent` is present. The harnesses themselves limit how far audio and video can go. Every major harness passes MCP images to the model, but only Gemini CLI is verified to forward audio and video. Your VM's `agy` binary is most likely its successor, Antigravity CLI. Everywhere else, clips must degrade to contact sheets and audio to transcripts. The VM itself is better news than you expected: it runs XFCE on **X11, not Wayland**. That is the one Linux target where capture, input, window control and AT-SPI all work without consent prompts, so the first milestone is a one-day smoke test of `DISPLAY=:0 cua-driver mcp` over Tailscale SSH, aimed at Cua's open X11 bugs. Holo4 cannot run on the VM, because its Q4 weights need about 21 GB against 11 GiB of RAM. A 2B–4B Qwen3-VL-derived grounder on llama.cpp's Vulkan backend can. H Company's harness also has ideas worth borrowing: a stateless locate-by-description tool, zoom refinement, verification in code, the "skill says when, MCP says how" split, and a hard kill switch.

## Every capability has a known per-OS mechanism, and the VM sits on the forgiving one

None of the requested capabilities is still an open research problem at the API level. Each OS has a settled capture, input, window and accessibility stack. Working toolkits differ from broken ones in permissions and session plumbing. Which process owns the consent? Does the daemon live inside the graphical session? How do coordinates convert between screenshot pixels and OS input space? The table gives the recommended primary mechanism for each capability. The paragraphs after it cover the traps.

| Capability | Windows | macOS | Linux X11 (your VM) | Linux Wayland |
|---|---|---|---|---|
| Screenshot | Windows.Graphics.Capture; DXGI Desktop Duplication fallback; GDI last | ScreenCaptureKit (`SCScreenshotManager`) | XShm/GetImage on root, crop via RandR | Portal Screenshot/ScreenCast (GNOME/KDE); `ext-image-copy-capture` or `wlr-screencopy` (wlroots); KWin `ScreenShot2` |
| Mouse/keyboard | `SendInput` (UIPI-limited) | `CGEventPost` (Accessibility grant) | XTest | RemoteDesktop portal + libei `ConnectToEIS`; wlr virtual pointer/keyboard; uinput last |
| Windows | `EnumWindows`, DWM bounds, `SetWindowPos` | `CGWindowListCopyWindowInfo` + AX | EWMH (`_NET_CLIENT_LIST`, `_NET_ACTIVE_WINDOW`) | Compositor-specific: GNOME Shell extension, KWin script, `hyprctl`, `swaymsg`, `niri msg` |
| Accessibility tree | UI Automation | `AXUIElement` | AT-SPI2 over D-Bus (must be enabled) | AT-SPI2; coordinates often window-relative |
| Processes / launch | `sysinfo`/`psutil`; `ShellExecuteExW` | same; `NSWorkspace` | same; `xdg-open`/`gtk-launch` | same |
| OCR | `Windows.Media.Ocr` | Apple Vision | RapidOCR (PP-OCR ONNX) | RapidOCR |
| System/mic audio | WASAPI loopback; per-process loopback on build 20348+ | SCK `capturesAudio` (13+), mic (15+) | PipeWire sink monitor or Pulse `.monitor` | same |
| Video clip | ffmpeg `ddagrab` or WGC + Media Foundation | `SCStream` → `AVAssetWriter` | ffmpeg `x11grab` | Portal ScreenCast → PipeWire → encoder |
| Main trap | Silent UIPI failure; secure desktop; capture border | TCC "responsible process"; re-prompts | AT-SPI enablement; session environment over SSH | No global APIs; consent dialogs; compositor fragmentation |

**Windows** rewards the newer APIs. Windows.Graphics.Capture handles multi-GPU systems automatically, while Desktop Duplication must run on the GPU that drives the display ([OBS forum](https://obsproject.com/forum/threads/windows-graphics-capture-vs-dxgi-desktop-duplication.149320)). Removing WGC's yellow capture border requires a user consent prompt plus a package-manifest capability, available from build 20348 ([Microsoft Learn](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession.isborderrequired)), so an unpackaged CLI will show the border. The serious trap is input. `SendInput` is blocked by UIPI when the target runs at a higher integrity level, and "neither GetLastError nor the return value will indicate the failure" ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)). The toolkit therefore has to check the target's integrity level itself and report "target is elevated" rather than claim success. The process must also declare Per-Monitor-v2 DPI awareness before it touches any coordinates ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/desktop/hidpi/dpi-awareness-context)). For audio, per-process loopback capture exists from build 20348 ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/audioclientactivationparams/ne-audioclientactivationparams-audioclient_activation_type)). ffmpeg's `ddagrab` hands D3D11 frames to hardware encoders ([FFmpeg wiki](https://trac.ffmpeg.org/wiki/Capture/Desktop)). An OpenSSH session cannot drive the interactive desktop, so the daemon must run in the logged-on session. Cua's `autostart` registers a logon Scheduled Task on Windows for exactly this reason ([Cua CLI reference](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/cli/mcp.mdx)).

**macOS** is mostly a consent problem. `CGWindowListCreateImage` is obsoleted in the macOS 15 SDK, which leaves ScreenCaptureKit as the only capture path ([Apple forums](https://developer.apple.com/forums/thread/740493)). TCC judges Screen Recording against the *responsible* process, not the parent ([openclaw#14138](https://github.com/openclaw/openclaw/issues/14138)). On Tahoe, a Python helper that showed as "allowed" still failed with error -3801 ([cua#870](https://github.com/trycua/cua/issues/870)). Sequoia re-prompts for Screen Recording monthly ([9to5Mac](https://9to5mac.com/2024/08/14/macos-sequoia-screen-recording-prompt-monthly/)). The robust design is a daemon inside a stably signed .app, which Cua already ships as `CuaDriver.app`. Cua warns that a gateway must connect to the app-owned socket rather than spawn the daemon itself; otherwise the grants attach to the gateway's identity ([Cua EMBEDDING.md](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/rust/Skills/cua-driver/EMBEDDING.md)). ScreenCaptureKit captures system audio from macOS 13 and the microphone from macOS 15 ([screencapturekit crate](https://docs.rs/crate/screencapturekit/8.0.1)).

**Wayland is where Linux is heading, and it is the hardest target.** GNOME 50 removed the X11 session ([heise](https://heise.de/-11067046)). KDE Plasma 6.8, due around October 14, 2026, is Wayland-exclusive ([Phoronix](https://www.phoronix.com/news/KDE-Plasma-68-Wayland-Exclusive)). Wayland deliberately offers ordinary clients no global screenshot, input or window-list API, which leaves three tiers:

- **GNOME and KDE:** xdg-desktop-portal ScreenCast plus RemoteDesktop with libei. `persist_mode=2` restore tokens avoid repeat dialogs, but each token is single-use ([portal spec](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html); [Who-T](http://who-t.blogspot.com/2026/07/libei-integrations-in-xdg-remotedesktop.html)).
- **wlroots compositors:** direct protocols. `ext-image-copy-capture` succeeds the deprecated `wlr-screencopy` ([wayland.app](https://wayland.app/protocols/ext-image-copy-capture-v1)). Hyprland's portal-based RemoteDesktop is still an unmerged PR ([xdph #402](https://github.com/hyprwm/xdg-desktop-portal-hyprland/pull/402)).
- **Fallback:** uinput, which cannot see which window has focus.

GNOME Shell's own Screenshot D-Bus interface has answered only allowlisted callers since Shell 41 ([gnome-shell MR !1970](https://gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/1970)). Even Cua concedes that on Wayland "an ordinary client cannot send raw input to an unfocused, occluded window" ([Cua platform support](https://cua.ai/docs/cua-driver/concepts/platform-support.md)). XFCE's Wayland compositor, xfwl4, is only a 4.21 preview ([Lamco matrix](https://lamco.ai/products/lamco-rdp-server/platforms/)), so your XFCE VM will stay on X11 for the foreseeable future.

**Your VM is on X11, which is the easy case.** XShm capture, XTest input, EWMH window control, AT-SPI2 and ffmpeg `x11grab` all work without per-use prompts. Debian 13 ships Xfce 4.20 and PipeWire 1.4.2. PipeWire is installed by default "at least if you install Gnome or KDE" ([Debian wiki](https://wiki.debian.org/PipeWire)), so on an Xfce install the audio code has to detect PipeWire versus PulseAudio. AT-SPI must be enabled, and Chromium-family apps have historically needed `--force-renderer-accessibility` ([orca-list](https://mail.gnome.org/archives/orca-list/2020-July/msg00122.html)). Cua has an open issue saying the flag is still needed on Linux ([cua#4768](https://github.com/trycua/cua/issues/4768)). Apps launched outside the session "couldn't register with accessibility bus" ([Xfce forum](https://forum.xfce.org/viewtopic.php?id=14239)). So the SSH user must own the XFCE session, and `DISPLAY`, `XAUTHORITY` and the D-Bus address must come from that session. On X11, scaling is per session rather than per monitor, so screenshot pixels normally equal XTest coordinates (background knowledge, not re-verified).

**The library ecosystem favors Rust, and the commodity pieces are solved.** xcap 0.9.8 (August 2026) captures on Windows, macOS and X11 but marks Wayland "not fully supported in some special scenarios" ([lib.rs](https://lib.rs/crates/xcap)). enigo flags both Wayland and libei input as experimental ([enigo](https://github.com/enigo-rs/enigo)). nut.js now sells its prebuilt packages ([nut.js](https://nutjs.dev/docs/getting-started)). Process listing is commodity work with `sysinfo` or `psutil` ([psutil](https://pepy.tech/projects/psutil)). For OCR, the native engines are cheapest. One small benchmark measured Apple Vision at 3.2 images/s with 90.0% accuracy and Windows OCR at 1.2 images/s with 95.2%, on an unspecified dataset ([uni-ocr](https://docs.rs/crate/uni-ocr/latest)). Tesseract took about 4 s per 1080p screenshot ([tesseract-ocr group](https://groups.google.com/g/tesseract-ocr/c/c_S7GG5njkw/m/OPQ6q5zBAQAJ)), and one developer dropped it for RapidOCR because it "produced garbage on real screenshots" ([Mic92](https://git.thalheim.io/Mic92/dotfiles/src/branch/main/pkgs/live-text/live_text/ocr.py)). Running RapidOCR on crops rather than full screens is the portable default.

## Downscaling, not clicking, is where small targets die

The worry that vision models downscale and miss small detail is correct, and it is now the main grounding failure mode rather than a side issue.

**Every pipeline caps or shrinks screenshots before the model sees them:**

- **Anthropic.** Opus 4.7 and later accept up to **2,576 px on the long edge (4,784 visual tokens)**. Earlier models top out at 1,568 px. Images returned to the new computer-use toolset are *rejected*, not downscaled, when oversized ([Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)).
- **Claude Code.** It shrinks a 3,456×2,234 Retina capture to about **1,372×887**, with no override ([Claude Code docs](https://code.claude.com/docs/en/computer-use)).
- **Codex.** It resizes to 2,048 px ([codex image utils](https://github.com/openai/codex/blob/main/codex-rs/utils/image/src/lib.rs)).
- **pi.** It resizes to 2,000×2,000 ([pi models docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md)).
- **OpenAI models.** They need `detail: "original"` to avoid a downscale ([OpenAI vision guide](https://developers.openai.com/api/docs/guides/images-vision)).
- **Gemini.** It requires its `ultra_high` resolution tier (2,240 tokens per image) for computer use ([Gemini docs](https://ai.google.dev/gemini-api/docs/media-resolution)).

Anthropic's own illustration makes the problem concrete: a **16 px checkbox on a 4K display shrinks to about 5 px at 1280×720** ([Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)).

**Zoom is the remedy with the strongest evidence. Overlays and tiling are not.** The training-free ZoomClick method shrinks the viewport around a first guess. It searches three levels deep at half size each step, with a 768 px minimum crop. That lifted Qwen3-VL-32B on ScreenSpot-Pro from **54.0 to 72.1**, and UI-Venus-72B from 61.4 to 73.1 ([ZoomClick](https://arxiv.org/html/2512.05941v1)). The same paper shows that crops that are too tight make models lose context and pick distractors, so a zoom tool needs a sensible minimum size. Anthropic made zoom a first-class action that is on by default in `computer_toolset_20260801`. Coordinates stay "in the pixel space of the full-display screenshots you return… Zoom images don't change this" ([Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)). Anthropic also reports that **tiling, coordinate-grid overlays and resampling-algorithm choice did not help** Claude ([Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)). Frontier models now ground natively at roughly 85–88% on ScreenSpot-Pro, with Opus 4.8 at 87.9% ([BenchLM](https://benchlm.ai/benchmarks/screenspot-pro)). They score that well only when the image arrives at their native budget. The design rule follows directly: send screenshots sized to the model's budget, and offer a `zoom` that returns a native-resolution crop in the same coordinate frame. Keep set-of-marks overlays optional. Claude Code already saves the full-resolution original of every MCP image to disk and gives Claude the path ([Claude Code MCP docs](https://code.claude.com/docs/en/mcp)), so a zoom tool that reads from saved originals fits naturally.

**Structured targets beat pixels wherever they exist, but pixels remain the universal fallback.** In the original OSWorld baselines, GPT-4 with only the accessibility tree scored 12.24%, against 5.26% for GPT-4V with only screenshots. Set-of-marks overlays *fell* to 4.59% with GPT-4o ([OSWorld paper](https://arxiv.org/html/2404.07972)). Anthropic's browser toolset tells Claude to prefer accessibility refs because "a scoped tree read often costs fewer input tokens" ([Anthropic browser docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/browser-use-tool)). One developer measured 2.4 KB of accessibility text against a 16 KB screenshot for the same page ([dev.to](https://dev.to/siropkin/accessibility-tree-vs-screenshots-the-token-math-behind-my-browser-agent-3fk9)). Pixel-only models are catching up, though: Fara-7B beat a GPT-4o set-of-marks agent on WebTailBench, 38.4 to 30.0 ([Microsoft Research](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/)). The toolkit should therefore return text first, with accessibility tokens, and treat screenshots and OCR as escalation paths. It should not pick one modality.

**The loop techniques have converged, and the toolkit's job is to support them, not reinvent them.** All three frontier vendors batch actions:

- **Anthropic** runs several `tool_use` blocks in order, halting at the first failure with a fixed "Not executed" reply for the rest ([Anthropic docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)).
- **OpenAI** returns a single `computer_call` holding an `actions[]` array ([OpenAI guide](https://developers.openai.com/api/docs/guides/tools-computer-use.md)).
- **Gemini** emits parallel function calls, each carrying an `intent` string ([Gemini docs](https://ai.google.dev/gemini-api/docs/computer-use)).

Anthropic recommends keeping the three most recent screenshots and pruning in batches every 25 turns, which protects the prompt cache ([Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)). OpenAI now recommends *code execution* (PyAutoGUI or Playwright) over its computer tool for GPT-6 Astra ([OpenAI guide](https://developers.openai.com/api/docs/guides/tools-computer-use.md)). That argues for exposing a scriptable CLI alongside structured tools. Best-of-N with a judge reached 72.6% on OSWorld in Agent S3, at about $0.72 and 891 s per GPT-5 rollout ([Agent S3](https://arxiv.org/html/2510.02250v2)). That makes it an evaluation technique, not an interactive one.

OSWorld-Verified is effectively saturated: the top entry is at 90.19% against a human baseline of 72.36% ([Presenc](https://presenc.ai/research/osworld-computer-use-leaderboard-2026)). The frontier has moved to long-horizon OSWorld 2.0 ([OSWorld 2.0](https://osworld-v2.xlang.ai/)). Coordinate conventions still differ across vendors and models:

- **Anthropic and OpenAI:** absolute screenshot pixels.
- **Gemini:** a 0–999 grid.
- **Qwen3-VL-derived grounders:** 0–1000 relative coordinates.

A harness-agnostic server must therefore stamp every capture with an explicit frame and accept targets in a declared frame.

## Cua Driver is the only engine that spans all four desktops

The field splits into one cross-platform engine, a handful of strong single-OS servers, and many projects that are agents rather than tool layers.

| Project | Platforms | Surfaces | License | State, Oct 2026 | Role for this toolkit |
|---|---|---|---|---|---|
| **Cua Driver** | Win 10/11, macOS 14+, X11, Wayland (limits) | MCP stdio, CLI, daemon, Py/TS SDK, skills | MIT (perception add-on partly AGPL) | 0.34.0 on 10-05; several releases a week | **Foundation engine** |
| computer-use-linux | Wayland-first, X11 incl. XFCE/EWMH | MCP stdio, CLI, skill, pi package | MIT | 0.7.12 on 10-07 | Linux fallback engine |
| Windows-MCP | Windows 7–11 | MCP stdio/SSE/HTTP with TLS and OAuth | MIT | 0.8.7 on 09-30; telemetry on by default | Reference for transport and processes |
| Peekaboo | macOS 15+ | CLI, MCP stdio | MIT | 4.9.0 on 10-07 | Reference for frame capture |
| clawdcursor | Win/mac/X11/Wayland | MCP, HTTP, CLI, plugin | MIT | 1.5.14; solo maintainer | Reference for safety and OCR fusion |
| Open Computer Use | mac/Linux/Win | 9-tool Codex-compatible MCP, CLI | MIT | 0.3.6 on 09-29 | Reference for session discovery |
| Terminator | Windows only now | MCP, SDKs | MIT | last release April 2026 | Not viable |
| lcu | X11, macOS | Harness adapters | MIT wrapper over OpenAI's runtime | needs ChatGPT app installed | Legally fragile |
| UI-TARS, Agent-S, UFO, Bytebot | Various | Agents with their own loops | Various | Bytebot archived March 2026 | Wrong layer |

Sources: [Cua README](https://github.com/trycua/cua), [computer-use-linux](https://github.com/agent-sh/computer-use-linux), [Windows-MCP](https://github.com/CursorTouch/Windows-MCP), [Peekaboo](https://github.com/openclaw/Peekaboo), [clawdcursor](https://github.com/AmrDab/clawdcursor), [Open Computer Use](https://github.com/iFurySt/open-codex-computer-use), [Terminator](https://github.com/mediar-ai/terminator), [lcu](https://github.com/amontlabs/lcu), [Bytebot](https://github.com/bytebot-ai/bytebot).

**Cua Driver already implements most of the requested surface.** Version 0.34.0 serves **64 MCP tools**: 59 on every OS, 4 Linux-only and 1 Windows-only. Every tool is also callable as `cua-driver <tool> '<json>'` from the shell ([tool index](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/mcp-tools/index.mdx)).

- **Screenshots.** Window screenshots default to 1,568 px on the long edge with automatic coordinate mapping. They come back inline or are written to disk via `screenshot_out_file` ([window-state tools](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/mcp-tools/window-state.mdx)).
- **Accessibility.** The tree renders as compact Markdown with element tokens. It is bounded to 250 nodes by default and supports diff reads.
- **Action results.** Actions return a structured `effect` (`confirmed`, `unverifiable`, `suspected_noop`, …) instead of claiming success blindly ([tool output format](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/docs/tool-output-format.md)).
- **Batching.** `run_actions` runs up to 32 steps with `wait_for` and `expect` checks ([batch tools](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/mcp-tools/batch.mdx)).
- **Browser.** The tools bind a CDP target to a verified native window and can launch an isolated profile that is deleted at session end ([browser guide](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/guides/browsers.mdx)).
- **Remote.** The SSH recipe is `codex mcp add cua-driver-vm -- ssh -T -o BatchMode=yes … cua-driver mcp` ([Cua VM guide](https://cua.ai/docs/cua-driver/guides/vms-and-remote.md)).
- **Harness setup.** Presets cover Claude Code, Codex, OpenCode and Pi, and `skills install` links the skill pack into each ([connect-your-agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md)).
- **Protocol.** It speaks MCP **2026-07-28** over stdio and keeps the legacy 2025-06-18 handshake ([mcp_wire.rs](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/rust/crates/cua-driver-core/src/mcp_wire.rs)).
- **Engineering rigor.** About 3,495 test attributes, release-gated desktop E2E on all three OSes, and signed, notarized macOS builds ([Cua workflows](https://github.com/trycua/cua/tree/b0a6348133a34b3d158eae38d06a606215eec6df/.github/workflows)).

The ecosystem is converging on it. Open Interpreter now delegates native-app control to trycua ([Open Interpreter README](https://raw.githubusercontent.com/openinterpreter/openinterpreter/main/README.md)). One pi computer-use package bundles Cua's binaries ([@amaster.ai/pi-computer-use](https://github.com/TGYD-helige/pi/blob/58a1389/packages/pi-computer-use/package.json)), and another has an open issue to adopt it ([injaneity#55](https://github.com/injaneity/pi-computer-use/issues/55)).

**Depend on Cua; don't fork it.** The driver is a 368,517-line, 16-crate Rust workspace. Its Linux and Windows tools live in single giant `impl_.rs` files ([Cargo.toml](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/rust/Cargo.toml)).

- **Churn.** It shipped **113 tagged releases between May 13 and October 5, 2026** ([tags](https://github.com/trycua/cua/tags)). Nine changelog sections have been marked BREAKING since July 22. The latest made element targeting token-only and closed the schemas ([CHANGELOG](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/rust/CHANGELOG.md)).
- **Bus factor.** One lead developer wrote **72% of non-bot commits** ([commit history](https://github.com/trycua/cua/commits/main/libs/cua-driver)).
- **Extensibility.** There is no plugin API for new tools. Upstream changes need a CLA and an RFC ([CONTRIBUTING](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/CONTRIBUTING.md)).
- **Telemetry.** It goes to PostHog EU and is **on by default**. It is content-free, but session events carry the MCP client name and the reported model and agent ([telemetry.rs](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/rust/crates/cua-driver/src/telemetry.rs)). A separate update check also runs by default ([operate guide](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/guides/operate.mdx)).
- **Default permissions.** The default `standard` mode "allows input to every app". The strong `bounded` mode, with deny-by-default capability manifests plus YAML or Rego policies, is opt-in ([permissions guide](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/guides/permissions.mdx)).

**Your VM is not yet covered by Cua's test matrix.** Debian 13 is not in the distro smoke matrix ([CI workflow](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/.github/workflows/ci-distro-compat-cua-driver.yml)), and Linux E2E runs under Xvfb with openbox, not xfwm4 ([E2E workflow](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/.github/workflows/e2e-rust-linux.yml)). Session discovery is half done. The driver finds `XAUTHORITY` and the D-Bus session (it even names `xfce4-session` as a known leader), but it does **not** discover `DISPLAY` ([issue #3047](https://github.com/trycua/cua/issues/3047)). There is also no official way to keep `serve` running on Linux ([issue #3957](https://github.com/trycua/cua/issues/3957)). Several open bugs hit the click-and-type loop directly:

- `type_text` delivering 0 of 10 characters while reporting success ([#3774](https://github.com/trycua/cua/issues/3774)).
- A systematic **~47 px title-bar offset** on pixel actions ([#3237](https://github.com/trycua/cua/issues/3237)).
- A full desktop freeze on Cinnamon at MCP startup ([#3871](https://github.com/trycua/cua/issues/3871)).

These bugs are why the first milestone is a validation run, not a build.

| Goal | Cua Driver 0.34.0 today | Fill it where | Effort |
|---|---|---|---|
| Screenshot zoom/crop | Window-only `zoom`, JPEG ≤500 px wide, 20% padding; desktop captures full-size by default ([screen tools](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/mcp-tools/screen.mdx)) | Wrapper: desktop/region zoom from saved full-res capture; default desktop cap | Easy |
| Mouse/keyboard | Background and foreground routes; open X11 bugs | Upstream reports; wrapper verify-after-act | Medium |
| Windows | List, raise, move/resize, menus; no minimize/close tool | Wrapper (hotkeys/EWMH) | Easy |
| Processes | Linux `list_apps` reads `/proc`; macOS lists GUI apps only; kills limited to driver-launched processes ([apps tools](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/mcp-tools/apps-and-windows.mdx)) | Wrapper `processes` tool (psutil) | Easy |
| OCR | Only an opt-in extension whose detector is AGPL-3.0-only ([notices](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/docs/perception-third-party-notices.md)); OCR quality issue open ([#4332](https://github.com/trycua/cua/issues/4332)) | Wrapper RapidOCR / PP-OCR ONNX (Apache-2.0) | Medium |
| Audio | **None anywhere in the driver**; the macOS recorder "does not enable system-audio capture" ([recording tools](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/mcp-tools/recording.mdx)) | Wrapper: PipeWire/Pulse, then WASAPI, then SCK | Medium–High |
| Short clips | Whole-session main-display `recording.mp4`, H.264 at 30 fps via ffmpeg `x11grab`; returned as a path only ([video_ffmpeg.rs](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/rust/crates/cua-driver-core/src/video_ffmpeg.rs)) | Wrapper `record_clip` with region, fps, contact sheet | Medium |
| Remote VM | Works as `DISPLAY=:0 cua-driver mcp` over SSH; no Linux remote docs | Wrapper session discovery + user unit; upstream #3047 | Easy |
| Network transport | Loopback-only legacy HTTP with bearer; OAuth still an RFC ([#3197](https://github.com/trycua/cua/issues/3197)) | SSH stdio first; optional tailnet HTTP in wrapper | Medium |
| Safe defaults | Promptless `standard`; telemetry on | Wrapper launcher forces `bounded` + policy + opt-outs | Easy |
| Untrusted-content tagging | Skill guidance only | Wrapper post-processing | Easy |

**Borrow from the single-OS servers rather than adopt them.**

- **computer-use-linux** is the credible second Linux engine. It has an explicit XFCE/EWMH backend using `wmctrl` and `xprop`. It "opens no TCP/UDP listener, makes no outbound Internet connections, and ships no telemetry", and it ships a native pi package ([computer-use-linux](https://github.com/agent-sh/computer-use-linux)). It is the right adapter if Cua's X11 bugs reproduce on xfwm4.
- **Windows-MCP** has the only first-class authenticated network MCP (TLS, OAuth, IP allowlists) and a real `Process` tool. It also defaults telemetry on and exposes PowerShell and Registry tools ([Windows-MCP](https://github.com/CursorTouch/Windows-MCP)).
- **Peekaboo**'s `capture live` keeps frames by diff and writes a contact sheet plus MP4. That is the right shape for model-facing clips ([Peekaboo capture](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/commands/capture.md)).
- **clawdcursor** contributes three safety patterns: it wraps screen text in `<untrusted-screen-content>`, gates actions in allow/confirm/block tiers, and fuses OCR into accessibility element IDs ([clawdcursor](https://github.com/AmrDab/clawdcursor)).
- **Open Computer Use** is the cautionary tale. It returns a full tree plus screenshot after every action, and its own issue tracker records about 300k tokens consumed in one session ([Open Computer Use](https://github.com/iFurySt/open-codex-computer-use)).

The vendor built-ins are not options for this toolkit. Claude Code's computer-use server is a macOS-only research preview for interactive sessions ([Claude Code docs](https://code.claude.com/docs/en/computer-use)). lcu depends on OpenAI's closed runtime from the ChatGPT app ([lcu](https://github.com/amontlabs/lcu)).

### Browser control rides CDP refs, and Firefox stays a pixel target

Browser tooling has converged on one pattern: an accessibility snapshot with short refs, then act by ref. Playwright, chrome-devtools-mcp, agent-browser and Anthropic's own browser toolset all use it ([agent-browser](https://github.com/vercel-labs/agent-browser); [chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)). Since **Chrome 136**, remote-debugging flags are ignored on the default profile ([Chrome blog](https://developer.chrome.com/blog/remote-debugging-port)). Driving a real logged-in browser now means one of two routes:

- **The Chrome 144+ `chrome://inspect/#remote-debugging` toggle**, which shows a consent dialog and publishes a dynamic port in `DevToolsActivePort` ([chrome-devtools-mcp docs](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/advanced-usage.md)).
- **An extension bridge.**

Cua's browser tools cover Chromium and Electron only. Firefox and Safari return `browser_route_unavailable` ([Cua browser guide](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/guides/browsers.mdx)). Playwright drives only its own patched Firefox, not the branded build ([Playwright docs](https://playwright.dev/docs/browsers)). Mozilla's BiDi-based firefox-devtools-mcp "isn't complete yet" ([Firefox docs](https://firefox-source-docs.mozilla.org/ai-agent-tools/firefox-devtools-mcp.html)).

On your VM, use Cua's browser tools with an isolated Chromium profile as the zero-dependency start, and treat the system Firefox as a desktop accessibility-and-pixel target. Playwright MCP and chrome-devtools-mcp both need Node, which the VM lacks. chrome-devtools-mcp also enables Google usage statistics by default. Keep inner-LLM frameworks out of the core: browser-use, Stagehand, Skyvern and Notte each run their own agent loop, and Skyvern and Notte carry AGPL or SSPL licenses. One caveat on integration: Cua measured its tab-to-window binding on OSWorld 2.0 and found a +0.0255 gain that was not significant ([Cua blog](https://cua.ai/blog/extension-free-browser-use)). Unified desktop and browser control is a convenience, not a proven accuracy win.

## Harness quirks force a thin owned layer over a pinned engine

The four target harnesses all speak MCP and Agent Skills, but they disagree on what reaches the model. These differences, more than the OS plumbing, decide the toolkit's output format.

| Harness | MCP image → model | MCP audio | Video | Key gotcha | Skills path |
|---|---|---|---|---|---|
| Claude Code | Yes, inline and scaled; full-res original saved to disk with path | Not documented; Claude reportedly takes no audio | No | Default 25k-token cap applies to image results | `~/.claude/skills` |
| Codex CLI | Yes, as `input_image`; `_meta["codex/imageDetail"]`; max 2,048 px | Mapped to `input_audio`; model support unclear | No | **Any `structuredContent` drops all images** | `~/.agents/skills` |
| opencode | Yes, as an attachment | **Silently dropped** | No | Image misattribution in parallel calls | `~/.agents`, `~/.claude`, `~/.config/opencode` |
| pi 1.0 | Yes; 2,000×2,000 resize | Placeholder text | No | Default `codemode` exposure hides tools | `~/.agents/skills` |
| Gemini CLI (→ Antigravity `agy`) | Yes, `inlineData` | **Yes** | **Yes**, resource blobs and `read_file` up to 20 MB | Replaced for individual users on 2026-06-18; agy's handling unverified | `~/.agents/skills` |
| Crush | First image only | Only when no image is present | No | One image per result | — |

Sources: [Claude Code MCP docs](https://code.claude.com/docs/en/mcp); [codex models.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs) and [codex#10334](https://github.com/openai/codex/issues/10334); [opencode tools.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/session/tools.ts) and [opencode#52977](https://github.com/anomalyco/opencode/issues/52977); [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md) and [pi-mcp content.js](https://cdn.jsdelivr.net/npm/@earendil-works/pi-mcp@1.0.4/dist/protocol/content.js); [gemini-cli mcp-tool.ts](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/tools/mcp-tool.ts) and [fileUtils.ts](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/utils/fileUtils.ts); [Google Developers Blog](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/); [crush tools.go](https://github.com/charmbracelet/crush/blob/main/internal/agent/tools/mcp/tools.go); [Claude audio feature request](https://claudeissues.com/issue/73566-feature-allow-claude-to-hear-and-process-audio).

**The Codex row alone justifies owning the output layer.** Cua returns its action results and window state in `structuredContent` next to the PNG. Codex's source turns the entire result into serialized `structuredContent` text whenever that field is non-null, dropping every image ([codex models.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs)). The issue has been open since February with no maintainer response ([codex#10334](https://github.com/openai/codex/issues/10334)). Claude Code had the mirror-image bug until May 2026 ([claude-code#54737 mirror](https://claudeissues.com/issue/54737-bug-mcp-tool-results-image-content-blocks-dropped-when-structuredcontent-is-also)).

The portable result shape follows from the matrix:

- **One short text block first.** It holds JSON with the artifact path, pixel dimensions, scale, coordinate frame and capture ID.
- **At most one image.**
- **No `structuredContent` or `outputSchema` on any image-returning tool.**
- **A long edge of about 2,000 px or less** by default, with per-model profiles up to 2,576 px.
- **`codex/imageDetail: "original"`** set on zoom crops.

pi needs `exposure: "direct"` for this server. Otherwise pi 1.0 hides MCP tools behind codemode scripts, which slows a tight screenshot-click loop ([pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)).

**Ship MCP and CLI as two front-ends to one core.** Each has evidence on its side.

- **For the CLI:** Zechner measured Playwright MCP's 21 tools at 13.7k tokens of context, against 225 tokens for a README-plus-CLI skill ([Zechner](https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/)). Playwright's own README now says coding agents "increasingly favor CLI–based workflows exposed as SKILLs" ([playwright-mcp](https://github.com/microsoft/playwright-mcp)).
- **For MCP:** the one controlled comparison found the CLI route used 2–3× less context but needed about 3× more tool calls and ran 2–3× slower at similar cost, because MCP returns state with each action ([Ranger](https://outpost.ranger.net/post/the-hidden-cost-of-fewer-tokens/)). Claude Code also defers MCP tool definitions by default through tool search ([Claude Code MCP docs](https://code.claude.com/docs/en/mcp)), which removes much of the schema-cost penalty.

The resolution is MCP for the observe-act loop, with a compact observation returned after each action, and a CLI that prints one line of JSON with file paths for shell-only harnesses and scripted batches. Every target harness can view a PNG from disk with a built-in tool, such as Codex's `view_image` or opencode's `read` ([codex view_image](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/view_image.rs); [opencode read.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/tool/read.ts)), so the CLI path needs no integration code.

**The MCP spec has no answer for video, and it pushes model calls out of the protocol.** The 2026-07-28 revision removed protocol-level sessions and made Tasks an extension. It deprecated Sampling and suggests teams "integrate directly with LLM provider APIs instead". The content types are still text, image, audio, resource and resource_link, with **no video type** ([MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)). File transfer is still only a proposal ([SEP-2631](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2631)). Codex's default tool timeout is 60 s ([Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)), and Cua's hand-rolled MCP layer sends no progress notifications. Clip and audio tools must therefore either finish within about 30–60 s or come as start/stop pairs with explicit handles.

The deprecation of Sampling has a useful corollary. When the toolkit wants a model's help, it should call an OpenAI-compatible endpoint itself, never ask the harness. Examples include a grounder that turns a description into a point, or an omni model that turns a clip into text.

### The architecture: one contract, one session daemon, many front-ends

The toolkit should be four layers, each with one job.

- **Engine:** pinned Cua Driver. On Linux and Windows the toolkit can hold a child `cua-driver mcp` or embed the runtime through Cua's UniFFI SDK, whose `call_tool()` reaches "the full generic tool surface" ([Cua SDK guide](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/guides/use-the-sdk.mdx)). On macOS it must connect to the `CuaDriver.app` socket so that TCC grants stay with Cua's signed identity.
- **Toolkit daemon:** lives inside the graphical session and owns everything Cua lacks:
  - the public tool contract and its coordinate frames;
  - a media broker for resizing, desktop zoom, clips, audio and OCR;
  - the policy launcher;
  - an artifact store that assigns every image, clip and recording an ID and a path;
  - an append-only event log.
- **Front-ends:** `toolkit mcp` (stdio), `toolkit <verb>` (CLI printing one-line JSON), and later an optional streamable-HTTP listener bound to the Tailscale interface with a bearer token.
- **Packaging:** one SKILL.md installed at `~/.agents/skills/computer-use`, which Codex, opencode, pi and Gemini read, symlinked into `~/.claude/skills` for Claude Code ([agentskills.io](https://agentskills.io); [Claude Code skills](https://code.claude.com/docs/en/skills)). It is wrapped by per-harness shims:
  - a Claude Code plugin with `bin/` on PATH and `.mcp.json` ([plugins reference](https://code.claude.com/docs/en/plugins-reference));
  - a Codex `config.toml` entry;
  - an opencode `mcp` entry;
  - a pi package with a native `pi.registerTool` extension ([pi extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md));
  - a Gemini/Antigravity extension.

**Remote operation should start with SSH, not a new network listener.** The harness on your Mac launches `ssh -T -o BatchMode=yes user@linux-vm 'toolkit mcp'`, which Tailscale authenticates. On the VM, the toolkit resolves the session environment and drives Cua locally. There is one subtlety: in CLI mode, file paths printed on the VM are useless to a harness on the Mac. The CLI therefore needs a `--remote` mode that runs locally, pulls each artifact back to a local temp file and prints the local path.

**Write the wrapper in Python, managed with uv.** The VM has Python and uv but no Node or Bun. Cua publishes a PyPI wheel. RapidOCR, numpy and Pillow cover cropping and OCR, and ffmpeg and PulseAudio/PipeWire are easy subprocesses. The heavy per-OS work stays in Cua's Rust. Keep the tool contract as a language-neutral JSON schema so a later Rust port stays mechanical. The one known cost comes on macOS: an interpreter as the TCC subject is fragile ([cua#870](https://github.com/trycua/cua/issues/870)), so macOS audio will need a small signed helper.

**Policy has to live in the toolkit, because MCP servers get no vendor safety net.** Anthropic states that its screenshot prompt-injection classifiers "are not available for custom tool definitions" ([Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)). The launcher should:

- Always start Cua in `bounded` mode with a generated capability manifest and a Rego or YAML policy.
- Set `DO_NOT_TRACK=1` and disable the update check.
- Wrap every screen-, accessibility- or OCR-derived string in an untrusted-content tag.
- Require an `intent` string on every mutating call, borrowing Gemini's per-action `intent` ([Gemini docs](https://ai.google.dev/gemini-api/docs/computer-use)).
- Apply per-app tiers modeled on Claude's (browsers view-only, terminals click-only, everything else full) ([Claude Code docs](https://code.claude.com/docs/en/computer-use)).
- Keep the shell tool off by default.
- Enforce a single-controller lock and a hard kill switch.

## Holo4 will not fit in 11 GiB, but its ideas and its small siblings will

**Holo4 is a near-frontier, open-weight computer-use *policy* model, not a narrow grounder.** It was released on September 28, 2026 in two sizes, both with 262,144-token context:

| Model | Architecture and base | License |
|---|---|---|
| **Holo4-27B** | Dense, built on Qwen3.8-27B | **CC BY-NC 4.0** ([HF](https://huggingface.co/Hcompany/Holo4-27B)) |
| **Holo4-35B-A3B** | MoE with 3B active parameters, built on Qwen3.6-35B-A3B | **Apache 2.0** ([HF](https://huggingface.co/Hcompany/Holo4-35B-A3B)) |

H reports **85.2% on OSWorld at $0.08 per task** and 61.7% score (41.5% success) on OSWorld 2.0 for the 27B, all in H's own harness ([H newsroom](https://hcompany.ai/newsroom/holo4)). The newsroom does not report grounding benchmarks for Holo4.

**Holo4 does not fit the VM.** H's docs list the same-class Holo3.1-35B-A3B at **21.3 GB for Q4_K_M weights alone**, and they recommend Macs with at least 36 GB of unified memory for that size ([H local inference](https://hub.hcompany.ai/models-api/local-inference)). The VM shares 11 GiB of RAM between XFCE, the capture pipeline and the iGPU. Raising the VM's allocation to the mid-20s of GiB would only make sense if the host has that memory to spare, and it would still mean slow image prefill. H measured only 3.6 model requests per minute for a Q4 model under llama.cpp on an M4 Pro MacBook. The hosted route is cheap:

- `holo4-35b-a3b` costs $0.30 input and $2.00 output per million tokens.
- `holo3-1-35b-a3b` is **free at 10 requests per minute**.
- Zero data retention is the default ([H Models API](https://hub.hcompany.ai/models-api/introduction)).

At roughly 2.5k input tokens per 1080p screenshot, a hosted grounding call works out to about $0.0008 (my arithmetic).

**H's harness runs on your VM's platform, but only as a reference, not a foundation.** HoloDesktop CLI is an Apache-2.0 client around a **closed-source `hai-agent-runtime`** that is downloaded on first run ([holo-desktop-cli](https://github.com/hcompai/holo-desktop-cli)). Its docs list Linux support as x86_64 under an X11 session, with Wayland unsupported ([HoloDesktop docs](https://hub.hcompany.ai/holo-desktop-cli.md)), which matches your VM. The GitHub README is less explicit, and testing claims cover Ubuntu 22.04, not Debian 13. It drives the visible screen and shares your mouse. Its MCP surface is a single `holo_desktop(task)` tool that "blocks until completion" ([mcp.py](https://github.com/hcompai/holo-desktop-cli/blob/161449a/src/holo_desktop/cli/mcp.py#L63)). That makes it a sub-agent, not a tool layer. Its value here is as a Phase 3 baseline: can a hosted Holo complete the same tasks end-to-end, and at what cost? Run it against hosted inference, accepting that screenshots leave the VM.

**A small grounder on the 780M is feasible.** At the 2B–4B tier, single-pass ScreenSpot-Pro scores have converged:

| Grounder | Single pass | With zoom or agentic pass | License |
|---|---|---|---|
| UI-Venus-1.5-2B | 57.7 | 64.6 | Apache 2.0 badge, but labeled research-only ([UI-Venus](https://github.com/inclusionAI/UI-Venus/blob/UI-Venus-1.5/README.md)) |
| MAI-UI-2B | 57.4 | — | Code under Apache 2.0 ([MAI-UI](https://github.com/Tongyi-MAI/MAI-UI)) |
| Holo2-4B | 57.2 | 68.6 | Apache 2.0 ([Holo2-4B](https://huggingface.co/Hcompany/Holo2-4B)) |
| UI-TARS-1.5-7B | 39.0 | — | — ([Holo2-4B card](https://huggingface.co/Hcompany/Holo2-4B)) |

Holo3.1-0.8B and 4B are Apache 2.0, with community GGUFs ([HF search](https://huggingface.co/api/models?search=Holo-3.1&limit=50)), but they have no text-verified grounding scores.

- **Backend.** Use llama.cpp's Vulkan backend on Mesa RADV, which supports the 780M's gfx1103 natively ([k8s.it](https://www.k8s.it/posts/running-a-local-llm-on-amd-radeon-780m-gfx1103-rocm-and-the-gpu-that-wasnt-supposed-to-work/)). Despite your `/dev/kfd`, avoid ROCm: llama.cpp's HIP backend currently crashes on gfx1103 because rocBLAS lacks it ([llama.cpp#20839](https://github.com/ggml-org/llama.cpp/issues/20839)).
- **Memory.** A 2B model at Q8 or a 4B at Q4 fits in about 3 GB plus the vision projector.
- **Latency.** No VLM measurement on a 780M exists. The research estimate is **2–8 s per grounding call for a 2B model** at 1080p, roughly halved at 1280×720.

Frontier hosts already ground at 85–88%, so the grounder is optional. It is most useful in three situations: with cheaper or open host models, on dense professional UIs, and for keeping high-resolution screenshots out of the host's context entirely.

**H's design choices are worth borrowing even without its model.**

- **A stateless locate call.** H's localization call sends one image with a description at temperature 0, with thinking off and a JSON schema. It returns integers in **0–1000 normalized to the exact bytes sent**, with the warning that resizing after the request causes misses ([H element localization](https://hub.hcompany.ai/models-api/element-localization)). That is the right contract for a `locate` tool.
- **Agentic zoom refinement.** Re-asking on a crop gave "10–20% relative gains across all Holo2 model sizes" ([Holo2-235B preview](https://hcompany.ai/holo2-235b-a22b-preview)).
- **Verify in code.** Surfer-H split the work into policy, localizer and validator ([Holo1 paper](https://arxiv.org/html/2506.02865v2)). HoloDesktop's architecture says "the agent observes and acts; it does not verify" and recommends checking results "with code, not another model call" ([HoloDesktop architecture](https://hub.hcompany.ai/holo-desktop-cli/architecture)).
- **Skill says when, MCP says how.** HoloDesktop's skill guidance draws this split explicitly. Task strings must carry the app, account and **success condition**, because the tool cannot see the host conversation ([HoloDesktop skill docs](https://hub.hcompany.ai/holo-desktop-cli/integrations/use-as-skill)).
- **Operational ideas, all in H's docs:** a fast mode (one screenshot, no thinking, smaller images), a double-Esc kill switch with step and time budgets, standing instructions in a dotfile directory snapshotted per run, and a local event log.
- **Memory and a desktop shell.** The Holo4 harness itself was "rebuilt" around persistent memory and a shell on the desktop machine ([H newsroom](https://hcompany.ai/newsroom/holo4)). That supports offering an opt-in shell tool on the target.

## The plan: validate on the VM, wrap, then add the missing senses

**Build on Cua; don't fork it or start fresh.**

| Option | Verdict | Why |
|---|---|---|
| **Build on Cua Driver, pinned, behind an owned wrapper** | **Adopt** | Covers every OS and the native accessibility APIs today; documented MCP/SDK boundary; MIT; new modalities fit outside it |
| Fork Cua | Reject | 368k lines, 113 releases in five months, nine breaking; a fork diverges within weeks |
| Fresh build | Reject (except as a hedge) | X11-only could be done in weeks, but Windows UIA, macOS TCC/SCK, CDP binding and the Wayland matrix are months of verified work |
| Assemble per-OS servers | Reject as primary | Three incompatible contracts; keep computer-use-linux as the Linux fallback engine |

**Phase 0 is a one-to-two-day validation on `user@linux-vm`.** It has four parts:

- **Confirm session ownership.** `loginctl` should show that the XFCE session on `:0` belongs to `admin`. If lightdm auto-logs in another user, AT-SPI and X access will fail over SSH.
- **Install prerequisites.** ffmpeg is missing, and Cua's video path shells out to it. Cua's quickstart also asks for `libxi6` and `at-spi2-core` ([Cua quickstart](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/quickstart.mdx)).
- **Probe audio and GPU.** Check whether audio runs on PipeWire or PulseAudio, and whether RADV sees the 780M.
- **Install Cua and register it.** Install exactly 0.34.0, turn off telemetry and the update check, and register it over SSH in two harnesses on the Mac.

```bash
# on the VM
loginctl list-sessions && loginctl show-session <id> -p Name -p Display -p Type
sudo apt install ffmpeg libxi6 at-spi2-core vulkan-tools pulseaudio-utils
pactl info | grep 'Server Name'                 # PipeWire or PulseAudio?
vulkaninfo --summary | grep -i deviceName       # RADV sees the 780M?
# install cua-driver 0.34.0 (install.sh verifies SHA256SUMS), then:
cua-driver telemetry disable && cua-driver config set update_check_enabled false
# on the Mac (absolute path: non-interactive SSH may not have ~/.local/bin on PATH)
claude mcp add cua-vm -- ssh -T -o BatchMode=yes user@linux-vm 'DISPLAY=:0 /abs/path/cua-driver mcp'
codex  mcp add cua-vm -- ssh -T -o BatchMode=yes user@linux-vm 'DISPLAY=:0 /abs/path/cua-driver mcp'
```

The smoke run then works through Cua's tools in order:

1. **`list_apps`** — confirm it reports non-GUI processes.
2. **`get_window_state` on Mousepad and Thunar** — check tree, PNG and `frame_scale`.
3. **`type_text` into Mousepad** by element token and by pixel, then read the text back. This tests #3774.
4. **Pixel clicks near the title bar.** This tests the ~47 px offset in #3237.
5. **`zoom`.**
6. **`get_desktop_state`** with a `max_image_dimension` cap.
7. **`start_recording` with video, then `stop_recording`.**
8. **`browser_prepare`** with an isolated Chromium profile, then `get_browser_state`.
9. **A `run_actions` batch.**

Run the daemon with `--no-overlay` to sidestep the X11 overlay bugs ([daemon CLI](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/docs/content/docs/cua-driver/reference/cli/daemon.mdx)). If `XAUTHORITY` auto-discovery fails, set it explicitly. Cua reads the X server's `-auth` argument ([xauth.rs](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/rust/crates/platform-linux/src/xauth.rs)), and the lightdm path conventions on Debian 13 are unverified.

Two cheap side experiments belong in the same phase:

- **A media probe.** Build a 50-line MCP test server that returns, in turn, image plus text, image plus `structuredContent`, audio, and a `video/mp4` resource blob. Run it in Claude Code, Codex, opencode, pi and `agy`, and replace the source-read matrix above with measured behavior.
- **A grounder benchmark.** Build llama.cpp with Vulkan, run a 2B grounder GGUF on real XFCE screenshots, and time it against the free hosted Holo3.1 tier.

The exit decision is binary. If typing and clicking are reliable on xfwm4, Cua is the Linux engine. If not, the wrapper's first adapter targets computer-use-linux, and the bugs go upstream.

**The public tool surface should be small, opinionated and engine-neutral.** About 20 tools, each one action wide in the style of Anthropic's toolset, map onto Cua where Cua is strong and onto the wrapper where it is not.

| Tool | Purpose | Backed by | Phase |
|---|---|---|---|
| `doctor` / `capabilities` | Engine version, DISPLAY/XAUTHORITY/D-Bus, AT-SPI, ffmpeg, audio backend, permissions, harness media profile | Cua `health_report` + wrapper probes | 1 |
| `observe` | Text-first state: bounded accessibility tree with tokens and diffs, window list, optional screenshot; returns `capture_id` + frame | Cua `get_window_state` / `get_desktop_state` | 1 |
| `screenshot` | Desktop, monitor, window or region at the model-profile budget; saved file + one inline image | Cua capture + wrapper resize | 1 |
| `zoom` | Native-resolution crop of any earlier capture, desktop or window, in the same frame | Wrapper crop of saved original; Cua `zoom` for windows | 1 |
| `click`, `type_text`, `key`, `scroll`, `drag`, `move` | Target by element token, by `{x,y,frame,capture_id}`, or by zoom coordinates; mandatory `intent` | Cua pointer/keyboard tools | 1 |
| `batch` | Ordered actions, halt on first failure, one fresh observation at the end | Cua `run_actions` (≤32 steps) | 1 |
| `wait_for` | Settle until frame or accessibility state is stable or an expectation holds, bounded | Cua `verify_state` + frame diff | 1 |
| `windows`, `apps`, `processes`, `clipboard` | List/focus/move/close windows; launch/kill apps; ps-style list; clipboard | Cua + psutil | 1 |
| `browser_snapshot`, `browser_act`, `browser_navigate` | Chromium tabs by CDP ref, isolated profile by default | Cua `browser_*` | 1 |
| `ocr` | Text and boxes for a region, tagged untrusted | RapidOCR / PP-OCR ONNX | 2 |
| `record_clip` / `clip_start` + `clip_stop` | ≤30 s clip of desktop, window or region → MP4 + contact-sheet PNG + keyframes | ffmpeg `x11grab`; later `ddagrab`/SCK | 2 |
| `audio_capture` | System monitor or mic, fixed duration or start/stop → WAV/FLAC + optional transcript | PipeWire/Pulse; later WASAPI/SCK | 2 |
| `locate` (optional) | Description → point, with optional zoom refinement | llama-server (Vulkan) or H API | 3 |
| `describe_media` (optional) | Clip or audio → text via a configured omni model | OpenAI-compatible endpoint | 3 |
| `run` (off by default) | Shell on the target machine | Wrapper | 1, disabled |

| Phase | Scope | Hand-off artifacts | Exit criterion |
|---|---|---|---|
| 0 · Validate (1–2 days) | Prerequisites, Cua smoke over SSH, media probe, grounder timing | Smoke script + log, measured harness media matrix, latency numbers, go/no-go on the Linux engine | Reliable type/click on Mousepad, Thunar and Chromium, or a recorded switch to computer-use-linux |
| 1 · Contract + Linux wrapper (1–2 weeks) | JSON tool contract, output normalization, policy launcher, desktop zoom, processes, doctor, SKILL.md, five harness shims, session unit or XFCE autostart | `contract/tools.json`, snapshot of Cua `list-tools` for drift tests, packages | One scripted task (e.g., edit and save a file in Mousepad, verify in code) passes from at least three harnesses |
| 2 · Media (≈2 weeks) | Clips, audio, OCR, contact sheets, transcripts, per-harness media profiles | Media tools + fixtures | Contact sheets visible in every harness; raw audio/video reach the model in `agy` or Gemini CLI |
| 3 · Grounding + reliability (≈2 weeks) | `locate` backends, zoom refinement, verify-after-act, settle waits, 20–30-task eval with a Holo baseline | Eval suite + baseline table | Measured accuracy and cost deltas; keep or drop `locate` on evidence |
| 4 · Cross-platform + transport (ongoing) | Windows (logon-task daemon, WASAPI, `ddagrab`), macOS (CuaDriver.app socket, signed audio helper), Wayland (Cua opt-in backends), tailnet HTTP, upstream PRs (#3047, #3957, stale pi preset) | Per-OS doctor + smoke results | Contract tests pass on each OS |

The phase durations are rough sizing, not commitments.

**Hand-offs between harnesses work if the contract, not any harness's memory, is the source of truth.** Each phase should end with three artifacts:

- the updated `contract/tools.json`;
- an executable acceptance script that any harness can run over SSH;
- an entry in `.project/tracker.md` recording decisions, measured results and the next action.

Run each phase's acceptance test from at least two different harnesses. That turns the multi-harness handoff into continuous compatibility testing rather than a coordination risk. Pin Cua by exact version and diff its `list-tools` output before every bump. Cua itself calls its text output "diagnostic, not a stable parsing API" ([tool output format](https://github.com/trycua/cua/blob/b0a6348133a34b3d158eae38d06a606215eec6df/libs/cua-driver/docs/tool-output-format.md)).

## Conclusion

The hard part of harness-agnostic computer use has moved. Two years ago it was grounding and per-OS input. In October 2026 frontier models ground at 85–88%, and one MIT engine already handles the per-OS mechanics. What remains is a **delivery problem**: getting the right pixels, at the right budget, in a shape each harness actually forwards to its model. The value you can own is therefore in a coordinate-frame contract, a media broker and a safety policy, not in drivers. That layer outlives whichever engine sits under it. The same view explains why audio and video feel unfinished across the ecosystem. The bottleneck is not capture, which is easy on X11. It is that only one harness family forwards those media at all. "Perception sidecars" should be first-class tools: a grounder that returns a point, an omni model that returns a description. The toolkit calls these models directly rather than through the harness, which matches where the MCP spec now points.

The VM's X11 session makes Phase 0 easy, but it is a stepping stone. GNOME and KDE have both left X11, so any Linux machine you care about after this one will probably be Wayland. That is where Cua is weakest and portal consent is unavoidable, which is the strongest argument for keeping the engine swappable behind your own contract from day one.
