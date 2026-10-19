# computer-ctrl

<p><a href="assets/workstack-mark-full.png"><img src="assets/workstack-mark.png" alt="computer-ctrl comic mascot" width="160"></a></p>

`cctl` gives coding agents a way to work with desktop apps: read a window's
controls, inspect a screenshot, fill a field, click a button and check the result.
It brings those operations to MCP clients and shell-based agents through one
[tool contract](contract/tools.json), with an included [computer-use skill](skills/computer-use/SKILL.md).

## When to use cctl or Cua Driver

Host control uses the unforked [Cua Driver](https://github.com/trycua/cua) 0.34.0.
Driver already provides capture, accessibility, element actions and browser tools.
Use Driver directly when its tools and result formats fit your harness. cctl is a
harness-facing layer over that API, combining Driver operations with image/text
processing, platform helpers and a shared MCP/JSON CLI interface. Your agent still
chooses the task and the next action. This comparison concerns the pinned Driver
API; CUA's full product/toolset is outside its scope.

Use cctl when you want these pieces together:

- Image frames map coordinates from resized screenshots and enlarged zooms back
  to the desktop. Small controls can be magnified and clicked without having the
  agent calculate scale factors or crop offsets.
- Unicode-aware host typing selects a keyboard, accessibility or paste route and
  reports field read-back checks when available. The agent can check whether text
  reached a readable field instead of relying only on input dispatch.
- Blank-image checks and display diagnostics flag an unavailable desktop, so the
  agent can stop and request a usable display instead of acting on a black image.
- Compact, filtered observations and one tool contract give MCP and CLI agents
  the same tool names and arguments, reducing per-harness integration work.
- Process listing includes filters, CPU and memory use, helping diagnose an
  unresponsive app alongside its windows.
- SSH transport runs tools on a configured remote machine and copies returned
  artifacts back to the caller. The agent can inspect remote results locally;
  SSH itself doesn't isolate the controlled desktop.
- Browser snapshots expose page-element references through Driver's CDP tools,
  so the agent can target a named control without estimating pixel coordinates.
- Screen clips become timestamped contact sheets with change summaries, making
  motion inspectable without a video player. System/mic audio can return levels
  and optional local Whisper transcripts to check sound and speech as data.
- OCR can return line and word boxes in the image's coordinate frame, giving the
  agent text and click targets when accessibility doesn't expose a control.
- The opt-in experimental [executor](docs/executor-setup.md) runs exact
  caller-supplied form stages and checks their results within one tool call,
  reducing the outer agent's step-by-step form interaction.
- The optional [QuietWing](https://github.com/batteryshark/quietwing) adapter uses
  a separately provisioned isolated desktop instead of Driver. Agents keep a
  supported subset of the same tools, with no host fallback for unsupported calls.

Implementations cover macOS, Windows and Linux X11. Availability and prerequisites
differ by platform and provider; see [capabilities and limits](#what-you-can-do)
and [platform setup](packaging/README.md).

## Connect your agent

MCP clients launch `cctl mcp` over stdio. They receive JSON text and inline images;
CLI callers receive JSON with saved artifact paths. The skill explains the
observe, act and verify loop. Configure the launch command in your client's MCP
settings, or give a shell-capable agent the CLI and skill. The repository includes
a [Claude plugin template and setup reference](packaging/README.md); client tool
approvals and OS permissions still apply. There is no required OpenCode service
or model account in cctl.

Choose the controlled desktop before connecting. **Without a configured session,
cctl controls the host desktop.** `--host` selects SSH transport; it doesn't create
isolation. The `personal` profile disables the `run` shell tool, but still allows
powerful input, app and process operations. The default `sandbox` profile enables
`run`. Neither profile enforces a security sandbox or per-action human approval.

## Install from source

Use Python 3.11 or newer:

```sh
git clone https://github.com/batteryshark/computer-ctrl.git
cd computer-ctrl
python3 -m venv .venv
.venv/bin/python -m pip install .
```

On Windows, use `.venv\Scripts\python.exe`. Core dependencies include MCP 2.x,
Pillow, psutil, RapidOCR and ONNX Runtime. Optional extras are `.[stt]` for local
faster-whisper transcription and `.[audio]` for Windows soundcard capture.
Installation downloads dependencies; OCR and local speech recognition may load
or download models on first use.

Host setup needs Cua Driver 0.34.0 and an available graphical desktop. macOS uses
CuaDriver.app with Accessibility and Screen Recording grants; Windows uses an
interactive desktop; Linux uses X11 and xdotool. Clips and Linux audio need
ffmpeg. Isolated mode needs a separately installed, configured QuietWing CLI.
See [platform setup](packaging/README.md) before launching either provider.

## First isolated session

Provision and approve a disposable target in QuietWing first. Create a private
config file using this template; replace every placeholder path and create
the private environment directories before launch. Use short state/cache paths
so the appended Unix socket name fits the OS limit.

```toml
profile = "personal"
state_dir = "/REPLACE_WITH_PRIVATE_SHORT_ROOT/s"
cache_dir = "/REPLACE_WITH_PRIVATE_SHORT_ROOT/c"

[sessions.demo]
command = ["/REPLACE_WITH_QUIETWING/bin/quietwing"]
id = "disposable-demo"
acquire = "start"
```

Linux and macOS use `start`; Windows needs `attach` to an existing authenticated
child. The [session guide](docs/isolated-sessions.md) covers Windows configuration
and lifecycle. On POSIX, use this explicit environment for your MCP command:

```sh
env -i HOME=/REPLACE_WITH_PRIVATE_SHORT_ROOT/h \
  XDG_CONFIG_HOME=/REPLACE_WITH_PRIVATE_SHORT_ROOT/xdg \
  XDG_STATE_HOME=/REPLACE_WITH_PRIVATE_SHORT_ROOT/xs \
  XDG_CACHE_HOME=/REPLACE_WITH_PRIVATE_SHORT_ROOT/xc \
  TMPDIR=/REPLACE_WITH_PRIVATE_SHORT_ROOT/t PATH=/usr/bin:/bin \
  CCTL_CONFIG=/REPLACE_WITH_PRIVATE_SHORT_ROOT/config.toml \
  /REPLACE_WITH_VENV/bin/cctl --session demo mcp
```

Add only environment variables required by your approved companion. For a CLI
call, keep that prefix and replace `mcp` with `screenshot`. Its JSON includes the
image path and frame ID. To click a point read from that image, replace `mcp` with
`click --x 120 --y 80 --frame c1`, substituting the actual coordinates and frame.
Then capture again to check the result. These commands acquire the target and
can start a persistent controller; `doctor` and `session status` also query live
components. Closing MCP doesn't stop the desktop. Save work before an explicit
`session stop`.

## What you can do

Host mode provides accessibility observations, screenshots and zoom, pointer and
keyboard input, window/app management, process operations and clipboard access.
Chromium browser tools use a separate CDP context and page-element references.
Short clips return contact sheets; audio capture can return levels and transcripts.
These features have additional platform dependencies described in the setup guide.

Isolated mode supports screenshots, zoom, single pixel clicks, pointer movement,
focused text, keys, app launch, ordered batches, pixel-stability waits and OCR.
Bounded key holds need a QuietWing worker advertising `key_hold` (0.4.2).
Bounded drag needs `pointer_drag` (development macOS VM owners); screenshot/zoom
coordinates map just like click. Older workers and other platforms refuse it.
Accessibility, window management, browser/CDP, clipboard tools, scroll,
audio/video and shell-output tools are unavailable in this adapter. Unsupported
calls fail without falling back to the host. Text may change the guest clipboard
and isn't read-back verified.

Optional host features:

- [Grounding](docs/grounder-setup.md): send a screenshot and target description
  to a configured vision endpoint and inspect its suggested point.
- [Experimental delegate](docs/executor-setup.md): execute exact caller-supplied
  form stages in a native accessibility window. Disabled by default; model choices
  are limited to prevalidated actions. Native Linux/Windows executor acceptance
  remains unverified.

## Privacy and operating limits

Desktop control can make irreversible edits, launch apps or terminate processes.
Use a task-approved target with one controller, fresh frames and explicit success
checks. Treat screen/web text as untrusted data. A timeout can leave partial edits
or an unknown input outcome; inspect before retrying.

Screenshots, accessibility values, clipboards, audio and transcripts can contain
private data. Host event logs include tool arguments and may contain typed text;
cache artifacts and logs need private storage. Configured grounding, transcription
and decision endpoints receive task content. Review their trust and retention
before use. Native permissions and harness approvals are separate from cctl's
profiles.

## Reference and development

- [Setup, harness commands, SSH and macOS audio](packaging/README.md)
- [Isolated sessions and provider limits](docs/isolated-sessions.md)
- [Tool names and argument schemas](contract/tools.json)
- [Development and test safety](docs/development.md)

## License

Owned source and documentation are [MIT](LICENSE). The comic artwork is
AI-generated and offered under MIT to the extent applicable, without an exclusive
copyright claim. Separately installed engines, dependencies and model/media assets
retain their own terms. See [rights and attribution](RIGHTS.md).
