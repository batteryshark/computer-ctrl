# Setup and harness integration

Start with the [README](../README.md) to select a target and configure private
state/cache and an allowlisted environment. Registering the command in a harness
enables live tools; obtain the operator's approval before connecting.

## Native dependencies

Host Linux uses Cua Driver 0.34.0, an unlocked X11 desktop and xdotool; ffmpeg
supports clips and PulseAudio capture. Host macOS needs CuaDriver.app under
`/Applications`, accessibility/screen grants and a usable display. Host Windows
needs Cua's installed executable and an interactive session; SSH control starts
a session-resident controller with a scheduled task. Configure explicit executable
paths rather than assuming a globally installed editable cctl is the reviewed one.
Do not disable locks or grant permissions automatically.

Optional macOS audio uses `macos/build-audio-helper.sh`. It requires Swift/Xcode
command line tooling, Python 3.11+, ScreenCaptureKit, AVFoundation, CoreMedia and codesign.
Before running, set `CCTL_AUDIO_APP` to an absolute, new operator-approved app
destination and optionally `CCTL_AUDIO_SIGN` to an explicitly selected signing
identity (default ad-hoc). Both the app destination and `macos/build` must be new;
existing files/directories are refused, not removed. Raw empty, `.` and `..`
components and all existing symlink ancestors (including dangling links) are
refused before directory creation or compilation. Use direct absolute paths
(spaces are supported), with operator-controlled parents. Fresh directories are
reserved exclusively, but these static checks are not race-hardened against
concurrent ancestor replacement and are not an OS sandbox. A failed build can
leave partial new directories; review them manually, never delete existing data
as a setup shortcut. This script writes a local build and installs/signs the
helper; it is not an offline validation step.

The host macOS runtime first checks the executable under `CCTL_AUDIO_APP`,
defaulting to `$HOME/Applications/cctl-audio.app`, then passes that app path to
LaunchServices. A custom build destination must also be explicitly carried as
`CCTL_AUDIO_APP` into the reviewed controller environment; discoverability alone
is not enough. Keep the environment stripped and allowlisted, adding only that
approved path for separately approved host audio setup. Do not inherit
`CCTL_HOST` or the ambient environment, and do not add host audio to the isolated
launch example: this helper does not enable audio in unsupported isolated mode.
Grant Screen & System Audio Recording, and Microphone
only for approved mic capture. System audio requires macOS 14+, mic capture 15+.
Rebuilding ad-hoc signatures may reset grants. Input names must come from the
operator's approved target, never a guessed device. No audio binary/media ships.

Isolated mode instead uses a separately installed compatible QuietWing CLI with
schema/protocol version 1. See [sessions](../docs/isolated-sessions.md). Nothing
here provisions a VM, guest account, authenticated Windows child or Linux display.

## Harness command

Configure your harness to invoke the exact isolated MCP launch shape in the
README, including `env -i`, the private config and `--session demo`.
The tool catalog depends on the chosen provider. Shell-only callers can use the
same prefix for CLI verbs and inspect the returned local artifact paths. Tool
approval and native permissions remain required; never disable harness safeguards
as a setup shortcut.

The POSIX Claude plugin `.mcp.json` is deliberately **non-runnable until edited**:
it uses absolute placeholder paths, a stripped environment and explicit isolated
target. Review every replacement before loading it. Its `skills` symlink points
to the included root skills, not an external install. Other clients can install
the skill according to their current local documentation. No global config or
skill destination is written here.

For other MCP clients, register the executable and argument array using the
client's current documentation. The generic interface is stdio MCP; this
repository doesn't supply a Pi extension or an OpenCode-specific service.
Shell-capable clients can use CLI tools and load the skill through their own
skill mechanism. Media support depends on the client and model; clips have contact
sheets and audio can include transcripts for clients that need text.

## SSH is not isolation

The CLI retains `--host` and supports explicit remote executable/SSH arguments
in a private `hosts` table. It needs reviewed cctl installations on both ends;
the session/config resolves on the remote machine. `--host` alone can control
that machine's real desktop. Remote artifacts are copied back with SSH/scp.
The caller's private config/environment is not automatically applied remotely.
Arrange a separately reviewed remote config, allowlisted environment and disposable
target before use; no real hostname, key or remote-session example is supplied.
Windows controller/task lifetime and inherited environment need native validation.

## Host configuration

Settings default to `~/.config/cctl/config.toml`; `CCTL_CONFIG` selects a dedicated
file. Set `profile = "personal"`, private `state_dir` and `cache_dir`, and the exact
`cua_bin` path for your approved host installation. An empty session selects host
control. `CCTL_HOST` and `CCTL_SESSION` can override the target, so remove inherited
values when constructing the launch environment. The supported environment
overrides are listed in [config.py](../src/cctl/config.py).

`CCTL_STATE_DIR` and `CCTL_CACHE_DIR` aren't supported overrides, and XDG variables
alone don't move cctl's default paths. Host CLI commands can start a persistent
controller automatically. On Windows, controller startup uses a one-shot Limited
scheduled task in the interactive session. Only an explicitly approved host
configuration should use a launch command without `--session`.

Source, native helper and third-party rights are described in
[RIGHTS](../RIGHTS.md). Test drivers and build instructions are covered in
[development](../docs/development.md).
