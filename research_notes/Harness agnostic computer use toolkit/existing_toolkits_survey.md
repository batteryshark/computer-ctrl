# Existing open-source computer-use toolkits, MCP servers and CLIs (survey as of 2026-10-07)

Method note: I took GitHub star counts, push dates, licenses and archive status from the GitHub REST/search API on 2026-10-07 between 21:05 and 21:15 UTC. Release tags came from the GitHub releases API, and package versions from PyPI and npm on the same day. Feature claims come from each project's README or docs, fetched the same day. A claim taken only from a third-party roundup is labeled. "Unverified" means I could not confirm it from a primary source.

## Q1. Feature, platform, license and maturity matrix of the serious candidates

### Takeaway
Only one project covers Windows, macOS, Linux X11 and Linux Wayland in one MIT codebase, and also exposes MCP, a CLI and Agent Skills while being actively released: **Cua Driver**, from trycua/cua. It has a11y trees, a `zoom` tool, file-path screenshot output, trajectory video recording, an SSH-remote recipe, and Windows/macOS/Linux/Wayland coverage. The rest of the field breaks into three groups:
- Strong single-OS servers: Windows-MCP, Peekaboo on macOS, and computer-use-linux on Wayland.
- Younger cross-platform challengers: Open Computer Use, clawdcursor and nuphus-mcp.
- Agent frameworks or sandboxes, not reusable tool layers: UI-TARS, UFO, Agent-S, OmniParser, Bytebot, E2B, screenenv, and the Anthropic/OpenAI reference apps.

### Cited Findings

#### A. Summary matrix (stars and dates from the GitHub API, 2026-10-07)

| Project | Platforms | Interface | Lang | License | Stars | Latest release / last push | A11y tree | Zoom/crop | OCR | Rec/Audio | Local vs sandbox |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Cua Driver** (trycua/cua, libs/cua-driver) | Win 10/11, macOS 14+, Linux X11, Linux Wayland (with limits) | MCP stdio, CLI (`cua-driver call`), daemon, Py/TS SDK, skills | Rust | MIT (perception ext. includes AGPL part) | 28,699 (whole monorepo) | cua-driver 0.34.0, 2026-10-05; push 2026-10-07 | Yes (AX/UIA/AT-SPI) | Yes (`zoom`) | Optional extension | Video trajectory recording (mp4); no audio in driver | Local host, or inside Lume VM / Cua sandboxes |
| **Windows-MCP** (CursorTouch) | Windows 7–11 | MCP stdio/SSE/streamable HTTP | Python | MIT | 7,963 | v0.8.7, 2026-09-30 | Yes (UIA) | Region crop + scale | No | No | Local; network HTTP with auth |
| **MacOS-MCP** (CursorTouch) | macOS 12+ | MCP stdio/SSE/streamable HTTP | Python | MIT | 196 | v0.4.6, 2026-09-08 | Yes (AX) | n/v | n/v | No | Local; network HTTP |
| **Peekaboo** (openclaw, formerly steipete) | macOS 15+ | CLI, MCP stdio, menu-bar app, agent | Swift | MIT | 5,259 | v4.9.0, 2026-10-07 | Yes (AX, element IDs) | n/v | OCR text as evidence | `capture live/video` frames, contact sheet, MP4 | Local only |
| **computer-use-linux** (agent-sh) | Linux Wayland-first (GNOME, KDE, Hyprland, niri, i3, COSMIC) + X11 | MCP stdio, CLI, skill | Rust | MIT | 662 | v0.7.12, 2026-10-07 | Yes (AT-SPI) | Scaling/crop options | No | No | Local only (no listener) |
| **Open Computer Use** (iFurySt/open-codex-computer-use) | macOS 14+, Linux, Windows | MCP stdio, CLI (`call`/`js`/`repl`), skill, installers | Swift (+others) | MIT | 2,349 | v0.3.6, 2026-09-29 | Yes (a11y-based) | n/v | n/v | No | Local |
| **clawdcursor** (AmrDab) | Win 10/11, macOS 12+, Linux X11 + Wayland | MCP stdio + localhost HTTP, CLI, Claude Code plugin/skill | TS | MIT | 403 | v1.5.14, 2026-10-07 | Yes (fused with OCR) | n/v | Yes | No | Local |
| **agent-desktop** (lahfir) | macOS only shipped (Win/Linux "Planned") | CLI, C-ABI FFI, skills (no MCP described) | Rust | Apache-2.0 | 1,773 | v0.9.4, 2026-09-23 | Yes (refs) | No | No | Trace HTML | Local |
| **Terminator** (mediar-ai) | Windows only now | MCP (`terminator-mcp-agent`), CLI, TS/Py/Rust SDK | Rust | MIT | 1,650 | v0.24.32, 2026-04-05; push 2026-06-02 | Yes (UIA) | n/v | n/v | Workflow recorder | Local |
| **nuphus-mcp** (mrpulor-gh) | Windows full; macOS/Linux partial | MCP stdio | Rust | MIT | 322 | v0.3.1, 2026-09-28 | Yes (UIA/AX) | No | Yes (PaddleOCR + YOLO) | No | Local |
| **Interceptor** (Hacker-Valley-Media) | macOS native; Win/Linux browser only | CLI, MCP, local daemon, browser ext. | TS + Swift | Elastic License 2.0 | 516 | v1.0.24, 2026-10-02 | Yes | n/v | Yes | Screen streaming + system/mic audio (macOS) | Local |
| **lcu** (amontlabs) | Linux X11 (Ubuntu 24.04 glibc), macOS Apple Silicon; Win "candidate" | CLI + harness plugins (Pi, Codex, Claude Code) | Python | MIT (wraps OpenAI app runtime) | 723 | v0.9.7, 2026-10-07 | via Codex runtime | n/v | n/v | n/v | Local |
| **computer-use-mcp** (domdomegg) | macOS/Win/Linux (via nut.js) | MCP stdio, single `computer` tool | TS | MIT | 382 | v1.8.0, 2026-04-13 | No | No | No | No | Local |
| **computer-control-mcp** (AB498) | Win/mac/Linux (PyAutoGUI) | MCP | Python | MIT | 169 | PyPI 0.3.13, 2026-07-25 | No | n/v | Yes (RapidOCR) | No | Local |
| **GhostDesk** (YV17labs) | Linux (Docker Sway), macOS, Windows | MCP | Rust | FSL-1.1-ALv2 | 152 | push 2026-09-23 | n/v | n/v | n/v | n/v | Linux = container |
| **UI-TARS-desktop / Agent TARS** (bytedance) | Win/macOS + browser | Desktop app, CLI/Web UI, SDK/operators | TS | Apache-2.0 | 39,207 | v0.3.0, 2025-11-04; push 2026-10-05 | Vision-model based | n/a | n/a | n/a | Local + remote operators |
| **UFO³ / UFO²** (microsoft) | Windows (UFO²); Galaxy: Windows, Linux, Android | Python framework, WebSocket AIP client/server, MCP servers | Python | MIT | 9,947 | v3.0.10, 2026-09-22 | Yes (UIA + vision hybrid) | n/a | n/a | n/a | Local devices |
| **Agent-S (S3)** (simular-ai) | Linux/macOS/Windows | CLI + Python SDK (no MCP) | Python | Apache-2.0 | 12,550 | v0.3.2, 2025-12-16 | No (pyautogui + grounding model) | n/a | n/a | n/a | Local or VM |
| **OmniParser / OmniTool** (microsoft) | Model; OmniTool drives a Windows 11 VM | Library/model | Python | CC-BY-4.0 repo; mixed model licenses | 25,493 | news 2026/7; push 2026-07-20 | Vision parse | n/a | Yes (part of parse) | n/a | VM |
| **Bytebot** | Ubuntu 22.04 XFCE container | REST + web UI | TS | Apache-2.0 | 11,076 | **Archived 2026-03-07** | No | n/a | n/a | n/a | Container |
| **screenenv** (huggingface) | Ubuntu 22.04 XFCE in Docker | Python + MCP (streamable HTTP) | Python | MIT | 459 | PyPI 0.1.2, 2025-07-25; push 2026-09-24 | n/v | n/v | n/v | Video recording | Container |
| **E2B Desktop** | Linux Xfce cloud sandbox | Py/JS SDK | Python/TS | Apache-2.0 (repo); PyPI says MIT | 1,514 | e2b-desktop 2.6.1, 2026-10-05 | No | n/v | No | Streaming | Cloud sandbox |
| **Anthropic computer-use-demo** | Linux X11 + VNC in Docker | Streamlit reference app | Python | MIT | 17,815 (claude-quickstarts) | push 2026-10-07 | No | n/v | No | No | Container |
| **openai-cua-sample-app** | Local Playwright browser; local desktop via PyAutoGUI | Sample app (Responses API) | TS/Python | MIT | 1,886 | push 2026-09-04 | No | n/a | n/a | n/a | Local, no sandbox |

