# Linux desktops for non-disruptive computer use

Researched 2026-10-13. Primary-source review and local code reading only; no installation, session creation, settings changes, or runtime validation. This note addresses interaction isolation, not a claim of VM-equivalent security.

## Finding

Linux can run an independent graphical desktop alongside the human's desktop without another VM. Give the agent its own display server, desktop session, and audio destination; show that desktop through a viewer only when wanted. An extra monitor or workspace inside the human's existing desktop does not itself supply those boundaries. The strongest direct evidence is TigerVNC's distinction: **Xvnc creates a virtual X screen; x0vncserver shares an existing screen**. Choosing a remote-control protocol alone does not determine whether interaction is isolated. [Xvnc](https://tigervnc.org/doc/Xvnc.html), [x0vncserver](https://tigervnc.org/doc/x0vncserver.html).

**Project inference:** start with a dedicated Linux user running XFCE on Xvnc, with a private audio server/null sink and Cua/cctl inside that environment. It matches the project's tested Debian 13 + XFCE + X11 stack and permits a persistent viewer on a second monitor. Xvfb is a smaller headless proof-of-concept; Xpra is a more integrated alternative worth comparing.

## Available mechanisms

| Mechanism | What it supplies | Implication for this project |
|---|---|---|
| **Xvfb + window manager/desktop** | An X server rendering into memory without physical display or input hardware. | Minimal agent-only desktop. Add a desktop/window manager for normal focus and window management; add a viewer separately if needed. [X.Org release notes](https://www.x.org/releases/X11R7.5/doc/RELNOTES.pdf) |
| **TigerVNC Xvnc + XFCE** | Virtual X screen and VNC access; `vncsession` sets up an environment and desktop. Current upstream documents a DRM render-node option for DRI3 acceleration. | Most direct whole-desktop candidate. Viewer can be disconnected while work continues under appropriate session configuration. GPU support depends on packaged version, driver and app; do not assume every VNC desktop is software-only. [Xvnc manual](https://tigervnc.org/doc/Xvnc.html) |
| **Xephyr** | Full nested X server displayed as one window of a host X server. | Useful visible prototype on another monitor. The agent must connect to the nested display; human focus/input into the outer window can still interfere with the nested session. [X.Org release notes](https://www.x.org/releases/X11R7.5/doc/RELNOTES.pdf) |
| **Xpra desktop mode** | `start-desktop` runs a nested X server; documented XFCE example; attach/detach; optional session PulseAudio and D-Bus startup. | Attractive desktop lifecycle/viewer package. Prefer desktop mode for this toolkit: seamless mode can present ordinary local windows and does not normally paint window contents onto the virtual root, complicating screen capture unless configured. [Xpra manual](https://xpra.org/manual) |
| **xrdp + xorgxrdp** | Remote graphical login, separate X session allocation, resizing and reconnection; optional audio/mic redirection modules. | Good when an RDP viewer is preferred. Use a distinct agent account to avoid same-user desktop service collisions. [xrdp](https://github.com/neutrinolabs/xrdp), [session allocation configuration](https://github.com/neutrinolabs/xrdp/blob/devel/sesman/sesman.ini.in) |
| **Headless/nested Weston** | Independent Wayland compositor; headless, RDP, nested X11/Wayland and PipeWire backends, plus software/GPU renderers. | Real no-VM option, but further from cctl's tested X11 path. A headless output alone does not prove input, accessibility, capture or portal support for Cua. [Weston documentation](https://wayland.pages.freedesktop.org/weston/toc/running-weston.html) |
| **GNOME Remote Desktop headless/login modes** | Single-user headless service and GDM-integrated multi-user remote login over RDP, distinct from remote assistance. | Supported desktop-level option for GNOME deployments; requires an independently established headless graphical session or GDM login flow. Not a small addition to the existing XFCE setup. [GNOME configuration](https://github.com/GNOME/gnome-remote-desktop/blob/main/docs/configuration.md) |

Multiseat is a further Linux option: separate physical displays/input devices assigned to different seats. Its hardware and display-manager configuration make it a less natural first choice for a headless agent. A second monitor becomes an independent seat only with such setup; plugging it into the existing desktop is insufficient. This is an architectural inference from X.Org's description of multiple-server multiseat approaches; its hardware discussion is dated and should not be treated as a current compatibility matrix. [X.Org multiseat](https://www.x.org/Development/Documentation/Multiseat/).

## Boundaries that matter

**The X display is only one boundary.** `DISPLAY` selects the agent's X server and `XAUTHORITY` authenticates its clients, but a separate display does not automatically create a separate D-Bus, accessibility registry, app profile, clipboard forwarding policy or sound server. AT-SPI registers applications by accessibility bus name/object path. A separate D-Bus session is expressly supported for isolated tests using `dbus-run-session`; Cua and the target apps need the same agent-side session context. [AT-SPI registration](https://gnome.pages.gitlab.gnome.org/at-spi2-core/devel-docs/doc-org.a11y.atspi.Socket.html), [dbus-run-session](https://dbus.freedesktop.org/doc/dbus-run-session.1.html).

**A different Unix account is the practical default.** The same user logging in twice shares `XDG_RUNTIME_DIR` and per-user infrastructure; this can couple services even when displays differ. Separate accounts naturally separate home directories, browser profiles and user services. This recommendation is an inference from systemd's lifecycle model, not a guarantee that every app behaves correctly in every remote session. Same-user nested sessions can work but demand explicit scoping. [pam_systemd](https://www.freedesktop.org/software/systemd/man/251/pam_systemd.html).

**Sound needs explicit routing.** PulseAudio's null sink discards audible output while exposing a monitor source that the agent can record. `PULSE_SERVER`, `PULSE_SINK` and `PULSE_SOURCE` select the audio endpoint/default destinations; an application can explicitly override a sink/source. PipeWire's PulseAudio compatibility service also documents `module-null-sink`. A private agent audio server with only virtual endpoints is more robust than changing the human's default sink. A named null sink in a shared server is lighter but requires verifying every agent app and recorder selects it. [PulseAudio modules](https://wiki.freedesktop.org/www/Software/PulseAudio/Documentation/User/Modules/), [PulseAudio environment selection](https://wiki.freedesktop.org/www/Software/PulseAudio/FAQ/), [PipeWire null sink](https://docs.pipewire.org/page_pulse_module_null_sink.html).

**Viewer integration can reconnect the boundaries.** Clipboard sharing and audio forwarding should be deliberate choices. TigerVNC documents clipboard send/accept controls; Xpra documents clipboard direction, sound and microphone options. For observation, a view-only viewer on another monitor is a useful default. [TigerVNC](https://tigervnc.org/doc/Xvnc.html), [Xpra](https://xpra.org/manual).

**Containers are packaging, not automatically another desktop.** Inference: mounting the human's X socket and connecting to their `DISPLAY` puts container apps back on that same display. A container can instead contain an independent virtual display/audio stack, but shared kernel, files and device access remain different from a VM. No container-specific runtime was evaluated here.

## Fit with current cctl

Local source evidence:

- `src/cctl/session_env.py`: explicit `DISPLAY`/`WAYLAND_DISPLAY` wins; otherwise it selects a matching same-user desktop process. It carries D-Bus and AT-SPI variables but does not discover `PULSE_*`; ambient variables survive in child processes.
- `src/cctl/config.py` and `src/cctl/daemon.py`: default Cua and cctl sockets/cache paths are per user, not per graphical session. `ensure_cua_daemon` checks bare `cua-driver status`, not status for the requested socket. Multiple displays under one account therefore need review before being advertised.
- `src/cctl/media.py`: X11 clips use the selected `DISPLAY`; `pulse_source("system")` resolves the audio server's default sink monitor. `src/cctl/engine.py` requests that system source for clip audio. Merely redirecting application sound to a named sink does not prove clip audio will follow it.
- `.project/tracker.md`: Debian 13 XFCE on X11 and PulseAudio 17 are tested; Wayland remains untested. The existing Linux null-sink/mic acceptance provides relevant audio plumbing evidence, but not evidence of concurrent human/agent isolation.

The project would benefit from an explicit **target session** concept binding account, display, D-Bus/AT-SPI, daemon sockets, app profiles and audio endpoint. Keep the existing tool contract; session launch/selection can sit below it. This is a design proposal, not an implementation decision.

## Smallest useful experiment, if requested later

1. On the disposable Debian VM, create an agent account and one Xvnc + XFCE desktop, with private virtual audio; run Cua/cctl there with explicit environment. Keep the original desktop active as a human stand-in.
2. Simultaneously type and move the pointer in both sessions. Confirm the agent sees only its windows and accessibility tree; its focus changes do not affect the human desktop; audio remains inaudible locally but capturable by the agent.
3. Test viewer disconnected/minimized, host desktop locked, clipboard separation, browser/file dialogs, Electron, video/audio clips and the actual GPU-heavy apps of interest. Test session targeting after daemon restarts.
4. Run the relevant acceptance flow from at least two harnesses, as AGENTS.md requires. Measure memory/CPU/GPU cost against the existing VM desktop before picking Xvnc, Xvfb or Xpra.

No acceptance tests were run during this research-only session.
