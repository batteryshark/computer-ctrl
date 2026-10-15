# Desktop isolation and project scope

Research date: 2026-10-13. Documentation and local source inspection only; no desktop/session experiments, installed packages, settings changes, or implementation changes. Platform details: [Linux](desktop_isolation_linux.md), [Windows](desktop_isolation_windows.md), [macOS](desktop_isolation_macos.md).

## Finding

A VM is one solution, but the useful requirement is a **separate graphical execution session** with its own input, focus, rendering and audio route. A second physical or virtual monitor inside the human's existing desktop does not provide that separation. An independent session can be viewed in a window on a second monitor, or left out of view; the viewer is not the isolation mechanism.

| Platform | Promising non-VM option | What is established | What remains to prove with cctl |
|---|---|---|---|
| Linux | Dedicated account, Xvnc desktop (or Xvfb plus a desktop and viewer) | Xvnc provides a virtual X server display; applications render there and a VNC client views it. [TigerVNC](https://tigervnc.org/doc/Xvnc.html) | Independent Cua/cctl endpoints, session bus and audio; complete native input/capture/a11y/clip path; viewer-disconnect behavior. |
| Windows | Win32 Child Sessions, using a loopback RDP client | Documented Windows facility; Power Automate PiP uses a second session for physical mouse/keyboard automation alongside normal work. [Child Sessions](https://learn.microsoft.com/en-us/windows/win32/termserv/child-sessions), [Power Automate PiP](https://learn.microsoft.com/en-us/power-automate/desktop-flows/run-desktop-flows-pip) | Launch and bind Cua/cctl to the child rather than parent; native screenshots/clips, audio routing, minimized viewer and disconnection. |
| macOS | Another user's graphical login via Remote Desktop virtual display | Apple explicitly documents controlling that user's desktop while the locally logged-in user continues uninterrupted. [Apple Remote Desktop](https://support.apple.com/guide/remote-desktop/choose-how-to-control-and-observe-apd4f46319e/mac) | Current OS + CuaDriver.app/Accessibility/ScreenCaptureKit behavior in that session, permissions, audio, and a practical client/lifecycle path. Same-Mac loopback viewing is not established by the cited guide. |

These are documented OS/project capabilities, **not a claim that cctl already supports them**. Windows Child Sessions are especially worth investigating: the ordinary client RDP concurrency restriction does not mean every supported Windows session mechanism requires a VM.

## Important distinctions

- **Workspace versus session.** Mission Control Spaces, Windows Task View desktops and ordinary Linux workspaces organize one user's windows. They do not supply the complete independent computer-use environment requested here. The platform notes cover the distinction from lower-level alternate desktops and display servers.
- **Separate session versus existing windows.** The agent usually launches its own application instances. It does not automatically inherit the exact unsaved document, login state or already-open application on the human's desktop. Files can be shared deliberately; concurrent browser profiles and application singleton behavior need attention.
- **Noninterference versus security isolation.** A separate display is useful even without a VM, but it is not a separate kernel or necessarily a separate filesystem identity. Windows child sessions use the parent user's account. Separate Linux/macOS accounts improve separation but do not reproduce a VM's environment. Do not infer the existing `sandbox` policy from a session being offscreen.
- **Remote viewing versus remote control.** A viewer that mirrors the human's desktop leaves the original problem intact. The driver must run inside and target the independent session, rather than click the viewer from the human's desktop.
- **Hidden versus usable while disconnected.** Rendering, automation and audio can change when a viewer is minimized, disconnected, the parent locks, or the host sleeps. These are independent capabilities to measure.

## Audio must be handled explicitly

Silencing playback and making audio available to the agent are different requirements. The desired behavior is: applications produce audio into a session-specific endpoint, cctl can capture it, and the human hears it only when monitoring is enabled.

Microsoft documents that ordinary WASAPI endpoint loopback can include audio originating in multiple Terminal Services sessions, while RDP creates audio devices visible only to its session. Therefore neither a new login nor a mute toggle proves isolated, still-recordable audio. [Microsoft loopback recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)

Linux null sinks and independent audio servers offer a promising route (see Linux note). macOS and Windows need an explicit experiment verifying both silence on the human's output and successful agent recording. A VM viewer can also forward guest audio, so it needs a monitoring policy too.

## Browser-only work can use a smaller solution

Chrome Headless runs without visible platform windows; Playwright browser contexts separate cookies and storage. This can remove desktop interference for tasks wholly inside web content, without provisioning a whole desktop. It does not cover arbitrary native applications or desktop dialogs. Audio handling remains separate. [Chrome Headless](https://developer.chrome.com/docs/automation-and-testing/headless), [Playwright contexts](https://playwright.dev/docs/browser-contexts)

The current cctl browser implementation launches an isolated Chromium **profile**, but expects a native window and changes delivery behavior by policy profile. That is useful background operation, not an existing headless-desktop feature. [Local implementation](../../src/cctl/browser.py)

## Recommendation: an optional companion project

If pursued beyond experiments, make session management a separate project with cctl as one consumer. Its purpose would be to prepare and keep an independent desktop usable for arbitrary workloads. Native session mechanisms and VMs can be adapters behind the same small interface; there is no need to promise every provider initially.

| Module | Responsibilities |
|---|---|
| Session-management companion | Create/attach/list/stop sessions; OS-specific login/display lifecycle; launch a workload inside the session; optional viewer; audio routing and monitoring; reconnection and cleanup; report actual isolation and lifetime capabilities. |
| computer-ctrl | Observe and act inside a selected session; coordinate frames, accessibility, browser tools, OCR, audio/video capture, grounding, MCP/CLI outputs; verify that the connected driver belongs to the requested session. |

The seam is **launching or connecting to a workload in a specific graphical session**. Start with ordinary process launch, environment and existing stdio/SSH transport. A future session description might contain an opaque session identity, connection information, viewer access, audio endpoint and measured capabilities. Do not finalize a large protocol until two real adapters demonstrate what actually varies.

The companion should work with a plain GUI application before cctl is involved; cctl should remain usable against a manually prepared desktop. This makes each project independently useful and keeps OS provisioning out of the 27-tool computer-use contract. Reuse Xvnc/Xpra, Windows session facilities and Apple tooling rather than building new display servers or viewers.

Before creating a new implementation, evaluate existing tools. [ParaDesk](https://github.com/sinpoce/ParaDesk) documents a Windows child-session viewer and CLI intended for agents, including workload launch. It is a possible provider to reuse, not a dependency vetted here. Linux Xpra and macOS VM lifecycle tools supply other parts of this space; the platform notes describe them. A new companion should own only the missing integration that experiments establish.

This is a recommendation, not a decision to create a repository or move code. The user requested exploration only.

## Small cctl changes likely to be necessary later

Local source inspection identifies these integration concerns; none was changed:

1. **Explicit target identity.** Linux discovery honors a supplied `DISPLAY`/`WAYLAND_DISPLAY`; otherwise it picks a same-user graphical process. That is insufficient when multiple sessions are available. [session_env.py](../../src/cctl/session_env.py)
2. **Per-session endpoints.** cctl's socket/port file and Cua's default socket are per-user by default. The Cua status check does not pass the selected socket. Multiple same-user sessions need endpoint ownership/identity validation, not merely a different display variable. Configuration already permits separate cache/state paths and a Cua socket. [config.py](../../src/cctl/config.py), [daemon.py](../../src/cctl/daemon.py), [session_env.py](../../src/cctl/session_env.py)
3. **Windows launch targeting.** The current scheduled-task launcher chooses a user with interactive logon, not an explicit child session. Its launch path cannot be assumed to select the right desktop. [cli.py](../../src/cctl/cli.py)
4. **Session-aware health.** `doctor` equates inactive logind sessions with black capture. A headless display needs capability-based checks; actual screenshot rejection currently happens only for a blank image. [engine.py](../../src/cctl/engine.py)
5. **Audio selection.** Linux `system` capture chooses the default sink monitor; clips request that path. Windows selects the default speaker for loopback. Session output routing belongs in the companion; selecting and capturing its endpoint belongs in cctl. [media.py](../../src/cctl/media.py), [engine.py](../../src/cctl/engine.py)

Existing desktop-scope input is appropriate **inside** a dedicated session: X11 uses xdotool; Windows hover uses SetCursorPos; macOS/Windows pixel operations target Cua's desktop. The goal is to put those operations in the correct session, not suppress all native input. [x11.py](../../src/cctl/x11.py), [cua_input.py](../../src/cctl/cua_input.py)

## Proposed evidence before implementation commitment

1. Prove a Linux Xvnc desktop and a Windows child session independently of cctl. Investigate macOS's second-user route with a smaller feasibility spike because driver permissions and session lifecycle are unresolved.
2. In each candidate, run editor, browser, pixel/canvas, drag, modal-dialog, screenshot, clip and audio tasks while activity continues on the human desktop. Verify human pointer/focus/typing remain correct, clipboard sharing is explicit, and agent audio is recorded without leaking to the human's speakers.
3. Repeat with viewer hidden/minimized/disconnected and parent locked; report failures precisely rather than promising all modes work. Validate expected persistence and cleanup without ending unrelated sessions.
4. Run the resulting cctl acceptance path from at least two harnesses, per AGENTS.md. Record latency/resource use and app/profile limitations. Keep VMs as a fallback where native sessions fail the required behavior.

No acceptance test was run in this research session; no phase is marked complete by these findings.