(n/v = not verified from primary source; n/a = not applicable or not a tool layer.)

Sources for the matrix rows: [GitHub search API batch](https://api.github.com/search/repositories?q=repo:trycua/cua) (queried 2026-10-07); [GitHub releases API](https://api.github.com/repos/CursorTouch/Windows-MCP/releases) (queried 2026-10-07); [PyPI cua-driver](https://pypi.org/project/cua-driver/); [npm @trycua/cua-driver](https://www.npmjs.com/package/@trycua/cua-driver). Per-project feature sources are cited below.

#### B. Per-candidate details

**trycua/cua → Cua Driver (best foundation candidate)**
- The monorepo has been reorganized. Current components are Cua Driver, the `cua` SDK/CLI (Rust core), cua-sandbox, cua-spacesd (an in-sandbox gRPC daemon on port 3211), Cua Spaces, cua-bench, Lume, Lumier and CUA-S1 models. The README lists cuabot, cua-computer, cua-computer-server, cua-agent and cua-som as **deprecated**. — [trycua/cua README](https://github.com/trycua/cua)
- Repo: ★28,699, MIT, Rust as primary language, created 2025-01-31, pushed 2026-10-07. — [GitHub API](https://github.com/trycua/cua)
- cua-driver 0.34.0 was released 2026-10-05 on PyPI (MIT) and npm (`@trycua/cua-driver`). There were six `cua-driver-rs-v0.33.x/0.34.0` GitHub tags between 2026-10-03 and 2026-10-05. — [PyPI](https://pypi.org/project/cua-driver/), [npm](https://www.npmjs.com/package/@trycua/cua-driver), [GitHub releases](https://github.com/trycua/cua/releases)
- Platform APIs and support levels:
  - macOS 14+ (AX, ScreenCaptureKit, Quartz): Supported.
  - Windows 10/11/Server (UI Automation, Win32 input): Supported.
  - Linux X11 (AT-SPI, X11/EWMH, XTest): "Supported with toolkit limits".
  - Linux Wayland: "Supported with compositor limits".
  
  — [Cua Driver overview](https://cua.ai/docs/cua-driver)
- Wayland detail:
  - Native Wayland is opt-in with `CUA_DRIVER_RS_ENABLE_WAYLAND=1`.
  - Sway is supported with limits. GNOME/Mutter is supported with limits, needs a bundled "WinRects Shell helper", and portal video recording there is incomplete.
  - KDE/KWin is "Experimental" (its helper is read-only). Hyprland/Omarchy is experimental.
  - "an ordinary client cannot send raw input to an unfocused, occluded window. AT-SPI actions still work in the background."
  
  — [Cua Driver platform support](https://cua.ai/docs/cua-driver/concepts/platform-support.md)
- Integration surfaces:
  - `cua-driver mcp` (MCP stdio).
  - `cua-driver call <tool>` for shell-only agents, running against the `cua-driver serve` daemon.
  - Python/TS SDK via UniFFI.
  - A shared daemon via `cua-driver serve --socket <path>` plus `cua-driver mcp --socket <path>`.
  
  — [Cua Driver overview](https://cua.ai/docs/cua-driver); [libs/cua-driver README](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/README.md)
- Tool catalog: about 65 MCP tools in 17 groups, covering:
  - apps/windows (8), window state (4, e.g. `get_window_state` = a11y tree + screenshot), screen (4, incl. `zoom`)
  - click, double/right-click, pointer (7: drag, scroll, move, press/release), typing, keys/shortcuts (2), values/clipboard (3), batch
  - page tools (4) and browser input over CDP (6)
  - sessions (6), agent cursor (4), recording (5), maintenance (6)
  
  — [Cua Driver reference](https://cua.ai/docs/cua-driver/reference.md)
- `zoom` returns "a cropped JPEG of a window region (x1,y1)–(x2,y2)… with 20% padding". Output is at most 500 px wide on macOS and Linux. On Windows it zooms "at full (native) resolution". `from_zoom=true` on click/type_text maps coordinates back to the full window. — [Cua Driver screen tools](https://cua.ai/docs/cua-driver/reference/mcp-tools/screen.md)
- Screenshots come back as base64 PNG by default. `screenshot_out_file` writes "the PNG to this file path… instead of embedding base64", and the structured output then carries `screenshot_file_path`. The default screenshot is capped at about 1.15 MP (long edge 1568), and coordinates are auto-mapped back to full size. — [Cua Driver window-state tools](https://cua.ai/docs/cua-driver/reference/mcp-tools/window-state.md)
- Accessibility tree:
  - Rendered as compact Markdown with `[N]` rows addressed as `<snapshot_id>:N` element tokens.
  - Bounded to 250 nodes by default.
  - Stale snapshots invalidate their tokens.
  - On Wayland, when capture can't prove surface identity, it returns the tree without a screenshot (`surface_identity_unproven`).
  
  — [window-state tools](https://cua.ai/docs/cua-driver/reference/mcp-tools/window-state.md)
- OCR and set-of-marks-style parsing come only from an optional `cua-perception` extension. The README warns: "The extension is not MIT licensed. Its OmniParser icon detector is AGPL-3.0-only." The monorepo README separately mentions "Apache-2.0 PP-OCR model artifacts". — [libs/cua-driver README](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/README.md); [trycua/cua README](https://github.com/trycua/cua)
- Recording: `start_recording` with `record_video: true` saves every action with before/after screenshots plus `recording.mp4`. `cua-driver recording render` (needs ffmpeg) produces a zoom-on-click video. An encrypted, metadata-only "Computer History" is in nightly preview. — [Cua Driver trajectories guide](https://cua.ai/docs/cua-driver/guides/trajectories.md)
- Permission modes: `standard` is the promptless default and "allows input to every app". `bounded` uses a reviewed capability manifest. `unrestricted` requires `--dangerously-bypass-approvals`. YAML or Rego policies can restrict tools further. — [libs/cua-driver README](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/README.md); [connect-your-agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md)
- Audio: the driver does not mention audio. cua-spacesd (the sandbox daemon) advertises "low-latency video and audio streaming" for Spaces. — [trycua/cua README](https://github.com/trycua/cua)
- Third-party view: a Sept 23 2026 roundup calls Cua Driver "the biggest open-source project in computer use" and best for cross-platform agents and fleets. It adds that the scope is "broader than needed" for single-app clicking. — [Pinggy roundup (third-party)](https://pinggy.io/blog/best_computer_use_mcp_servers/)

**CursorTouch Windows-MCP (+ MacOS-MCP, Android-MCP)**
- Windows-MCP: ★7,963, MIT, Python, v0.8.7 released 2026-09-30. — [GitHub API/releases](https://github.com/CursorTouch/Windows-MCP)
- Tools:
  - Input and timing: Click, Type, Scroll, Move/drag, Shortcut, Wait/WaitFor, MultiSelect/MultiEdit.
  - Observation: Screenshot, Snapshot (UI state with interactive element IDs, optional vision/DOM extraction), DisplayInventory.
  - Apps and system: App (launch/resize/move/switch windows), Process (list/kill), PowerShell, FileSystem, Clipboard, Registry, Notification.
  - Other: Scrape, ControlStatus.
  
  — [Windows-MCP README](https://github.com/CursorTouch/Windows-MCP)
- Transports are stdio, SSE and streamable HTTP. Network modes support auth keys, IP allowlists, TLS and OAuth 2.0 + PKCE. `windows-mcp install` creates a per-user Scheduled Task. — [Windows-MCP README](https://github.com/CursorTouch/Windows-MCP)
- Screenshots return an image. `WINDOWS_MCP_SCREENSHOT_SCALE` ranges 0.1–1.0, `region=[l,t,r,b]` crops, and backends are dxcam, mss or pillow. The server relies on the a11y tree and "doesn't rely on any traditional computer vision techniques". It has no OCR. It needs Windows 7–11, Python 3.13+, and English as the default Windows language. — [Windows-MCP README](https://github.com/CursorTouch/Windows-MCP)
- MacOS-MCP: ★196, v0.4.6 released 2026-09-08, macOS 12+, Python 3.11+, stdio/SSE/streamable-HTTP. — [GitHub API](https://github.com/CursorTouch/MacOS-MCP); [MacOS-MCP README](https://github.com/CursorTouch/MacOS-MCP)
- The roundup counts 12 MacOS-MCP tools, including Snapshot, Shell and Scrape, and calls it the pick for driving a Mac remotely because of its transport. — [Pinggy (third-party)](https://pinggy.io/blog/best_computer_use_mcp_servers/)
- The CursorTouch org has Windows-MCP, MacOS-MCP and Android-MCP (★885). It has **no Linux sibling**. — [GitHub org API](https://api.github.com/orgs/CursorTouch/repos)

**openclaw/Peekaboo (macOS)**
- The repo moved from steipete to the openclaw org. ★5,259, MIT, Swift, v4.9.0 released 2026-10-07 (v4.8.0 on 10-04, v4.7.0 on 10-03). npm `@steipete/peekaboo` 4.9.0. — [GitHub API](https://github.com/openclaw/Peekaboo); [npm](https://www.npmjs.com/package/@steipete/peekaboo)
- Requires macOS 15+. Ships as a CLI (`see`, `click`, `type`, `press`, `scroll`, `drag`, `set-value`, `select-text`, `app`, `window`, `menu`, `menubar`, `dock`, `dialog`, `space`, `capture`, `agent`, `browser`), a menu-bar app and an MCP server. `see` yields "a structured UI map with opaque element IDs". — [Peekaboo README](https://github.com/openclaw/Peekaboo)
- The MCP server is stdio only. HTTP/SSE flags are "recognized… but server transports are not implemented yet". An optional `--bridge-socket` attaches to a Bridge host. "OCR-only text is semantic evidence, not an element-action target." — [Peekaboo docs/MCP.md](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/MCP.md)
- `capture live` takes adaptive PNG bursts of screens, windows or regions, with diff-based frame keeping, a contact sheet and an optional MP4. `capture video` samples frames from an existing video. The MCP `capture` tool exposes both. — [Peekaboo docs/commands/capture.md](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/commands/capture.md)
- Community ports: PeekabooWin (Windows, JS + PowerShell, ★38) and PeekabooX (Linux, Rust + Python). — [Peekaboo README](https://raw.githubusercontent.com/openclaw/Peekaboo/main/README.md); [GitHub search](https://github.com/FelixKruger/PeekabooWin)

**agent-sh/computer-use-linux (Linux, Wayland-first)**
- ★662, MIT, Rust, created 2026-05-13, v0.7.12 released 2026-10-07. — [GitHub API/releases](https://github.com/agent-sh/computer-use-linux)
- Supports GNOME, KDE/KWin, Hyprland, niri, i3 and COSMIC. It describes itself as "Wayland-first, X11 best-effort". Sway/wlroots has "no dedicated backend yet". It was validated on Ubuntu 25.10 / GNOME Shell 50.1. — [README](https://github.com/agent-sh/computer-use-linux)
- Input and capture:
  - Pointer input uses the `org.freedesktop.portal.RemoteDesktop` portal, falling back to ydotool/ydotoold.
  - Text goes through the KDE clipboard, wtype, or portal keysyms. X11 uses xdotool/XTEST.
  - Screenshot chain: GNOME Shell DBus → portal Screenshot → X11 GetImage → gnome-screenshot.
  - AT-SPI selectors (role/name/text/states).
  
  — [README](https://github.com/agent-sh/computer-use-linux)
- Interfaces:
  - MCP is stdio only, and the binary "opens no TCP/UDP listener".
  - The CLI has `doctor`, `state`, `screenshot` and `windows`.
  - A `computer-use-linux` skill ships with it. It names Claude Code, Claude Desktop, Codex, Hermes and **Pi Coding Agent** as harnesses.
  
  — [README](https://github.com/agent-sh/computer-use-linux)
- Images default to PNG (JPEG optional), bounded to 1920 px per side and 2 MiB. Metadata includes `coordinate_width/height` and `scale`. — [README](https://github.com/agent-sh/computer-use-linux)
- Derivatives: gih10012/niri-computer-use is "based on computer-use-linux". A Chinese-language HanaAgent integration guide exists. — [GitHub search](https://github.com/gih10012/niri-computer-use)

**iFurySt/open-codex-computer-use ("Open Computer Use")**
- ★2,349, MIT, created 2026-04-17, v0.3.6 released 2026-09-29. npm `open-computer-use` 0.3.6. — [GitHub API](https://github.com/iFurySt/open-codex-computer-use); [npm](https://www.npmjs.com/package/open-computer-use)
- Supports macOS 14+ (Accessibility + Screen Recording grants), Linux and Windows. It exposes `open-computer-use mcp` with a "native nine-tool compatibility surface" modeled on Codex Computer Use (e.g. `list_apps`, `get_app_state`, `press_key`). The CLI has `call` (single or sequenced calls), `js`, `repl` and `doctor`. Installers exist for Codex, Claude Code, Gemini CLI, opencode and DeepSeek Harness, and the skill installs via `npx skills add`. — [README](https://github.com/iFurySt/open-codex-computer-use)

**AmrDab/clawdcursor**
- ★403, MIT, TypeScript, v1.5.14. Three releases came out on 2026-10-07 alone, which shows very fast churn. — [GitHub API/releases](https://github.com/AmrDab/clawdcursor)
- Supports Windows 10/11 (x64/ARM64), macOS 12+, Linux X11 and Wayland.
- Interfaces:
  - MCP stdio plus HTTP at `127.0.0.1:3847/mcp`, with a bearer token in `~/.clawdcursor/token`.
  - CLI.
  - Claude Code plugin + SKILL.md.
- Tools: 7 compound tools (`computer`, `accessibility`, `window`, `system` incl. `ocr`, `browser` via CDP, `task`, `batch`) over 98 primitives.
- It "fuses the accessibility tree and OCR into a confidence-scored set of elements" with `el_NN` IDs. Screenshots are a last-resort tier.
- Safety design:
  - allow/confirm/block tiers
  - screen text wrapped in `<untrusted-screen-content>`
  - visible control banner
  - no telemetry by default
- Named harnesses include Claude Code, Codex, opencode, Goose, Gemini CLI and others.

— [clawdcursor README](https://github.com/AmrDab/clawdcursor)

**lahfir/agent-desktop**
- ★1,773, Apache-2.0, Rust, v0.9.4 released 2026-09-23. npm `agent-desktop` 0.9.4. — [GitHub API](https://github.com/lahfir/agent-desktop); [npm](https://www.npmjs.com/package/agent-desktop)
- Only macOS has shipped features. The README's feature table marks Windows and Linux as "Planned" in every row.
- Interfaces: a CLI plus a C-ABI FFI library and a bundled skill. The README does not describe an MCP server.
- Refs look like `@s8f3k2p9:e1`, with `STALE_REF` and `AMBIGUOUS_TARGET` errors. `launch --cdp` opens a DevTools endpoint.
- The CLI is stateless, and held-input names are "reserved for a stateful daemon".

— [agent-desktop README](https://github.com/lahfir/agent-desktop)

**mediar-ai/terminator**
- ★1,650, MIT, Rust. Last release v0.24.32 on 2026-04-05, last push 2026-06-02. npm `terminator-mcp-agent` latest is 0.24.28 (2026-01-28). — [GitHub API/releases](https://github.com/mediar-ai/terminator); [npm](https://www.npmjs.com/package/terminator-mcp-agent)
- The README says: "Terminator currently supports Windows only. macOS and Linux are not supported." The GitHub description now reads "playwright for windows computer use". It has an MCP agent, a CLI, TS/Python/Rust SDKs, a workflow recorder and a Chrome extension. The newest news item is "01/09/26 - Mediar IDE… is in public access". — [terminator README](https://github.com/mediar-ai/terminator)
- A separate repo, mediar-ai/mcp-server-macos-use (★357, Swift), was pushed 2026-09-30. — [GitHub search API](https://github.com/mediar-ai/mcp-server-macos-use)

**Hacker-Valley-Media/Interceptor**
- ★516, v1.0.24 released 2026-10-02. The license is the **Elastic License 2.0** plus commercial terms (GitHub shows NOASSERTION). — [GitHub API](https://github.com/Hacker-Valley-Media/Interceptor); [README](https://github.com/Hacker-Valley-Media/Interceptor)
- Full native control is macOS only. Windows 11 and Linux get "Browser automation only".
- Architecture: CLI + MCP + local daemon + browser extension + Swift bridge.
- macOS features: a11y trees, input, menus, windows, covered/minimized-window screenshots, screen streaming, OCR, "system/microphone audio", speech recognition.
- Skills install via `interceptor skills adopt`.

— [README](https://github.com/Hacker-Valley-Media/Interceptor)

**amontlabs/lcu ("Codex computer use, decoupled from the app")**
- ★723, MIT, Python, created 2026-09-22, v0.9.7 released 2026-10-07. — [GitHub API](https://github.com/amontlabs/lcu)
- It "exposes Codex's original computer-use runtime to your harness without requiring Codex authentication". The official ChatGPT desktop app "must still be installed locally: it supplies the runtime", and the OpenAI app "retain[s] [its] own terms".
- Platforms: Linux ARM64/x86-64 (X11 only, Ubuntu 24.04 glibc) and macOS Apple Silicon. Windows 11 is a "candidate". Native Wayland is unsupported.
- Adapters exist for Pi, Codex CLI and Claude Code.

— [lcu README](https://github.com/amontlabs/lcu)

**Smaller servers (lower maturity)**
- **mrpulor-gh/nuphus-mcp**: ★322, MIT, Rust, v0.3.1 released 2026-09-28. Windows is full; macOS and Linux are partial. 45 tools (22 desktop, 23 browser). PaddleOCR + YOLO via `desktop_perceive`. Screenshots are PNG/base64. stdio only, "no HTTP server, no daemon". — [README](https://github.com/mrpulor-gh/nuphus-mcp)
- **domdomegg/computer-use-mcp**: ★382, MIT, v1.8.0 released 2026-04-13. nut.js-based, and "near identical" to Anthropic's computer tool. Warns models "are vulnerable to prompt injections". — [README](https://github.com/domdomegg/computer-use-mcp); [GitHub releases](https://github.com/domdomegg/computer-use-mcp/releases)
- **AB498/computer-control-mcp**: ★169, MIT, PyPI 0.3.13 released 2026-07-25. Uses PyAutoGUI + RapidOCR + ONNXRuntime. Supports screenshots (screen or window), OCR, and list/activate windows. — [README](https://github.com/AB498/computer-control-mcp); [PyPI](https://pypi.org/project/computer-control-mcp/)
- **YV17labs/GhostDesk**: ★152, FSL-1.1-ALv2 (source-available). On Linux the server runs in a Docker container driving a virtual Sway desktop (`zwlr_virtual_pointer_v1`, grim). On macOS and Windows it is a native binary. — [README](https://github.com/YV17labs/GhostDesk)
- **Linux desktop-specific**:
  - isac322/kwin-mcp (★62, KDE Plasma 6 Wayland, 30 tools) — [GitHub](https://github.com/isac322/kwin-mcp)
  - IlyasKhallouki/hypruse (★34, Hyprland) — [GitHub](https://github.com/IlyasKhallouki/hypruse)
  - tristanmuzzu/deskwright (★8, GNOME Wayland) — [GitHub](https://github.com/tristanmuzzu/deskwright)
  - asattelmaier/gnome-ui-mcp (★1) — [GitHub](https://github.com/asattelmaier/gnome-ui-mcp)
  - Stars and dates are from the GitHub search API, 2026-10-07.
- **Other 2026 cross-platform entrants** have little traction:
  - opensymph/open-computer-use (Go, ★14) — [GitHub](https://github.com/opensymph/open-computer-use)
  - munimtechnologies/munim-computer-use (Rust, ★12) — [GitHub](https://github.com/munimtechnologies/munim-computer-use)
  - bigduu/Nova (Rust, macOS/Windows, ★22) — [GitHub](https://github.com/bigduu/Nova)
  - zavora-ai/computer-use-mcp (★77) — [GitHub](https://github.com/zavora-ai/computer-use-mcp)
  - minghinmatthewlam/computer-use-mcp (macOS Swift, ★46) — [GitHub](https://github.com/minghinmatthewlam/computer-use-mcp)
  - vectora-foundry/native-devtools-mcp (Rust, ★133) — [GitHub](https://github.com/vectora-foundry/native-devtools-mcp)

**Agent frameworks, reference apps and sandboxes (not drop-in tool layers)**
- **bytedance/UI-TARS-desktop**: ★39,207, Apache-2.0. The last tagged release is v0.3.0 (Agent TARS CLI), 2025-11-04, though the repo was pushed 2026-10-05. Ships local/remote computer and browser operators and a "UI TARS SDK". — [GitHub API/releases](https://github.com/bytedance/UI-TARS-desktop); [README](https://github.com/bytedance/UI-TARS-desktop)
  - `@ui-tars/operator-nut-js` and `@ui-tars/sdk` were last published as 1.2.3 on 2025-06-28. — [npm](https://www.npmjs.com/package/@ui-tars/operator-nut-js)
- **microsoft/UFO**: ★9,947, MIT, v3.0.10 released 2026-09-22.
  - UFO² is the Windows "Desktop AgentOS" (UIA/Win32/COM + hybrid visual detection).
  - UFO³ Galaxy orchestrates Windows, Linux and Android devices over a WebSocket "Agent Interaction Protocol". Linux and Android devices run MCP servers.
  
  — [GitHub API/releases](https://github.com/microsoft/UFO); [README](https://github.com/microsoft/UFO)
- **simular-ai/Agent-S**: ★12,550, Apache-2.0. S3 dates from 2025-10, and the last release is v0.3.2 (2025-12-16).
  - It executes generated pyautogui code via `exec` and needs a grounding model (UI-TARS-1.5-7B recommended).
  - CLI + SDK, no MCP.
  - Reports 72.6% on OSWorld with Behavior Best-of-N.
  
  — [README](https://github.com/simular-ai/Agent-S); [GitHub releases](https://github.com/simular-ai/Agent-S/releases)
- **microsoft/OmniParser**: ★25,493. Its newest news item is from 2026/7 (a YOLOv9-E region detector).
  - Licenses: `icon_detect_v3` is MIT (YOLOv9-based), earlier Ultralytics detectors are AGPL, and caption models are MIT. The repo's license field shows CC-BY-4.0.
  - OmniTool controls a Windows 11 VM.
  
  — [README](https://github.com/microsoft/OmniParser)
- **bytebot-ai/bytebot**: "archived by the owner on Mar 7, 2026", with no reason given. ★11,076, Apache-2.0. Its Ubuntu 22.04 XFCE container exposed `POST localhost:9990/computer-use`. — [README](https://github.com/bytebot-ai/bytebot)
- **huggingface/screenenv**: ★459, MIT. A Docker Ubuntu 22.04 XFCE sandbox with MCP (streamable HTTP), screenshots, mouse/keyboard, video recording and Playwright. The PyPI release is still 0.1.2 (2025-07-25), though the repo was pushed 2026-09-24. — [README](https://github.com/huggingface/screenenv); [PyPI](https://pypi.org/project/screenenv/)
- **e2b-dev/desktop**: Linux Xfce cloud sandbox. Supports screenshots, mouse, keyboard, window listing, app launch and streaming ("only one stream at a time"). The README does not mention MCP. e2b-desktop 2.6.1 was released 2026-10-05. — [README](https://github.com/e2b-dev/desktop); [PyPI](https://pypi.org/project/e2b-desktop/)
- **Anthropic computer-use-demo** (in anthropics/claude-quickstarts, ★17,815):
  - Docker Linux "with X11 + VNC".
  - Supports `computer_20241022` through `computer_20251124`, plus the new `computer_toolset_20260801`, where each action is its own tool.
  - Defaults to `claude-opus-4-8`.
  - "The components are weakly separated: the agent loop runs in the container being controlled by Claude".
  
  — [computer-use-demo README](https://github.com/anthropics/claude-quickstarts/tree/main/computer-use-demo)
- **openai/openai-cua-sample-app**: ★1,886, MIT. Two agents on the Responses API: Playwright (JS) and PyAutoGUI on the real desktop (Python). No MCP. "Generated code runs with your user permissions." — [README](https://github.com/openai/openai-cua-sample-app)
- **Open Interpreter**:
  - The repo redirects to openinterpreter/openinterpreter (★68,519, Apache-2.0, Rust), now "A coding agent for open models". Its README delegates computer use: it "can drive web apps… with agent-browser, or operate and test native apps with trycua". — [GitHub API](https://github.com/openinterpreter/openinterpreter); [README](https://raw.githubusercontent.com/openinterpreter/openinterpreter/main/README.md)
  - The old Python `open-interpreter` package was last released as 0.4.3 on 2024-10-26. — [PyPI](https://pypi.org/project/open-interpreter/)
  - openinterpreter/01 (AGPL) was last pushed 2024-11-01. — [GitHub API](https://github.com/OpenInterpreter/01)
- **goose**: now aaif-goose/goose, ★55,041, Apache-2.0. Its built-in Computer Controller extension is described as web scraping, file caching and automations (`web_scrape`, `cache`), not GUI control. — [GitHub API](https://github.com/aaif-goose/goose); [goose quickstart via search](https://goose-docs.ai/docs/quickstart); [third-party Mintlify docs](https://www.mintlify.com/block/goose/api/extensions/builtin)
- **Browser-only tools** (relevant for the "browser control" requirement):
  - ChromeDevTools/chrome-devtools-mcp: ★53,083, v1.10.1, 2026-09-23 — [GitHub](https://github.com/ChromeDevTools/chrome-devtools-mcp); [npm](https://www.npmjs.com/package/chrome-devtools-mcp)
  - microsoft/playwright-mcp: ★37,901, 0.0.83, 2026-09-28 — [GitHub](https://github.com/microsoft/playwright-mcp)
  - vercel-labs/agent-browser: ★43,622, Apache-2.0, Rust CLI, 0.38.2, 2026-10-01 — [GitHub](https://github.com/vercel-labs/agent-browser); [npm](https://www.npmjs.com/package/agent-browser)
  - browserbase/stagehand: ★25,560, MIT — [GitHub](https://github.com/browserbase/stagehand)
  - steel-dev/steel-browser: ★7,748, Apache-2.0 — [GitHub](https://github.com/steel-dev/steel-browser)
- **Hosted desktops**:
  - Orgo ships an official MCP server with 43 tools over stdio (create computer, bash, screenshot…), via npm `orgo-mcp-server`. — [Orgo MCP docs](https://docs.orgo.ai/guides/mcp)
  - Scrapybara docs still describe "virtual desktop infrastructure"; one analyst profile says the company's product focus is now Capy, a coding agent. — [Scrapybara docs](https://docs.scrapybara.com/llms-full.txt); [Verdantix profile](https://atlas.verdantix.com/vendors/scrapybara)

**Vendor and OS-level efforts**
- Claude Code built-in computer use:
  - Research preview on macOS from about 2026-03-23. — [apidog (secondary)](https://apidog.com/pt/blog/claude-code-computer-use/)
  - Background mode for Pro/Max shipped about 2026-09-02, needs macOS 15+. — [iGeeksBlog](https://www.igeeksblog.com/claude-code-computer-use-background-mac/); [letsdatascience](https://letsdatascience.com/news/anthropic-adds-background-computer-use-on-mac-e2eab345)
  - The roundup says it is a built-in MCP server that doesn't work with `claude -p` and isn't usable by other harnesses. — [Pinggy (third-party)](https://pinggy.io/blog/best_computer_use_mcp_servers/)
- OpenAI Codex computer use: shipped 2026-04-16 ("Codex for (almost) everything"). It runs in the background with its own cursor on macOS and is accessibility-based. — [TestingCatalog](https://www.testingcatalog.com/openai-codex-transformed-into-superapp-with-computer-use.md); [timesofai](https://www.timesofai.com/news/codex-can-control-desktop-via-computer-use/)
  - Community wrappers expose it to other harnesses: tmustier/codex-computer-use-mcp (★26) — [GitHub](https://github.com/tmustier/codex-computer-use-mcp); RS-Nocsi/codex-cua-mcp (★11) — [GitHub](https://github.com/RS-Nocsi/codex-cua-mcp); amontlabs/lcu.
- Microsoft Windows:
  - Native MCP plus the Windows On-device Agent Registry (ODR) went to public preview at Ignite 2025. It ships File Explorer and Settings "agent connectors", a consent proxy and `odr.exe`.
  - These are semantic connectors, not GUI computer use.
  
  — [Microsoft Learn: MCP on Windows](https://learn.microsoft.com/en-us/windows/ai/mcp/overview); [Origin HQ reverse-engineering (Mar 2026)](https://www.originhq.com/research/msft-odr-mcp)
- Apple:
  - MCP groundwork appeared in App Intents code in the macOS Tahoe 26.1 beta (Sept 2025). — [9to5Mac](https://9to5mac.com/2025/09/22/macos-tahoe-26-1-beta-1-mcp-integration/)
  - Claims that macOS 27 / iOS 27 ship system-wide MCP come only from third-party blogs; **unverified**. — [stork.ai](https://www.stork.ai/blog/tag/ios-27); [ChatForest](https://chatforest.com/builders-log/apple-ios-27-mcp-system-wide-siri-core-ai-builder-guide/)
- GNOME/KDE: I found no official upstream agent integration. Everything found is a community project (see Linux list above). — [hyper.ai (third-party)](https://hyper.ai/en/stories/a8f9125353d8f1ec0e8748c4c3d5bf24)

### Inferences
- Cua Driver is the only candidate that covers every required OS, is MIT, and is released several times a week. It already has a11y + screenshot snapshots, zoom, file-path image output, browser CDP routes, trajectory video, permission policy and a skill pack. Wrapping or forking it is far cheaper than rebuilding per-OS backends, especially the Wayland compositor matrix and the Windows background input.
- Single-OS leaders are better on some axes:
  - Windows-MCP for authenticated network transport.
  - Peekaboo for macOS depth and frame capture.
  - computer-use-linux for GNOME/KDE portal handling.
  
  They are useful as references or fallbacks, not as the foundation.
- Treat the frameworks (UI-TARS, UFO, Agent-S, OmniParser) as model or perception components. Treat the reference apps (Anthropic demo, OpenAI sample) as protocol references. None is a reusable, harness-neutral tool layer.

### Gaps
- I could not verify a public tool list or image-return format for Open Computer Use, MacOS-MCP, UI-TARS operators or E2B beyond the READMEs.
- I could not confirm whether Cua Driver's `list_apps` and `list_windows` give general **process** listing (PIDs of non-GUI processes). Windows-MCP's `Process` tool does.
- Steel and Browserbase: I found no evidence of 2026 *desktop* (non-browser) offerings; not verified either way.
- Star counts for the monorepos (trycua/cua, claude-quickstarts) cover the whole repo, not the specific component.

## Q2. Maintenance status (mid/late 2026) and security incidents or design flaws

### Takeaway
**Active (release within about 30 days):**
- Cua Driver
- Windows-MCP and MacOS-MCP
- Peekaboo
- computer-use-linux
- Open Computer Use
- clawdcursor
- agent-desktop
- Interceptor
- lcu
- nuphus-mcp
- UFO

**Slowing:**
- Terminator: Windows-only, last release April 2026.
- UI-TARS-desktop: last tag Nov 2025.
- Agent-S: last release Dec 2025.
- screenenv: last PyPI release July 2025.

**Dead or archived:**
- Bytebot (archived Mar 2026)
- browser-use/macOS-use (archived)
- steipete/macos-automator-mcp (archived)
- Open Interpreter OS mode (replaced)
- openinterpreter/01
- nut.js public repo
- automation-mcp
- mcp-remote-macos-use
- computer_use_ootb

Security problems are systemic, not specific to one project:
- Most servers default to unrestricted input, plus shell, registry or file tools.
- Prompt injection via screen content is warned about but rarely mitigated.
- Some Linux servers bypass portal consent.

### Cited Findings
- Archived repos (GitHub API flag, 2026-10-07):
  - bytebot-ai/bytebot, archived 2026-03-07 — [GitHub API](https://github.com/bytebot-ai/bytebot); [README notice](https://github.com/bytebot-ai/bytebot)
  - browser-use/macOS-use, last push 2025-03-05 — [GitHub API](https://github.com/browser-use/macOS-use)
  - steipete/macos-automator-mcp — [GitHub API](https://github.com/steipete/macos-automator-mcp)
- Dormant (last push):
  - ashwwwin/automation-mcp: 2025-06-11 — [GitHub API](https://github.com/ashwwwin/automation-mcp)
  - baryhuang/mcp-remote-macos-use: 2025-06-10 — [GitHub API](https://github.com/baryhuang/mcp-remote-macos-use)
  - nut-tree/nut.js: 2024-05-01, no license detected by the API — [GitHub API](https://github.com/nut-tree/nut.js)
  - The community fork @nut-tree-fork/nut-js was last published as 4.2.6 on 2025-03-13 — [npm](https://www.npmjs.com/package/@nut-tree-fork/nut-js)
  - showlab/computer_use_ootb: 2025-05-21 — [GitHub API](https://github.com/showlab/computer_use_ootb)
  - OpenInterpreter/01: 2024-11-01 — [GitHub API](https://github.com/OpenInterpreter/01)
- Terminator dropped macOS and Linux ("supports Windows only"). Its last release was 2026-04-05 and its last push 2026-06-02. — [README](https://github.com/mediar-ai/terminator); [GitHub releases](https://github.com/mediar-ai/terminator/releases)
- The Cua README lists cuabot as deprecated, says it has "known security issues", and tells users to stop and uninstall it. It also deprecates the old cua-computer-server and cua-agent stack. — [trycua/cua README](https://github.com/trycua/cua)
- Windows-MCP design warnings:
  - It "operates with full system access and can perform irreversible operations".
  - User takeover is "best-effort, not a security boundary".
  - Telemetry is **on by default** (`ANONYMIZED_TELEMETRY=true`).
  - It exposes PowerShell and Registry tools.
  
  — [Windows-MCP README](https://github.com/CursorTouch/Windows-MCP)
- The Pinggy roundup separately recommends trimming the PowerShell and Registry tools. — [Pinggy (third-party)](https://pinggy.io/blog/best_computer_use_mcp_servers/)
- Cua Driver's default `standard` permission mode "allows input to every app". `unrestricted` requires `--dangerously-bypass-approvals`. — [connect-your-agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md); [libs/cua-driver README](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/README.md)
- The Anthropic reference demo warns that "instructions on webpages or contained in images may override user instructions". It recommends a dedicated VM or container, a domain allowlist and human confirmation. — [computer-use-demo README](https://github.com/anthropics/claude-quickstarts/tree/main/computer-use-demo)
- domdomegg/computer-use-mcp warns models "are vulnerable to prompt injections" and suggests a sandboxed user account. — [README](https://github.com/domdomegg/computer-use-mcp)
- computer-use-linux:
  - Notes that "AT-SPI exposes window contents to any client on the session bus".
  - Keeps the ydotoold socket at 0600 and warns against running it as root.
  - Disables `run_shell` unless `COMPUTER_USE_LINUX_ENABLE_SHELL=1`.
  - Masks likely password fields.
  
  — [README](https://github.com/agent-sh/computer-use-linux)
- kwin-mcp sends input through KWin's private EIS D-Bus interface "rather than the XDG RemoteDesktop portal, so no user confirmation dialogs appear". — [search summary of kwin-mcp listing](https://glama.ai/mcp/servers/isac322/kwin-mcp)
- clawdcursor is the only project found that wraps screen text in `<untrusted-screen-content>` and has allow/confirm/block action tiers. — [clawdcursor README](https://github.com/AmrDab/clawdcursor)
- Agent-S runs model-generated Python via `exec`. Its README warns it "runs Python code to control your computer". — [Agent-S README](https://github.com/simular-ai/Agent-S)
- Related incidents (none specific to a computer-use MCP server):
  - Claude Desktop "PromptFiction" (July 2026): crafted `claude://` links auto-submitted prompts; fixed in 1.1.2321. — [letsdatascience](https://letsdatascience.com/news/oasis-discloses-claude-desktop-prompt-injection-flaw-6de3c828)
  - OpenHuman desktop agent CVE-2026-55743: indirect prompt injection led to a sandbox allowlist bypass and RCE. — [Halo Security advisory](https://cve.halosecurity.com/cve-advisory/cve-2026-55743-openhuman-desktop-agent-command-bypass-leading-to-rce)
  - An aggregator counts about 30 MCP CVEs in Jan–Feb 2026. — [heyuan110 (aggregator)](https://heyuan110.com/posts/ai/2026-03-10-mcp-security-2026)
- Licensing traps:
  - Cua's perception extension uses an AGPL-3.0-only OmniParser icon detector. — [libs/cua-driver README](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/README.md)
  - Interceptor is under the Elastic License 2.0. — [Interceptor README](https://github.com/Hacker-Valley-Media/Interceptor)
  - GhostDesk is FSL-1.1-ALv2. — [GhostDesk README](https://github.com/YV17labs/GhostDesk)
  - lcu depends on OpenAI's app runtime under OpenAI's terms. — [lcu README](https://github.com/amontlabs/lcu)

### Inferences
- A new toolkit should ship a restrictive default mode: allowlists per app, shell off by default, and no Registry or FileSystem tools. It should also tag screen-derived text as untrusted, as clawdcursor does. Most incumbents default to "allow everything".
- Building on lcu or the Codex wrappers is legally and operationally fragile: they depend on a closed vendor binary.
- Avoid the perception/OmniParser AGPL piece if the toolkit will be redistributed. MIT YOLOv9-based `icon_detect_v3` or RapidOCR/PP-OCR are cleaner choices.

### Gaps
- I found no CVE or published incident that specifically targets an open-source computer-use MCP server (Cua, Windows-MCP, Peekaboo, etc.).
- I did not audit cuabot's "known security issues". The README gives no details.

## Q3. Which projects offer a clean daemon/client split for driving a remote VM over SSH or Tailscale?

### Takeaway
- **Cua Driver** gives the cleanest pattern for the user's needs: a per-OS daemon (`cua-driver serve`) on the target machine, with MCP-over-SSH-stdio from the controller. It also has a shared-socket daemon and Cua Spaces relay/Tailscale/SSH hosting. Its only network HTTP endpoint is loopback and legacy.
- **Windows-MCP and MacOS-MCP** are the only ones with first-class authenticated network MCP (HTTP + TLS + auth/OAuth).
- **UFO Galaxy** has a WebSocket device-agent protocol, but it is a framework.
- Most others are stdio-only. computer-use-linux and Peekaboo still work over `ssh host binary mcp`.

### Cited Findings
- Cua Driver:
  - "always runs on the machine whose desktop it drives. To reach a VM or a remote computer, run the driver there and carry MCP over SSH". Example: `codex mcp add cua-driver-vm -- ssh -T -o BatchMode=yes "lume@${VM_IP}" …/cua-driver mcp`.
  - "The remote `cua-driver mcp` proxies to the daemon in the logged-in guest session." The guide also covers driving a Windows desktop over SSH.
  
  — [Cua Driver: Run in a VM or over SSH](https://cua.ai/docs/cua-driver/guides/vms-and-remote.md)
- `cua-driver serve --socket <path>` + `cua-driver mcp --socket <path>` "lets several clients share one daemon". On macOS, `cua-driver mcp` relies on the `CuaDriver.app` daemon. — [Cua Driver overview](https://cua.ai/docs/cua-driver)
- "The authenticated loopback HTTP endpoint remains on legacy MCP." Modern HTTP awaits "a reviewed application-handle contract". — [cua-driver mcp-protocol-and-skills.md](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/docs/mcp-protocol-and-skills.md)
- Cua Spaces:
  - Spaces run "on your Mac, on other machines you own, and in your own cloud account". They are hosted via "relay, Tailscale or SSH".
  - `cua host setup` makes a machine reachable through the cua.ai relay.
  - cua-spacesd exposes gRPC on port 3211 inside sandboxes.
  
  — [trycua/cua README](https://github.com/trycua/cua)
- There is also a guide to "Host Spaces on your spare Mac… over the relay, ssh or Tailscale". — [Cua docs index](https://cua.ai/docs/llms.txt)
- Windows-MCP: SSE and streamable HTTP are "Network-accessible". It supports auth keys, IP allowlists, TLS and OAuth 2.0 + PKCE, and a per-user Scheduled Task autostart. — [Windows-MCP README](https://github.com/CursorTouch/Windows-MCP)
- MacOS-MCP: `--transport streamable-http --host HOST --port PORT` ("recommended for production"). — [MacOS-MCP README](https://github.com/CursorTouch/MacOS-MCP)
- clawdcursor: `clawdcursor agent` runs an HTTP MCP daemon on port 3847, bound to localhost, with a bearer token. — [clawdcursor README](https://github.com/AmrDab/clawdcursor)
- computer-use-linux: MCP stdio only, "opens no TCP/UDP listener". — [README](https://github.com/agent-sh/computer-use-linux)
- Peekaboo: stdio only, HTTP/SSE "not implemented yet". `--bridge-socket` attaches to a local Bridge host. — [Peekaboo MCP.md](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/MCP.md)
- nuphus-mcp: "no HTTP server, no daemon". — [README](https://github.com/mrpulor-gh/nuphus-mcp)
- agent-desktop: stateless CLI, and the daemon is "reserved". — [README](https://github.com/lahfir/agent-desktop)
- UFO³ Galaxy: per-device server + client, and the "Agent Interaction Protocol" is a "WebSocket-based secure coordination layer". — [UFO README](https://github.com/microsoft/UFO)
- screenenv exposes MCP over streamable HTTP from its container (`MCPRemoteServer`). — [screenenv README](https://github.com/huggingface/screenenv)
- Bytebot (archived) exposed REST at `localhost:9990/computer-use`. — [Bytebot README](https://github.com/bytebot-ai/bytebot)
- E2B Desktop is a cloud SDK with streaming URLs. — [E2B Desktop README](https://github.com/e2b-dev/desktop)

### Inferences
- MCP-over-SSH-stdio is the lowest-friction remote pattern and needs no new network surface. Any stdio server qualifies (Cua Driver, computer-use-linux, Peekaboo).
- For a headless Linux VM, the issue is not transport but session: the driver needs a logged-in graphical session (or Xvfb/a nested compositor) and, on Wayland, portal grants. Cua documents this for Lume/macOS and has a "test in a sandbox" Linux guide. Windows-MCP has the most mature authenticated HTTP if a persistent network daemon is preferred.
- A harness-agnostic toolkit could adopt Cua's split directly: a per-machine daemon plus thin `mcp`/`call` front-ends. It would add an authenticated network transport (e.g. Tailscale-only bind) where Cua's HTTP is still loopback/legacy.

### Gaps
- I did not verify how Cua Driver behaves on a headless Linux VM over SSH (DISPLAY/WAYLAND_DISPLAY env inheritance, portal consent without a local user). The doc covers the macOS Lume VM and Windows over SSH explicitly.
- I found no project with built-in Tailscale-aware auth for the computer-use daemon itself. Cua's relay is for Spaces, not the bare driver.

## Q4. Which projects explicitly target harness-agnostic use (MCP + CLI + skills), and how do they handle image returns for harnesses that don't render MCP images?

### Takeaway
Several 2026 projects now ship the same trio of MCP + shell CLI + Agent Skill:
- Cua Driver
- computer-use-linux
- Open Computer Use
- clawdcursor
- Interceptor
- agent-desktop (CLI + skill only)

Cua Driver is the most explicit: presets for about 12 harnesses, including opencode and Pi. The main image-return strategies are:
- write the screenshot to a file path instead of base64 (Cua `screenshot_out_file`, Peekaboo capture outputs)
- downscale with coordinate-mapping metadata (Cua, computer-use-linux)
- minimize pixels via a11y/OCR-first observation (clawdcursor, Windows-MCP, agent-desktop)

### Cited Findings
- Cua Driver:
  - "An agent reaches Cua Driver in one of two ways: an MCP client launches `cua-driver mcp`, or a skill teaches a shell-capable agent to run `cua-driver call <tool>`. The harness owns the model and the loop".
  - `mcp-config --client` presets cover Claude Code, Codex, Cursor, Antigravity/Gemini, OpenClaw, Hermes, OpenCode, Factory Droid, ZCode, Qwen Code and Pi. For Pi the docs say "No MCP: runs one-shot `cua-driver call …` commands".
  
  — [Cua Driver: Connect your agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md)
- `cua-driver skills install` links the skill into Claude Code, Codex, Prime Agent, OpenClaw, OpenCode, Antigravity, Hermes and Pi. From 0.28.0 the skill is also served as MCP resources, verified with Codex 0.154.0 and Claude Code 2.1.268. — [connect-your-agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md); [mcp-protocol-and-skills.md](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/docs/mcp-protocol-and-skills.md)
- Cua Driver image handling:
  - `screenshot_out_file` writes the PNG to disk and returns `screenshot_file_path` instead of base64.
  - `max_image_dimension` caps size, with automatic coordinate mapping.
  - `include_screenshot:false` returns the tree only.
  
  — [window-state tools](https://cua.ai/docs/cua-driver/reference/mcp-tools/window-state.md); [screen tools](https://cua.ai/docs/cua-driver/reference/mcp-tools/screen.md)
- Cua also ships `cua-mcp-filter` to hide tools for small local models: "Every tool schema costs context". — [connect-your-agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md)
- computer-use-linux ships MCP + CLI + skill and names Pi Coding Agent and Codex. Images are bounded PNG/JPEG with `coordinate_width/height` and `scale` metadata. — [README](https://github.com/agent-sh/computer-use-linux)
- Open Computer Use: MCP + `open-computer-use call` (prints "the MCP-style JSON result") + `js`/`repl` + skill. Installers cover Codex, Claude Code, Gemini CLI, opencode and DeepSeek Harness. — [README](https://github.com/iFurySt/open-codex-computer-use)
- clawdcursor: MCP stdio/HTTP + CLI + Claude Code plugin with SKILL.md. It targets Claude Code, Codex, opencode, Goose, Gemini CLI, Cline, Zed, etc. Screenshots are the last-resort tier and "stay in RAM". — [README](https://github.com/AmrDab/clawdcursor)
- Interceptor: CLI + MCP. "Any agent that can run shell commands." Ships `.claude`, `.codex`, `.gemini` and `.agents` skill dirs. — [README](https://github.com/Hacker-Valley-Media/Interceptor)
- agent-desktop: CLI + skill (`agent-desktop skills get desktop --full`), no MCP. Screenshot is a PNG file (`screenshot --app Finder`). — [README](https://github.com/lahfir/agent-desktop)
- Peekaboo: CLI + MCP. `capture` writes PNG frames, `contact.png`, `metadata.json` and optional MP4 to an output dir. The MCP stdio server never streams raw bytes on stdout. — [Peekaboo capture.md](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/commands/capture.md); [Peekaboo MCP.md](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/MCP.md)
- lcu takes a different route: per-harness adapters (Pi slash commands, a Claude Code plugin, Codex CLI) around OpenAI's runtime. — [lcu README](https://github.com/amontlabs/lcu)
- Third-party view: the roundup names Cua Driver, Windows-MCP, Open Computer Use and computer-use-mcp as harness-agnostic, and says Claude Code's built-in server is not. — [Pinggy (third-party)](https://pinggy.io/blog/best_computer_use_mcp_servers/)
- Harness-side image support:
  - **Codex CLI**: renders MCP image outputs (a ratatui_image cell) and passes MCP images to the model (PR #5600). A Jan 2026 fix (#9815) stopped images being dropped when text preceded them. Source is a mirror of codex-rs. — [codex-rs mirror](https://forge.lthn.ai/core/core-agent-ide/src/commit/337643b00a385b6980112dd7dcfcc172765e77be/codex-rs)
  - **OpenCode**: an image-attachment bug drops images for custom OpenAI-compatible providers (anomalyco/opencode#20802). — [OpenCode-vision-OmniRoute listing](https://glama.ai/mcp/servers/WormAlien/OpenCode-vision-OmniRoute)
  - **Cursor**: one bug report says the model gets MCP images but the UI doesn't paint them. — [Cursor forum](https://forum.cursor.com/t/regression-mcp-tool-image-content-no-longer-renders-in-agent-chat-model-receives-it-ui-does-not/168824)
- **Pi now has built-in MCP**. Pi's docs say it "connects to Model Context Protocol servers over stdio or streamable HTTP". Tools can be exposed as `direct`, `deferred` (tool_search) or `codemode` (default). In codemode scripts, "`image(result.content[0])` forwards an image block". Pi implements the Agent Skills specification. — [pi docs/mcp.md](https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/mcp.md); [pi docs/skills.md](https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/skills.md)
  - This **conflicts** with Cua's table entry ("Pi: No MCP"), which is probably outdated. — [Cua connect-your-agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md)
  - Note that Pi's README now points to earendil-works/pi as the canonical repo. — [pi README](https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/README.md)

### Inferences
- The emerging pattern for harness-agnostic computer use is:
  1. One native binary per OS.
  2. `mcp` stdio for MCP-capable harnesses.
  3. `call <tool> <json>` for shell-only harnesses.
  4. A SKILL.md teaching the observe→act→verify loop.
  5. Images returned as base64 MCP image content *or* written to a file path the harness can open with its own image-reading tool.
  
  Cua Driver already implements all five. A new project would mostly add value through packaging, policy defaults, audio/video, and network transport.
- For harnesses with weak MCP image rendering (opencode with custom providers; codemode-style indirection in Pi), the file-path route plus the harness's native `read`-an-image tool is the most portable option. Pairing it with `zoom` and region crops keeps small text legible without full-res screenshots.

### Gaps
- I did not verify how each harness (opencode, Pi) renders MCP `image` content blocks in October 2026. That belongs to the harness researcher's scope.
- I did not verify whether Cua's CLI `call` path returns base64 to stdout by default or requires `screenshot_out_file`.

## Q5. Recommendation: foundation vs pieces to borrow vs uncovered gaps

### Takeaway
**Foundation:** build on, or thinly wrap, **Cua Driver** (MIT, Rust, all four platform targets, MCP + CLI + skills + SDK, zoom, a11y, SSH remote, recording). Add the missing pieces:
- audio capture
- returning short video clips to the model
- a network-authenticated daemon transport
- a hardened default policy
- MIT-only OCR / set-of-marks

**Borrow from:**
- Windows-MCP: network auth and transport.
- Peekaboo: adaptive frame capture / contact sheets.
- computer-use-linux: GNOME/KDE portal fallbacks and the `doctor` command.
- clawdcursor: a11y+OCR fusion and untrusted-content tagging.
- Interceptor: macOS audio.
- OmniParser `icon_detect_v3` (MIT): set-of-marks.

### Cited Findings
- Coverage evidence for Cua Driver as a foundation: platforms and Wayland limits ([platform support](https://cua.ai/docs/cua-driver/concepts/platform-support.md)); MIT driver license ([libs/cua-driver README](https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/README.md)); release cadence 0.33.0→0.34.0 in three days ([GitHub releases](https://github.com/trycua/cua/releases)); zoom ([screen tools](https://cua.ai/docs/cua-driver/reference/mcp-tools/screen.md)); SSH remote ([vms-and-remote](https://cua.ai/docs/cua-driver/guides/vms-and-remote.md)); multi-harness setup ([connect-your-agent](https://cua.ai/docs/cua-driver/guides/connect-your-agent.md)).
- Open Interpreter, a former computer-use pioneer, now uses trycua for native app control instead of its own OS mode. That is ecosystem evidence that Cua is becoming a default substrate. — [Open Interpreter README](https://raw.githubusercontent.com/openinterpreter/openinterpreter/main/README.md)
- Cua Driver's Linux limits: KDE/KWin experimental, Hyprland experimental, GNOME needs a Shell helper and one Shell restart, native Wayland opt-in. — [platform support](https://cua.ai/docs/cua-driver/concepts/platform-support.md)
  - computer-use-linux takes a different Linux approach: portal RemoteDesktop + ydotool, GNOME Shell DBus screenshots, and KDE clipboard text input. — [computer-use-linux README](https://github.com/agent-sh/computer-use-linux)
- Pieces to borrow:
  - **Windows-MCP**: `Process` list/kill and authenticated HTTP transport (TLS/OAuth/IP allowlists). — [Windows-MCP README](https://github.com/CursorTouch/Windows-MCP)
  - **Peekaboo**: `capture live` with diff-based frame keeping, contact sheet and MP4. — [capture.md](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/commands/capture.md)
  - **clawdcursor**: OCR fused into the element map, `<untrusted-screen-content>`, allow/confirm/block. — [README](https://github.com/AmrDab/clawdcursor)
  - **Interceptor**: system/mic audio on macOS (ELv2; reference only). — [README](https://github.com/Hacker-Valley-Media/Interceptor)
  - **OmniParser**: MIT `icon_detect_v3` and MIT caption models. — [README](https://github.com/microsoft/OmniParser)
  - **AB498/computer-control-mcp**: RapidOCR + ONNXRuntime as a light cross-platform OCR stack. — [README](https://github.com/AB498/computer-control-mcp)
  - **Browser layer**: chrome-devtools-mcp, playwright-mcp or agent-browser instead of reinventing CDP control. — [chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp); [playwright-mcp](https://github.com/microsoft/playwright-mcp); [agent-browser](https://github.com/vercel-labs/agent-browser)
- Audio capture: the only audio found is Interceptor (macOS-only, ELv2, system/mic audio) and Cua Spaces sandbox streaming (cua-spacesd "video and audio streaming"). — [Interceptor README](https://github.com/Hacker-Valley-Media/Interceptor); [trycua/cua README](https://github.com/trycua/cua)
- Video: Cua Driver records `recording.mp4` trajectories for demos ([trajectories](https://cua.ai/docs/cua-driver/guides/trajectories.md)), and Peekaboo can emit MP4 and frames ([capture.md](https://raw.githubusercontent.com/openclaw/Peekaboo/main/docs/commands/capture.md)). Neither documents returning a short clip as model input.

### Inferences
- **Gaps no candidate covers (with evidence above):**
  1. Cross-platform **audio capture** returned to omni models (system audio, mic) on Win/macOS/Linux, including PipeWire on Wayland.
  2. **Short screen-video clips as model input**: a bounded N-second clip or keyframe bundle returned as tool output, not a demo trajectory.
  3. **Authenticated network transport** for the Cua daemon (its HTTP is loopback and legacy). Only Windows-MCP/MacOS-MCP have this, and only on their own OS.
  4. **MIT-clean OCR + set-of-marks overlay** shipped by default across all OSes. Cua's is optional and partly AGPL. clawdcursor has OCR but is young.
  5. **Consistent Wayland coverage on KDE and Hyprland** (experimental everywhere). No upstream GNOME/KDE agent API exists.
  6. **General process listing** beyond GUI apps on every OS (only clearly present in Windows-MCP).
  7. A **safe-by-default policy profile** (shell/registry off, per-app allowlists, untrusted-content tagging) that is the default rather than opt-in.
- **Build vs. buy:** reimplementing Cua Driver's per-OS backends (UIA, AX/ScreenCaptureKit, AT-SPI, X11, several Wayland compositors, CDP routes) would be very large. A thin harness-agnostic layer is more defensible: a skill pack, an image/video/audio broker, network transport and a policy profile, using `cua-driver` as the per-OS engine (pinned version, MIT). Fallback adapters (Windows-MCP, Peekaboo, computer-use-linux) could fill per-OS gaps.
- **Risk of depending on Cua:**
  - Very fast churn: multiple releases per day, plus a history of deprecating whole stacks (cua-computer-server, cua-agent, cuabot).
  - The company also sells a hosted product.
  
  Pin versions and keep the integration surface at the documented MCP/CLI boundary.

### Gaps
- I did not benchmark reliability or latency of any candidate. All judgments are based on documentation.
- I could not confirm Cua Driver's behavior or packaging on Linux ARM64 or non-x86_64 hosts. Its docs say x86_64 for Linux.
- I found no maintained project offering PipeWire/WASAPI/CoreAudio capture as an MCP tool. Absence may reflect search limits rather than nonexistence.
