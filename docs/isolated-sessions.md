# Optional isolated desktops

[QuietWing](https://github.com/batteryshark/quietwing) is a separate companion
owning OS-session lifecycle, native input and capture. cctl uses its local CLI
schema/protocol version 1. The source docs identify the 0.4.x interface (bounded
Windows key holds require a worker advertising `key_hold`, introduced in 0.4.2).

**Without `--session`, host desktop control remains the default** unless config
`session` or `CCTL_SESSION` selects an isolated target. `--host` is just SSH.
Explicitly selecting an unknown session fails with no host fallback. Use the
[README's private config and stripped environment](../README.md) for all calls;
never inherit host/session/driver overrides from an ordinary user environment.
Obtain approval for a disposable target first. Names below are synthetic and
must not be interpreted as discovered or approved real sessions.

## Configuration

```toml
profile = "personal"
state_dir = "/REPLACE_WITH_PRIVATE_SHORT_ROOT/s"
cache_dir = "/REPLACE_WITH_PRIVATE_SHORT_ROOT/c"
cua_bin = "/REPLACE_WITH_UNUSED_HOST_DRIVER"
[sessions.disposable-demo]
command = ["/REPLACE_WITH_REVIEWED_COMPANION/bin/quietwing"]
id = "approved-disposable-demo"
acquire = "start"
```

The cctl session name and companion ID have distinct roles. Commands and
`acquire_args` are literal argument arrays, not shell strings. Linux/macOS use
`start`; Windows uses `attach` to an existing authenticated child with connected,
unminimized viewer (it may be hidden). Windows-specific alternative table:

```toml
[sessions.disposable-windows-demo]
command = ['C:\REPLACE_WITH_REVIEWED_COMPANION\quietwing.exe']
id = "approved-disposable-child"
acquire = "attach"
acquire_args = ["--hide-viewer"]
[sessions.disposable-windows-demo.env]
DESKHELPER_PARADESK_DATA = 'C:\REPLACE_WITH_PRIVATE_CHILD_DATA'
```

Adapter environment names intentionally retain `DESKHELPER_*` compatibility.
Only allowlist variables needed for the approved companion; its subprocess
inherits the controller environment plus the explicit session env table.
Linux needs Xvfb/X11/PulseAudio tooling. macOS needs an explicitly provisioned
Apple Silicon VM. No wheel install alone provides these environments, logs in,
changes RDP/credential policy or authorizes capture.

## Lifecycle and identity

With the README launch prefix, replace `mcp` by `session status`, `session start`,
`screenshot`, or `session stop`. Always retain the configured `--session` name
(`demo` in the root README; `disposable-demo` in this guide's config).
Doctor/status query the companion; ordinary capture/input can automatically
acquire the configured target. Normal CLI/MCP use can start a persistent controller
and Windows can register a one-shot Limited task; neither is an offline operation.

Every native operation carries the pinned generation; replacement, loss and stale
frames fail closed. `session status` does not rebind. Explicit `session start`
can rebind and invalidates old frames. Explicit stop blocks automatic reacquisition
in that controller; repeated stop must not destroy a replacement. Closing an MCP
connection is not stop. Mac stop saves the guest, Windows releases owned workers/
apps but preserves the external authenticated child, Linux releases its owned
session. Save work before cleanup. Companion platform/TTL behavior is a separate
deployment responsibility; no unlimited lifetime or automatic rollback is promised.

Keep Unix cache paths short for the appended `sessions/<hash>/cctl.sock` socket.
Target/config identity gives separate state/cache/artifacts and browser profiles;
XDG variables alone do not change the base cctl paths. Arbitrary apps or shell
wrappers can still have global/single-instance behavior. This is not a general
filesystem sandbox or protection against a malicious companion.

## Capability limits

- Screenshot/zoom capture the isolated desktop or region, not host windows.
- Click supports a single unmodified pixel click; move is pixel-based.
- Drag supports `from`, `to`, `frame` and left/middle/right `button` only when
  the worker advertises `pointer_drag` (development macOS VM owners). Both points
  map through the same screenshot/zoom frame as click. One bounded native request
  presses, interpolates and releases; the response must confirm release. There is
  no persistent button-down state. Save/stop the guest, install/build updated
  QuietWing, resume and explicitly rebind to replace an older owner. Restart an
  existing cctl controller/MCP process to load adapter changes. No host fallback
  or replay on an unknown outcome. Scroll is still unavailable.
  CLI example with your approved target/environment prefix:
  `drag --from '[120,80]' --to '[240,160]' --frame FRAME --then screenshot`.
  Substitute points from the fresh image; these are syntax examples, not targets.
- `type_text` supports focused-field `mode=auto`, no element tokens or `set_value`.
  Text is passed literally to the provider; Unicode behavior is provider-native,
  guest clipboard may change and the result is not read-back verified.
- Key taps target guest focus. `hold_ms` must be integer 1–5000, `repeat=1`, with
  `key_hold: true`. The reply must confirm duration and release. Direct host holds
  and old workers refuse; there is no silent tap fallback. Save work and explicitly
  reattach an upgraded worker before use. Unknown release/outcome means inspect,
  not replay.
- Apps supports launch by executable/app name and literal argv, not list/quit/URLs.
  Use only an operator-approved disposable app. macOS simple names use guest
  `/usr/bin/open -a`. Known Windows browsers receive target-private profiles;
  profile override arguments are rejected.
- Batch executes supported actions in order. Wait supports pixel stability only.
  OCR reads an already captured isolated frame and can load OCR models.

Accessibility/observe, window management, browser/CDP, shell-output `run`, clipboard
tools, audio/video, scroll, grounding and delegate are unavailable. MCP omits
unsupported tools and CLI rejects them explicitly, without host fallback. This
does not remove host-mode features. Observe/action pipelines intended for host
accessibility do not apply to this adapter.

Timeouts may leave mutations in flight. Do not infer completion from model text,
replay unknown input, or reuse old frames. Verify actual saved synthetic content,
fresh images and exact session identity in a separately approved native test.
Viewer setup and any remote preview are companion operations requiring their own
approval. See [QuietWing's viewer guide](https://github.com/batteryshark/quietwing/blob/main/docs/viewer.md).
