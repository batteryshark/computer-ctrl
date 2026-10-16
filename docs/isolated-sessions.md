# Optional isolated desktops

[QuietWing](https://github.com/batteryshark/quietwing) is an independent companion. It owns the OS session,
native input/capture transport and lifecycle. Computer-ctrl selects that session
through a versioned local CLI interface; it never falls back to the host desktop.
With no default session configured, omitting `--session` keeps existing host
control. A config-level `session` or `CCTL_SESSION` selects an isolated default;
use separate configs when switching between host and isolated work.

Install QuietWing 0.3.1 separately on the machine being controlled. Its sole command
is `quietwing`; computer-ctrl defaults to that executable when `command` is omitted.
There is no `deskhelper` alias. Update existing 0.2 target command arrays explicitly.
Native state/cache paths and `DESKHELPER_*` adapter environment names retain their
existing identities so saved guests and authenticated children remain usable.
Python 3.11+ is required. Native prerequisites remain platform-specific:
authenticated ParaDesk child on Windows, Xvfb/X11/PulseAudio tools on Linux, and
an explicitly provisioned Apple Silicon macOS VM. Installing the Python wheel
does not change host settings or provision a guest.

Add a named target to a private cctl config (or a separate file selected by
`CCTL_CONFIG`). Commands are argument arrays, never shell command strings:

```toml
[sessions.work]
command = ["/absolute/path/to/quietwing"]
id = "minimal"
acquire = "start"
```

Linux also uses `acquire = "start"`. To reuse an explicitly stopped Linux ID,
set `acquire_args = ["--replace-stopped"]`; the companion archives only a fully
cleaned prior instance. A running instance is adopted without recreation.
Windows uses an existing authenticated child:

```toml
[sessions.work]
command = ["C:\\absolute\\path\\quietwing.exe"]
id = "agent-work"
acquire = "attach"
acquire_args = ["--hide-viewer"]
[sessions.work.env]
DESKHELPER_PARADESK_DATA = "C:\\private\\paradesk-data"
```

The Windows viewer must stay connected and hidden. Minimize/detach is unsupported.
The companion never prompts for login or changes RDP/credential policies.

```sh
cctl --session work session start
cctl --session work doctor
cctl --session work apps --action launch --name TextEdit
cctl --session work screenshot
cctl --session work type_text --text 'Hello — café 日本語'
cctl --session work session status
cctl --session work session stop
```

Use an executable appropriate to the target for `apps`: for example `mousepad`
on Linux or `notepad.exe` on Windows. Arguments remain an array. On macOS, simple
application names use guest `/usr/bin/open -a`; to open an existing document use
`name=/usr/bin/open` and `args=["-a","TextEdit","/guest/path/document.txt"]`.
First ordinary control use acquires the configured session automatically.
Explicit stop prevents automatic reacquisition by that controller until
`session start`. Closing a CLI/MCP connection preserves the work session.

For MCP, configure the harness command as `cctl --session work mcp`. Remote use
is `cctl --host user@machine --session work mcp` (or a CLI tool command). The
session name/config resolves on the remote machine. Existing SSH transport is
reused; the companion exposes no network listener. The Windows cctl controller
uses a private, token-authenticated loopback endpoint, matching cctl's existing
Windows transport. A target-specific one-shot Limited scheduled task launches
it outside the SSH job; the task has no trigger and is removed after launch.

## Supported tools

| Tool | Isolated-session behavior |
| --- | --- |
| doctor | Read-only descriptor, capabilities and supported tools; does not acquire a session |
| apps | Launch by executable/app name and argv; no list/quit/default URL handler |
| screenshot, zoom | Whole isolated desktop or region; fresh capture and generation-bound frames |
| click, move | Pixel coordinates; single unmodified click only |
| type_text | Focused field, mode=auto; provider's native Unicode route; guest clipboard may change |
| key | Focused guest window; no window targeting |
| batch | Supported actions, ordered, with ordinary failure semantics |
| wait_for | Pixel stability only; no element/window predicates |
| ocr | Reads an already captured isolated image, with boxes in its frame |

Accessibility/observe, window management, browser/CDP tools, shell-output `run`,
clipboard tools, audio/video, scroll/drag, grounding and delegate are unavailable
in this adapter. Unsupported tools are omitted from MCP and fail explicitly
if called via CLI. This does not change their availability for host control.

Each configured target has distinct daemon state, artifacts and browser-profile
paths. Known Chromium/Firefox executables launched through `apps` on Windows
receive a private target profile; overriding that profile is rejected. Linux's
private HOME and Mac's separate guest account provide profile separation.
Arbitrary applications and explicit shell wrappers can have their own global
profile/single-instance behavior; they are not a filesystem security sandbox.

## Identity and recovery

Computer-ctrl pins the descriptor's generation. Every native operation sends
`--expect-generation` and the companion checks it before delivery. A replaced,
lost or stopped session cannot silently become an input target. Frames include
controller-run identity and generation; a fresh controller cannot accidentally
reuse an earlier `c1` frame.

`session status` reports current state without changing the pinned generation.
After a replacement, `requires_rebind` signals that `session start` is needed.
That explicit rebind discards old frames. Inspect errors before retrying a
timed-out mutation: completion may be unknown, and commands are never replayed
automatically.

Mac stop saves the guest and releases RAM; start restores it without login.
Windows stop removes owned workers/apps and preserves viewer visibility, retaining the
external authenticated child. Linux stop releases only its owned session.
Crashes and cold boots have different recovery requirements; consult the
companion's platform documentation rather than changing host login policies.

## Daily use and viewing

First ordinary control use acquires the configured target; status and doctor do
not start it. A clean Mac save/resume needs no new login. Windows requires an
existing signed-in, connected viewer; Linux creates or adopts its private display.
Closing MCP alone preserves the work instance, subject to the backend lifetime.

Ask the agent for a fresh screenshot, or run `cctl --session work screenshot`
and open its returned image path.

QuietWing's 0.4 development build adds a read-only preview window on Mac. Using the
same QuietWing environment configured for your isolated target, build it once
with `quietwing build --viewer`, then run `quietwing view --id minimal` while the
guest runs. Use the companion ID from configuration; it can differ from the
cctl session name. The preview opens without taking keyboard focus and never
forwards input. Close its window or use `quietwing view --id minimal --close`;
the guest and agent keep running. Viewing never resumes a saved guest or follows
a replacement generation. See the companion's
[viewer guide](https://github.com/batteryshark/quietwing/blob/45f59a5a40ec5e8db996579c1a029e335043a7f2/docs/viewer.md).
The published 0.3.1 release does not include this development feature.

Development 0.4.0.dev1 can also show an isolated Linux desktop in that Mac window
over existing SSH. Use matching QuietWing builds on both ends, then on Mac:

```sh
quietwing view --host user@linux-machine --id work \
  --remote-command /home/user/quietwing/venv/bin/quietwing
```

Add `--remote-state-root /absolute/private/state` when the Linux agent target
uses a custom state root. Use the same target options with `--status` or `--close`.
The preview never starts a desktop, extends Linux TTL, forwards input or follows
a replacement generation. A long agent action can temporarily pause capture;
only read-only capture retries against the pinned generation. See the tested
[Linux viewer guide](https://github.com/batteryshark/quietwing/blob/52063ff/docs/viewer.md)
and [PR #2](https://github.com/batteryshark/quietwing/pull/2). This development
feature is separate from the published 0.3.1 release.

Development 0.4.0.dev2 adds the same Mac window for an already attached Windows
child. Keep ParaDesk connected, hidden and unminimized, then on Mac:

```sh
quietwing view --host user@windows-machine --remote-platform windows --id work \
  --remote-command 'C:\private\venv\Scripts\quietwing.exe' \
  --remote-state-root 'C:\private\helper-state'
```

If the existing Windows SSH login uses a nondefault key, also pass
`--ssh-identity /absolute/path/to/existing/key`. Use the exact same target options
with `--status` or `--close`; those act on the Mac preview only. Viewing never
attaches, reconnects, reveals ParaDesk or forwards input/audio. Closing leaves
Windows work running, and frames do not reset its 30-minute worker inactivity
timer. Stop, lock, connection loss or generation replacement clears the image;
explicitly reopen after recovery. See the tested
[Windows viewer guide](https://github.com/batteryshark/quietwing/blob/1bc2107292aa7149b57649902447604f3d6d183a/docs/viewer.md#windows-over-ssh)
and [PR #3](https://github.com/batteryshark/quietwing/pull/3). This feature remains
separate from published 0.3.1; no computer-ctrl tool/configuration change is needed.

There is no unified takeover control. Linux has no local viewer window, and
Windows must keep its ParaDesk viewer connected and unminimized.

Linux defaults to a fixed 30-minute TTL from creation, even while active. A target
can set `acquire_args = ["--ttl", "14400", "--replace-stopped"]` for a bounded
four-hour desktop and safe reuse of a fully stopped ID. Windows closes owned apps
after 30 minutes without activity other than preview frames; this worker timeout is not configurable yet.
Mac has no automatic idle save/stop. Save documents before Windows/Linux cleanup.

## Acceptance status

The 141-test regression suite includes 23 isolated-provider cases covering exact
argv/text preservation, session
replacement refusal, frame invalidation, target path separation and unchanged
host-engine selection. Native Linux, Mac and Windows cctl workflows have passed
launch/input/capture/lifecycle tests, including live installed-wheel use on all
three platforms. Windows private-artifact ACL and
SSH-controller-lifetime fixes have passed native verification.
Real Codex and OpenCode ordinary-editor workflows passed on all three platforms.
Exact saved Unicode, successful native calls, fresh captures and host cursor/focus
metadata were verified independently. Native suites separately cover stale
rejection, reconnect/resume and owned cleanup. Model completion
messages do not count as proof: saved content, actual tool calls, fresh images,
session identity and host observations must be checked independently.

The reusable `acceptance/isolated_harness.py` runner accepts a configured MCP
command, prepared editor document, unique text marker and a fresh output directory.
It supports Codex, OpenCode and Claude; successful acceptance here used Codex and
OpenCode. OpenCode v1 uses `--opencode-mode pure`. The tested v2.0.23 needed
`--opencode-owned-server` with `--opencode-mode standalone`: this starts a private
loopback server, registers only the chosen isolated target, waits for its actual
tool catalog, and removes its owned server afterward. This workaround changes no
global harness configuration. Model/provider flags apply only to that run. See the
companion's `VALIDATION.md` and platform reports for repeatable preparation and
independent verification, including unsuccessful zero-tool attempts.

Windows follow-up on 2026-10-15 used the published QuietWing 0.3 wheel: native
lifecycle/reconnect checks and fresh actual Codex/OpenCode editor workflows passed.
Exact saved Unicode, tools, child identity, captures and cleanup were independently
verified; 1,849 parent samples had unchanged pointer/focus and a hidden connected
viewer. This closes the initial Windows live-acceptance deferral. The original
reported main-desktop obstruction remains unidentified. Version 0.3.0 restored
viewer visibility at stop; 0.3.1 preserves current visibility so a hidden viewer
stays hidden. That patch initially had static/simulated coverage. A later
2026-10-15 follow-up against the unchanged official 0.3.1 wheel passed native
input/capture/stop/crash/rollback and actual Codex/OpenCode ISE workflows, with
independently verified Unicode, tools, images and child identity; 1,708 parent
samples kept ParaDesk hidden/unminimized. The same signed-in child was retained.
This closes the 0.3.1 native deferral; release tags/assets were not replaced.

The Codex acceptance runner marks its isolated MCP server required and allows
60 seconds for startup. This waits for SSH/tool discovery before the first turn;
a successful model exit alone remains insufficient acceptance evidence.
