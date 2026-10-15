# Windows desktop isolation for concurrent computer use

Researched 2026-10-13. Documentation/source review only; no Windows settings, sessions, or implementation changed. The cross-platform session owner should update the tracker with this note.

## Takeaway

**Windows has a credible non-VM candidate: a Remote Desktop child session.** It deserves a bounded prototype in a separate session-management companion, with computer-ctrl as one consumer. Microsoft already uses it for Power Automate's picture-in-picture (PiP) automation while the person continues working. A persistent VM remains the straightforward fallback for application compatibility and stronger separation. Merely adding a monitor or Task View desktop does not provide independent computer-use input.

## Evidence and distinctions

| Mechanism | What the primary sources establish | Implication for computer-ctrl (inference unless stated) |
|---|---|---|
| Another physical/virtual monitor | Local displays belong to the console terminal; there is one active console terminal. [Terminal model](https://learn.microsoft.com/en-us/windows/win32/termserv/consoles-vs-terminals) | More screen area still shares the local cursor/focus. An indirect display driver alone is not a second input session. |
| Task View virtual desktop | These organize and hide windows; applications keep running normally. [Windows team explanation](https://devblogs.microsoft.com/oldnewthing/20200421-00/?p=103689) | Useful organization, insufficient input/audio isolation. |
| Alternate Win32 desktop/window station | `CreateDesktop` associates a desktop with a window station. Only the input desktop is active; only the interactive station can receive user input. Every RDS session has its own `WinSta0`. [CreateDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createdesktopw), [desktops](https://learn.microsoft.com/en-us/windows/desktop/winstation/desktops), [stations](https://learn.microsoft.com/en-us/windows/win32/winstation/window-stations) | An offscreen desktop can host windows, but is not a drop-in isolated pixel/mouse desktop. |
| Fast User Switching / disconnected user | Other users' processes and network connections persist across switching. [Fast User Switching](https://learn.microsoft.com/en-us/windows/win32/shell/fast-user-switching) | A running process is not proof that screenshots and physical input still work. DXGI explicitly returns `DXGI_ERROR_SESSION_DISCONNECTED` for disconnected sessions. [Capture API](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/nf-dxgi1_2-idxgioutput1-duplicateoutput) |
| Ordinary client RDP | Microsoft's console/RDP model moves the user's session between local and remote terminals. Its own unattended automation cannot run on Windows 10/11 while another active Windows session exists. [Terminal model](https://learn.microsoft.com/en-us/windows/win32/termserv/consoles-vs-terminals), [Power Automate unattended](https://learn.microsoft.com/en-us/power-automate/desktop-flows/run-unattended-desktop-flows) | Ordinary RDP/Fast User Switching on client Windows is not the supported route to simultaneous independent human and agent desktops. Child sessions below are an important special case. |
| Server RDS / AVD multi-session | Server RDSH supports concurrent user sessions. Windows Enterprise multi-session supports concurrent interactive users, with production use restricted to Azure Virtual Desktop service. [Terminal model](https://learn.microsoft.com/en-us/windows/win32/termserv/consoles-vs-terminals), [multi-session FAQ](https://learn.microsoft.com/en-us/azure/virtual-desktop/windows-multisession-faq) | Suitable when that infrastructure already exists; unnecessary infrastructure for one local assistant. |

`SendInput` injects into keyboard/mouse streams and has no desktop-target parameter. `SetCursorPos` explicitly requires the caller's desktop to be the input desktop. Accordingly, creating a second hidden Win32 desktop does not give the current pixel backend an independent pointer. UIA/provider actions can be useful without physical input, but support must be proved per application. Microsoft's separate PiP virtual-desktop mode is a practical example: it supports selector-oriented work but excludes physical mouse/keyboard, screenshots and image actions. This is distinct from Task View and from its child-session mode. [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput), [SetCursorPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setcursorpos), [PiP modes](https://learn.microsoft.com/en-us/power-automate/desktop-flows/run-desktop-flows-pip)

## Child sessions: the most interesting non-VM option

The Win32 API documents a special loopback RDP session tied to the existing user, available since Windows 8/Server 2012. A system permits one active, connected child session. Creation uses the RDP ActiveX control with `ConnectToChildSession=true`, after enabling child sessions; `WTSGetChildSessionId` identifies it. It ends when its parent session ends, cannot be locked, and has no screen saver. These are documented APIs, not a patch to bypass normal RDP limits. [Child sessions](https://learn.microsoft.com/en-us/windows/win32/termserv/child-sessions), [enablement](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsenablechildsessions), [session identifier](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsgetchildsessionid)

Power Automate documents simultaneous main-desktop work and child-session physical UI automation. Its product requires Pro/Enterprise Windows or supported Server editions, administrator enablement, separate browser data directories, and has application conflicts (including Office in both sessions), shared clipboard, and authentication caveats. These establish feasibility, not compatibility of arbitrary cctl applications. [PiP documentation](https://learn.microsoft.com/en-us/power-automate/desktop-flows/run-desktop-flows-pip)

**Inference:** a separate companion could host that connection in an optional viewer and launch arbitrary workloads inside the child, including cctl's daemon. Same-user sessions still share user files/profile resources; this is workspace/input separation, not a VM-like security boundary. Keep the connection alive until measured otherwise. Generic RDP automation has documented minimized-window failures, so hidden/minimized/disconnected operation is an explicit experiment, not a promised feature. [Microsoft RDP automation troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/power-platform/power-automate/desktop-flows/ui-automation/uipi-issues)

Existing first-party project documentation is worth examining before building: MIT [ParaDesk](https://github.com/sinpoce/ParaDesk) describes exactly this child-session viewer/launcher shape, including JSON status, CLI start/detach, commands after sign-in, audio mute, and clipboard policies. Its setup changes RDP, firewall and credential-delegation settings. MIT [childstream](https://github.com/mattxslv/childstream) is a smaller streaming proof of concept; [MsRdpEx](https://github.com/Devolutions/MsRdpEx) exposes the child-session property. These were documentation-reviewed only, not installed or vetted as dependencies. No official Microsoft launcher sample was located in the bounded search.

## Audio is a separate requirement

Windows endpoint loopback can mix audio from multiple Terminal Services sessions; RDP can instead expose session-specific audio devices. Being in a different user session alone therefore does not prove audio isolation. [WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)

RDP exposes playback redirection modes, including no playback, and device-selection properties for playback and microphone capture. Whether disabled playback preserves a capturable render stream is **unverified**. [Audio mode](https://learn.microsoft.com/en-us/windows/win32/termserv/imsrdpclientsecuredsettings-autoredirectionmode), [extended settings](https://learn.microsoft.com/en-us/windows/win32/termserv/imsrdpextendedsettings-property)

Microsoft's process-tree loopback sample captures selected processes independently of the audio endpoint (build 20348+). That could exclude the human's media from agent observations; it does not itself silence the agent's speakers. A silent render endpoint plus capture, or capture before suppressed client playback, needs testing. [Application loopback sample](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/)

## VM alternatives

Windows Sandbox is already a lightweight VM with a separate kernel. It ships in supported Pro/Enterprise/Education editions and discards its internal state on closing. Configuration supports startup commands and mapped folders, making reproducible short jobs plausible. Its `AudioInput` setting controls microphone sharing, not speaker output. [Sandbox overview](https://learn.microsoft.com/en-au/windows/security/application-security/application-isolation/windows-sandbox/), [configuration](https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file)

A persistent Hyper-V guest is a better candidate for retained applications, login state, and longer tasks. VMConnect enhanced sessions can redirect audio, clipboard, and other host resources; isolation still requires intentional resource routing. The daemon should act inside the guest, with the viewer optional. [Hyper-V local resources](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/use-local-resources-virtual-machine-connection)

## Candidate validation for this project

No implementation is proposed as already working. The current daemon proxy endpoint is per-user (`src/cctl/daemon.py`, `cctl.port`), pointer movement uses `SetCursorPos` (`cua_input.py`), clips use `gdigrab`, and audio uses the default speaker's WASAPI loopback (`media.py`). A same-user child-session experiment must first select endpoints per session and verify the upstream Cua process/pipe is session-specific.

Acceptance should then cover:

1. Human typing/mouse motion concurrently with agent clicks, typing, drag, modal dialogs, screenshots, UIA, and browser actions; verify neither receives the other's input.
2. Visible, obscured, minimized, disconnected/reconnected viewer, parent lock/unlock and logoff. Report unsupported states explicitly.
3. Human and agent playing distinct audio simultaneously: no agent sound at the human's speakers, successful agent capture/transcription, and no human sound in that capture. Include clipboard and browser-profile collision checks.
4. Two harnesses using the same cctl contract, plus orderly shutdown without touching the parent desktop.

**Recommendation:** if the user later authorizes implementation, evaluate existing child-session launchers as a provider for a separate companion; retain VM operation as the compatibility fallback. Keep session lifecycle, viewer and audio routing out of cctl's tool surface. Do not spend the first experiment on Task View, extra monitors, hidden Win32 desktops, or unsupported RDP concurrency patches.
