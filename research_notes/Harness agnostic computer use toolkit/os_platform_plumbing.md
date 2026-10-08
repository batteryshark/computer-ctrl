# OS Platform Plumbing for a Harness-Agnostic Computer-Use Toolkit (Windows, macOS, Linux X11/Wayland) — status as of 2026-10-07

Note on sourcing: "(background, unverified)" marks API facts I'm stating from prior knowledge without a fetched source in this session. The report writer should treat those as "likely correct but not re-verified." Everything else has an inline source. Many 2026 status claims come from GitHub issues/PRs and vendor pages, not official release notes. Treat them as indicative.

---

## Windows: capture, input, UIA, windows, audio, video, DPI

### Takeaway
Use Windows.Graphics.Capture (WGC) as the primary capture path, with DXGI Desktop Duplication as a fast full-monitor fallback and GDI BitBlt/PrintWindow as a last resort. WGC is multi-GPU-safe, can capture occluded/minimized windows, and on 20348+ the yellow border can be removed with user consent. Inject input with SendInput. It is silently blocked by UIPI for elevated targets and can't reach the secure desktop. Use UI Automation for the tree, WASAPI (endpoint loopback or process loopback on build 20348+) for audio, and ffmpeg ddagrab (on-GPU D3D11 frames) or WGC + Media Foundation for video. The process must declare Per-Monitor-v2 DPI awareness before touching any coordinates.

### Cited Findings
**Screen capture**
- WGC handles multi-GPU systems automatically, but DXGI Desktop Duplication requires the capturing process to run on the GPU driving the display (OBS moderator) — [OBS forum](https://obsproject.com/forum/threads/windows-graphics-capture-vs-dxgi-desktop-duplication.149320)
- WGC is built on DXGI internally. Desktop Duplication efficiently reports dirty and moved regions, which suits streaming, but one developer found it failed when no user was logged in. Desktop Duplication users must also handle releasing frames, processing dirty/move regions, rotation, and recreating duplication after display changes — [search synthesis of volcengine / MeshCentral#2003 / WgcSharp](https://github.com/Ylianst/MeshCentral/issues/2003); [WgcSharp NuGet](https://www.nuget.org/packages/WgcSharp)
- A WGC-based library (WgcSharp) advertises capturing any window by HWND, "including occluded, minimized, and DirectX/OpenGL game windows." Desktop Duplication can't see windows hidden behind others — [WgcSharp](https://www.nuget.org/packages/WgcSharp)
- `GraphicsCaptureSession.IsBorderRequired` controls the colored capture border. To disable it, the app must call `GraphicsCaptureAccess.RequestAccessAsync(GraphicsCaptureAccessKind.Borderless)`, which shows a user prompt, and must declare the `graphicsCaptureWithoutBorder` capability in its package manifest. If the user denies, setting false "will succeed, but the value will be ignored." If another app sets true on the same target, the border shows. Introduced in 10.0.20348.0 — [Microsoft Learn: IsBorderRequired](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession.isborderrequired)
- `IsCursorCaptureEnabled` toggles cursor inclusion. It was added in Windows 10 2004 (19041) — [Microsoft Learn: GraphicsCaptureSession](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession)
- OBS detects border-toggle support at runtime with `ApiInformation::IsPropertyPresent("Windows.Graphics.Capture.GraphicsCaptureSession","IsBorderRequired")` — [OBS winrt-capture.cpp mirror](https://git.tjdev.de/mirror/obs-studio/src/commit/ee144377dc50b5d9f1fdf0598cea56f7e34eab9b/libobs-winrt/winrt-capture.cpp)
- Rust crate `windows-capture` (NiiightmareXD) wraps the Graphics Capture API for Rust and Python. docs.rs shows 1.5.0, and the last push was ~Feb 2026 per a third-party tracker — [docs.rs windows-capture](https://docs.rs/windows-capture); [gittrend](https://gittrend.io/repo/NiiightmareXD/windows-capture)
- xcap 0.9.8 includes a `windows/wgc.rs` module, so it uses WGC on Windows — [docs.rs xcap wgc.rs](https://docs.rs/crate/xcap/0.9.8/source/src/windows/wgc.rs)

**Input**
- SendInput "is subject to UIPI. Applications are permitted to inject input only into applications that are at an equal or lesser integrity level." It "fails when it is blocked by UIPI. Note that neither GetLastError nor the return value will indicate the failure was caused by UIPI blocking." It also "does not reset the keyboard's current state," so already-pressed keys can interfere — [Microsoft Learn: SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
- Absolute mouse coordinates are normalized 0–65535. Without `MOUSEEVENTF_VIRTUALDESK` they map to the primary monitor, and with it they map to the whole virtual desktop (must be combined with `MOUSEEVENTF_ABSOLUTE`). Conversion formulas differ between implementations, such as .NET reference source versus Rabbit Remote Control, and a Moonlight bug was caused by a mismatch between the virtual-desktop flag and the scaling basis — [AutoIt MOUSEINPUT ref](https://www.autoitscript.com/autoit3/docs/libfunctions/$tagMOUSEINPUT.htm); [.NET Input.cs](https://referencesource.microsoft.com/UIAutomationClientsideProviders/MS/Internal/AutomationProxies/Input.cs.html); [moonlight-common-c#49](https://github.com/moonlight-stream/moonlight-common-c/issues/49)

**DPI**
- `DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2` adds per-top-level-window scaling and child DPI notifications. It is not available before Windows 10 1607. The legacy `dpiAware` manifest element can't request it, so you need `dpiAwareness` or `SetProcessDpiAwarenessContext` — [Microsoft Learn: DPI_AWARENESS_CONTEXT](https://learn.microsoft.com/en-us/windows/desktop/hidpi/dpi-awareness-context); [Setting default DPI awareness](https://learn.microsoft.com/en-us/windows/win32/hidpi/setting-the-default-dpi-awareness-for-a-process)
- Windows refuses `SetProcessDpiAwarenessContext` once awareness is already set by a manifest, an earlier call, or a compat override, so check the effective mode at runtime — [pixelcoords crate source](https://docs.rs/crate/pixelcoords/0.7.0/source/src/win.rs)
- In a DPI-unaware process, GetCursorPos returns logical (scaled) coordinates. Example: 1920×1080 at 125% reports ~1535×863 at the bottom-right corner. `GetPhysicalCursorPos` returns physical pixels — [Microsoft Learn: UIA and screen scaling](https://learn.microsoft.com/cs-cz/windows/win32/winauto/uiauto-screenscaling); [Microsoft Learn: GetPhysicalCursorPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getphysicalcursorpos); [fishc forum example](https://fishc.com.cn/archiver/tid-95046.html)

**Accessibility tree**
- Rust `uiautomation` crate (leexgone/uiautomation-rs) is "a wrapper for windows uiautomation." The last push was ~Mar 2, 2026 per a tracker, with 187 stars — [gittrend uiautomation-rs](https://gittrend.io/repo/leexgone/uiautomation-rs)

**Audio**
- Process loopback: `ActivateAudioInterfaceAsync` with `AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK` and `AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS` can include or exclude a target process tree (`PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE` / `..._EXCLUDE_...`). Minimum is Windows 10 build 20348. Microsoft ships an "Application Loopback API Capture Sample" — [Microsoft Learn: AUDIOCLIENT_ACTIVATION_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/audioclientactivationparams/ne-audioclientactivationparams-audioclient_activation_type); [PROCESS_LOOPBACK_MODE](https://learn.microsoft.com/en-us/windows/win32/api/audioclientactivationparams/ne-audioclientactivationparams-process_loopback_mode); [ActivateAudioInterfaceAsync](https://learn.microsoft.com/en-us/windows/desktop/api/mmdeviceapi/nf-mmdeviceapi-activateaudiointerfaceasync)

**Video**
- ffmpeg `ddagrab` (lavfi source, FFmpeg 5.1+) uses Desktop Duplication and "exclusively returns D3D11 Hardware Frames" for on-GPU encoding. Example: `ffmpeg -init_hw_device d3d11va -filter_complex ddagrab=0 -c:v h264_nvenc ...`. Software x264 needs `ddagrab=0,hwdownload,format=bgra`. The default is 30 fps — [FFmpeg wiki Capture/Desktop](https://trac.ffmpeg.org/wiki/Capture/Desktop); [ffmpeg-devel ddagrab patch](https://ffmpeg.org/pipermail/ffmpeg-devel/2022-July/298685.html)
- `gdigrab` (BitBlt) has been slow since Windows 8, when Aero could no longer be disabled. It can target a window by title, which ddagrab can't. On a secure-desktop (UAC) popup, gdigrab silently stops recording while ddagrab stops with an error — [doom9 forum](https://forum.doom9.org/archive/index.php/t-173985.html); [FFmpeg trac #9473 (Jun 2025)](https://ffmpeg.org/pipermail/ffmpeg-trac/2025-June/073881.html)
- A ddagrab bug when specifying an adapter ID on non-UWP builds was reportedly gone in 7.1.1 — [FFmpeg trac #10385](https://trac.ffmpeg.org/ticket/10385)

### Inferences
- Recommended Windows map:
  - **Screenshot (full, monitor, region):** WGC via `GraphicsCaptureItem` for a monitor (HMONITOR), then crop for regions. Fallback is DXGI Desktop Duplication. Last resort is GDI BitBlt for VMs/RDP where WGC/DDA may fail.
  - **Window screenshot:** WGC `CreateForWindow(HWND)`. Fallback is `PrintWindow(PW_RENDERFULLCONTENT)` (background, unverified).
  - **Input:** SendInput with `KEYEVENTF_UNICODE` for text and virtual keys or scancodes for combos (background, unverified for the flag specifics).
  - **Windows:** `EnumWindows`, `GetWindowText`, `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)` for true bounds, `SetWindowPos`, `SetForegroundWindow` (subject to foreground-lock rules) (background, unverified).
  - **A11y:** UIA via `IUIAutomation` (COM).
  - **Audio:** WASAPI loopback on the default render endpoint (`AUDCLNT_STREAMFLAGS_LOOPBACK`, background) plus process loopback on 20348+. Mic via a normal WASAPI capture endpoint.
  - **Video:** ffmpeg ddagrab plus a hardware encoder, or the WGC frame pool plus Media Foundation `IMFSinkWriter`.
- The silent UIPI failure means the toolkit must detect it itself: check the target's integrity level with `OpenProcessToken`/`GetTokenInformation(TokenIntegrityLevel)` (background) and report "target is elevated." The options are running the daemon elevated, or `uiAccess=true` in the manifest, which per prior knowledge requires an Authenticode-signed binary installed under Program Files (unverified this session).
- The secure desktop (UAC consent, Ctrl+Alt+Del, lock screen) can't be captured or driven from a user-session process. ffmpeg's behavior there confirms capture stops. The agent should treat a UAC prompt as "needs human."
- The WGC borderless consent flow needs a package-manifest capability. A plain unpackaged Win32 CLI/daemon may need packaging with identity (MSIX or sparse package) to get border-free capture. Otherwise users see the yellow border during capture.

### Gaps
- No controlled latency/throughput benchmark of WGC vs DDA vs BitBlt for single-shot screenshots (as opposed to streaming) was found.
- I did not verify the current `uiAccess` requirements or whether Chromium/Electron expose a full UIA tree by default in 2026 (versus requiring `--force-renderer-accessibility`).
- I did not confirm whether unpackaged apps can obtain the `graphicsCaptureWithoutBorder` capability via sparse packages.

---

## macOS: ScreenCaptureKit, CGEvent, AXUIElement, TCC, windows, Retina, Tahoe changes

### Takeaway
On macOS 15+, ScreenCaptureKit (`SCStream` for video/audio, `SCScreenshotManager` for stills) is the only supported capture path, since `CGWindowListCreateImage` is obsoleted in the macOS 15 SDK. Input is via `CGEventPost`, gated by the Accessibility pane / PostEvent service. The UI tree is `AXUIElement` (Accessibility). The biggest engineering risk is TCC. Grants attach to the *responsible process*, unbundled executables misbehave with ScreenCaptureKit on Tahoe, grants reset when ad-hoc-signed binaries change, and Screen Recording re-prompts periodically. Ship the daemon inside a stably-signed .app bundle with a fixed bundle ID.

### Cited Findings
**Capture APIs**
- Compiling `CGWindowListCreateImage` against the macOS 15 SDK fails because it is "obsoleted in macOS 15.0," with the compiler pointing to ScreenCaptureKit. It had been deprecated in macOS 14. The replacement is `SCScreenshotManager` (`captureImageWithFilter:configuration:completionHandler:`), which returns a CGImage or CMSampleBuffer. Chromium's snapshot code uses it — [Apple forums thread 740493](https://developer.apple.com/forums/thread/740493); [zenn.dev blog](https://zenn.dev/kyome/articles/c12c8a828173f5); [Chromium snapshot_mac.mm](https://chromium.googlesource.com/chromium/src/+/refs/tags/145.0.7632.159/ui/snapshot/snapshot_mac.mm)
- `CGWindowListCopyWindowInfo` (window enumeration metadata) was noted as *not* deprecated in a 2023 write-up — [nonstrict.eu ScreenCaptureKit on Sonoma](https://nonstrict.eu/blog/2023/a-look-at-screencapturekit-on-macos-sonoma/)
- `SCScreenshotManager` is async, and one developer sampling on every mouse move found it lagged badly compared with the old sync API — [Apple forums 740493](https://developer.apple.com/forums/thread/740493)
- The Rust `screencapturekit` crate (8.0.1) documents system-audio capture as available on macOS 13.0+ and microphone capture as macOS 15.0+ — [docs.rs screencapturekit 8.0.1](https://docs.rs/crate/screencapturekit/8.0.1); corroborated by [Recall.ai](https://www.recall.ai/blog/macos-screencapture-api); one Recall.ai tutorial says macOS 16 instead (conflict) — [Recall.ai meeting tutorial](https://www.recall.ai/blog/how-to-use-screencapturekit-to-record-a-meeting)
- Combining system-audio and mic streams can introduce echo, and none of the tools tested provided built-in AEC — [Recall.ai](https://www.recall.ai/blog/how-to-use-screencapturekit-to-record-a-meeting)

**TCC / permissions**
- Sequoia (15) moved Screen Recording re-authorization from weekly (beta) to monthly, with an "Allow For One Month" dialog. This applies to ScreenCaptureKit apps too. It also stopped prompting after every reboot. No documented developer opt-out exists, and a "Persistent Content Capture" entitlement is undocumented — [9to5Mac](https://9to5mac.com/2024/08/14/macos-sequoia-screen-recording-prompt-monthly/); [TidBITS](https://talk.tidbits.com/t/apple-reduces-excessive-sequoia-permission-requests-shifts-to-monthly/28621)
- Tahoe renamed the pane to "Screen & System Audio Recording." Apps enabled under the old entry may need re-granting. Sources disagree on the Tahoe re-prompt cadence (weekly vs monthly) — [Skilly](https://tryskilly.app/learn/enable-screen-recording-permission-macos/); [Screenify](https://www.screenify.studio/blog/2026-04-23-macos-screen-recording-permissions)
- Tahoe 26.1 regression report: a Unix executable that calls `CGRequestScreenCaptureAccess` gets the prompt but no longer appears in the Screen Recording list, so users can't review or revoke it. It worked on 26.0.1 — [Apple forums 807323](https://developer.apple.com/forums/thread/807323)
- On Tahoe, a Python helper's TCC entry showed as allowed but ScreenCaptureKit still failed with -3801, attributed to ScreenCaptureKit needing a proper app bundle. Capture "only shows desktop" — [trycua/cua#870](https://github.com/trycua/cua/issues/870)
- `CGPreflightScreenCaptureAccess` only checks status. `CGRequestScreenCaptureAccess` (or the first `SCShareableContent` call) registers or prompts. Authorization reset after each Xcode build for ad-hoc-signed builds. A 26.6.2 report describes re-prompting of an already-authorized build (FB24757092) — [search synthesis of Apple forums / ScreenCaptureKit tag](https://developer.apple.com/forums/tags/screencapturekit)
- Responsible-process attribution: an OpenClaw issue on Tahoe reports that `screencapture` spawned by a LaunchAgent-hosted Node gateway fails ("could not create image from display") even with Terminal/Node granted, because TCC "evaluates Screen Recording permissions based on the responsible process, not the parent process." The workaround was granting the exact `node` binary. The issue was closed as not planned — [openclaw/openclaw#14138](https://github.com/openclaw/openclaw/issues/14138)
- Posting synthetic keystrokes via `CGEvent.post` requires the Accessibility pane (TCC service `kTCCServicePostEvent`). `CGPreflightPostEventAccess`/`CGRequestPostEventAccess` exist but reportedly don't update until app restart. Listening via a listen-only `CGEventTap` is gated by Input Monitoring (`CGPreflightListenEventAccess`/`CGRequestListenEventAccess`), while a default (active) tap triggers Accessibility. Calling `AXIsProcessTrusted` registers the app in the Accessibility list — [Apple forums 820594](https://developer.apple.com/forums/thread/820594); [Apple forums 707680](https://developer.apple.com/forums/thread/707680); [Apple forums 122492](https://developer.apple.com/forums/thread/122492)
- Revoking Accessibility while an active CGEventTap runs can freeze system input until restart (reported, Feedback filed) — [Apple forums 844416](https://developer.apple.com/forums/thread/844416)
- MDM/PPPC: sources conflict on whether profiles can pre-grant Screen Recording. Apple's long-standing rule is that PPPC can only *deny* or allow-standard-user-to-approve for ScreenCapture. 26.2 started showing PPPC-granted permissions in System Settings — [Screenproof KB](https://screenproof.app/kb/screen-recording-permission); [Der Flounder](https://derflounder.wordpress.com/2025/12/12/pppc-device-management-settings-visible-in-system-settings-on-macos-tahoe-26-2-0/)

**Prior art**
- cua's macOS driver had to address Tahoe capture issues, and cua-driver-rs is a Rust port — [trycua/cua#870](https://github.com/trycua/cua/issues/870); [cua-driver-rs v0.6.6 release](https://newreleases.io/project/github/trycua/cua/release/cua-driver-rs-v0.6.6)

### Inferences
- Recommended macOS map:
  - **Screenshot:** `SCScreenshotManager` with `SCContentFilter` (display, or a single `SCWindow`). For bursts or low latency, keep a long-lived `SCStream` running and grab the latest frame instead of calling async one-shots.
  - **Input:** `CGEventCreateMouseEvent`/`CGEventCreateKeyboardEvent` + `CGEventPost(kCGHIDEventTap)`. Unicode text via `CGEventKeyboardSetUnicodeString` (background, unverified).
  - **Windows:** `CGWindowListCopyWindowInfo` for listing and z-order. `AXUIElement` (`kAXWindowsAttribute`, `kAXPositionAttribute`/`kAXSizeAttribute`, `AXRaise`) to move/resize/focus. `NSRunningApplication.activate` and `NSWorkspace` to launch/open (background).
  - **A11y:** `AXUIElementCreateApplication(pid)` tree walk (Accessibility permission).
  - **Audio:** ScreenCaptureKit `capturesAudio` (13+) and `captureMicrophone` (15+). Alternatively CoreAudio process taps on 14.4+ (background, unverified).
  - **Video:** `SCStream` → `AVAssetWriter` (or `SCRecordingOutput`, background, unverified).
- TCC strategy: a CLI or MCP server launched from Terminal/iTerm/VS Code/Claude Desktop inherits that host's grants via the responsible-process model. That is convenient but fragile, because it differs per host app and fails under launchd. The robust approach is a signed .app (Developer ID, stable bundle ID, hardened runtime) containing the daemon. Launch it via LaunchAgent with `AssociatedBundleIdentifiers` or open it as an app, so the grants for Screen Recording, Accessibility, Input Monitoring, and Microphone attach to one identity, and have the CLI talk to it over a local socket. This also avoids the Tahoe "unbundled executable missing from list" and -3801 problems.
- Retina: SCK/CG work in points for geometry (`SCDisplay.width/height`, `CGWindowBounds`, CGEvent locations in global display points with origin at the main display's top-left), while captured buffers are in pixels (×`backingScaleFactor`). Mixed-scale multi-monitor requires per-display scale lookup (background, unverified this session).
- Expect monthly (possibly weekly on Tahoe) Screen Recording re-confirmation dialogs. The toolkit should surface a "permission expired" error state rather than return black frames.

### Gaps
- I could not find Apple's official Tahoe release notes describing ScreenCaptureKit or TCC behavioral changes. The evidence is forum and GitHub reports.
- The Tahoe re-prompt cadence (weekly vs monthly) is unresolved.
- The `captureMicrophone` minimum OS (15 vs "16") conflicts across sources. 15.0 is more likely.
- I did not verify CoreAudio process-tap (`AudioHardwareCreateProcessTap`) availability or permission (it likely needs "System Audio Recording Only").

---

## Linux X11 (incl. user's Debian 13 XFCE/lightdm VM)

### Takeaway
On X11 everything is available without per-use prompts:
- **Capture:** XGetImage/XShm (xcb).
- **Input:** XTest.
- **Windows:** EWMH via `_NET_CLIENT_LIST`/`_NET_ACTIVE_WINDOW` (wmctrl/xprop).
- **Accessibility:** AT-SPI2 over D-Bus. It must be enabled, and Chromium/Electron may need flags or env vars.
- **Video:** ffmpeg x11grab.

Debian 13 ships Xfce 4.20 and PipeWire 1.4.2 / WirePlumber 0.5.8, but PipeWire's presence on an Xfce install isn't guaranteed. Audio code needs both PipeWire-native and PulseAudio-compat (`.monitor` source) paths.

### Cited Findings
- Debian 13 "trixie" (released 2025-08-09) ships GNOME 48, KDE Plasma 6.3, Xfce 4.20 — [Debian announcement](https://www.debian.org/News/2025/20250809)
- Trixie has PipeWire 1.4.2 and WirePlumber 0.5.8, "the default in most DesktopEnvironment's." A Debian developer says it's installed by default "at least if you install Gnome or KDE," so Xfce isn't confirmed — [Debian wiki PipeWire](https://wiki.debian.org/PipeWire); [Collabora](https://www.collabora.com/news-and-blog/news-and-events/debian-trixie-the-2025-flavor-release.html)
- A Rust MCP prior-art project (agent-sh/computer-use-linux) uses on native X11 a root-window `GetImage` capture, `xdotool`/XTEST for keyboard/clicks/scroll, and `wmctrl` + `xprop` (EWMH) for XFCE/other EWMH WMs, and the `atspi` crate for the a11y tree — [agent-sh/computer-use-linux](https://github.com/agent-sh/computer-use-linux)
- AT-SPI bus discovery happens via `org.a11y.Bus` on the session bus or the `AT_SPI_BUS` X root-window property. The `org.a11y.Status.IsEnabled` property on `/org/a11y/bus` is the desktop-neutral "accessibility on" flag. Xfce's 4.10 roadmap proposed syncing it with the "Enable assistive technologies" checkbox (shipping status unconfirmed) — [at-spi2-core bus README](https://git.stg.centos.org/source-git/at-spi2-core/blob/f9e01f6f07c1ca13baaa85d141081f17fef3cef0/f/bus); [Xfce wiki a11y roadmap](https://wiki.xfce.org/releng/4.10/roadmap/accessibility); [Launchpad Firefox bug 857153](https://bugs.qastaging.launchpad.net/ubuntu/+source/firefox/+bug/857153/comments/8)
- Chromium: in 2020 auto-detection was disabled and `--force-renderer-accessibility` was required again, with a fix said to land in v86. An attempt to read the AT-SPI bus property on non-GNOME desktops was reverted for performance. `ACCESSIBILITY_ENABLED=1` was reported to make Chromium/Electron apps expose a11y — [orca-list 2020-05](https://mail.gnome.org/archives/orca-list/2020-May/msg00298.html); [orca-list 2020-07](https://mail.gnome.org/archives/orca-list/2020-July/msg00122.html); [crrev](https://crrev.com/c7c15e712cb77a0fe276166996b2bb787490c896)
- Firefox historically enables a11y if `GNOME_ACCESSIBILITY=1` or the GNOME setting is true. It has an `accessibility.force_disabled` pref — [Launchpad 857153](https://bugs.qastaging.launchpad.net/ubuntu/+source/firefox/+bug/857153/comments/7); [Mozilla bug 769304](https://bugzilla.mozilla.org/show_bug.cgi?id=769304)
- Running apps over SSH as another user yields "Couldn't register with accessibility bus." `NO_AT_BRIDGE=1` silences it but disables a11y — [Xfce forum](https://forum.xfce.org/viewtopic.php?id=14239)
- Toggling accessibility may require restarting target apps (observed by computer-use-linux) — [agent-sh/computer-use-linux](https://github.com/agent-sh/computer-use-linux)
- Rust `atspi` crate 0.30.0 (May 6, 2026), part of the Odilia screen reader project, is a "Higher level, asynchronous, pure Rust AT-SPI2 protocol implementation using zbus," `#[deny(unsafe_code)]`, and works with tokio or smol — [lib.rs atspi](https://lib.rs/crates/atspi)
- Xfce's Wayland compositor `xfwl4` exists as a "4.21 preview," with no clipboard protocol yet — [Lamco platform matrix](https://lamco.ai/products/lamco-rdp-server/platforms/)

### Inferences
- Recommended X11 map:
  - **Screenshot:** xcb + MIT-SHM `ShmGetImage` on the root window, cropping per monitor via RandR (`xcb_randr_get_monitors`), or per window via `xcb_get_geometry`/`translate_coordinates`. Note that root-window capture of an occluded window shows what's on top unless a compositing WM with XComposite `NameWindowPixmap` is used (background, unverified).
  - **Input:** XTest `xcb_test_fake_input`. For Unicode, temporarily remap a spare keycode to the needed keysym (the xdotool technique, background).
  - **Windows:** EWMH `_NET_CLIENT_LIST_STACKING`, `_NET_WM_NAME`, `_NET_WM_PID`, `_NET_ACTIVE_WINDOW` (ClientMessage) and `_NET_MOVERESIZE_WINDOW` — xfwm4 is EWMH-compliant (background).
  - **A11y:** set `org.a11y.Status IsEnabled=true` (gsettings `toolkit-accessibility` on GNOME), export `ACCESSIBILITY_ENABLED=1`, `GNOME_ACCESSIBILITY=1`, `QT_ACCESSIBILITY=1` for launched apps, and launch Chromium-family with `--force-renderer-accessibility`.
  - **Video:** `ffmpeg -f x11grab -video_size WxH -framerate N -i :0.0+X,Y` (background).
  - **HiDPI on X11:** scaling is per-session (Xft.dpi / GDK_SCALE), not per-monitor, so screen pixel coordinates equal XTest coordinates (background).
- For the user's VM: if the VM uses a virtual GPU (virtio/QXL), there is no VAAPI on the Radeon 780M, so plan on software x264/VP9 encode for clips. Use XShm (works on Xorg in VMs). Check `pactl info` to detect PipeWire vs PulseAudio.

### Gaps
- I could not confirm whether current Chromium (2026) still needs `--force-renderer-accessibility` on non-GNOME desktops like Xfce.
- I could not confirm whether Xfce 4.20 toggles `org.a11y.Status.IsEnabled`.
- I did not confirm the xdg-desktop-portal version in Debian 13, or whether an Xfce portal backend implements Screenshot/ScreenCast on X11. It doesn't matter much on X11, since direct APIs work.

---

## Linux Wayland: portals, libei/EIS, wlroots/ext protocols, compositor IPC, recorders, audio

### Takeaway
Wayland deliberately has no global screenshot, input-injection, or window-list API for ordinary clients. The 2026 reality is three tiers:
1. **GNOME / KDE (and niri via the GNOME portal):** xdg-desktop-portal Screenshot/ScreenCast (PipeWire) + RemoteDesktop with ConnectToEIS (libei). Restore tokens (`persist_mode=2`) avoid repeated dialogs after first consent.
2. **wlroots family (Sway, Hyprland, river, Wayfire, labwc):** direct protocols with no dialogs, namely `wlr-screencopy` / `ext-image-copy-capture-v1` and `wlr-virtual-pointer` + `virtual-keyboard`, plus `wlr`/`ext-foreign-toplevel`. The RemoteDesktop/EIS portal path is still not merged in xdg-desktop-portal-wlr or -hyprland.
3. **Fallback:** uinput (ydotool) — compositor-agnostic but focus-blind and layout-fragile.

Window enumeration/focus remains compositor-specific: GNOME Shell extension, KWin scripting via D-Bus, hyprctl, swaymsg/i3 IPC, niri msg. GNOME 50 (Mar 2026) and Plasma 6.8 (due ~2026-10-14) are Wayland-only.

### Cited Findings
**Platform direction**
- GNOME 50 removed the X11 session code from Mutter/Shell, with X11 apps still running via Xwayland — [heise](https://heise.de/-11067046); [Linuxiac](https://linuxiac.com/gnome-50-ends-the-x11-era-after-decades/)
- KDE Plasma 6.8, expected ~Oct 14, 2026, is Wayland-exclusive. Plasma 6.7 is the last with an X11 session — [Phoronix](https://www.phoronix.com/news/KDE-Plasma-68-Wayland-Exclusive); [GamingOnLinux](https://www.gamingonlinux.com/2026/06/kde-plasma-waves-goodbye-to-x11-for-plasma-6-8/)

**libei / RemoteDesktop portal**
- libei has been integrated in the XDG RemoteDesktop and InputCapture portals since xdg-desktop-portal 1.17 (mid-2023). Session persistence has been in the portals since 1.21.0 and "should be in the major compositors in the current or next versions." Xwayland translates XTEST to libei since Xwayland 23.2.0. The EIS side (compositor) controls which devices exist and when events are allowed, and the user can see who is sending events — [Who-T blog, 2026-07-22](http://who-t.blogspot.com/2026/07/libei-integrations-in-xdg-remotedesktop.html)
- Portal spec: `ConnectToEIS` was added in RemoteDesktop v2. Once EIS is connected, the `Notify*` D-Bus methods must not be used. Remote desktop persistence uses `persist_mode` and `restore_token` in `SelectDevices()`. These must *not* be passed in `ScreenCast.SelectSources` for an RD session. `persist_mode` is 0 none, 1 app lifetime, 2 until revoked. A restore token is single-use, so you must store the new one returned by each `Start`. Tokens are ignored if the stored session can't be restored (e.g., a monitor is gone) — [XDG portal RemoteDesktop docs](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
- GNOME backend has supported RD persistence since xdg-desktop-portal-gnome MR !88 (merged 2023-08-04). On GNOME the "remember" box defaults to checked, and later processes restore until revoked — [agent-sh/computer-use-linux PR #188](https://github.com/agent-sh/computer-use-linux/pull/188); [issue #185](https://github.com/agent-sh/computer-use-linux/issues/185)
- Conflict: Lamco's matrix says for Ubuntu 24.04 + GNOME 46 "Portal tokens rejected by GNOME policy," while KDE Plasma 6.6+ token persistence works ("not rejected") — [Lamco platform matrix](https://lamco.ai/products/lamco-rdp-server/platforms/)
- Persistence pitfalls:
  - The KDE portal's tokens didn't survive reboot (KDE bug 480235), and one 2026 KDE report had no restore token returned until stale state files were deleted.
  - Concurrent processes spending the same token invalidated it, so hold a file lock across `Start`.
  - Launching from a terminal can make the portal see a different or empty app ID and reject persistence.
  — [KDE bug 480235](https://bugs.kde.org/show_bug.cgi?id=480235); [lamco-rdp-server#51](https://github.com/lamco-admin/lamco-rdp-server/issues/51); [bitbound/ControlR#169](https://github.com/bitbound/ControlR/issues/169); [cosmic-comp#2869](https://github.com/pop-os/cosmic-comp/issues/2869)
- KDE: Plasma 6.7.5 with xdg-desktop-portal-kde 6.7.5 exposes RemoteDesktop v2 with ConnectToEIS, alongside libei 1.6.0 — [fcitx5-lotus#526](https://github.com/LotusInputMethod/fcitx5-lotus/issues/526). Lamco lists libei on Plasma 6.1+ — [Lamco](https://lamco.ai/products/lamco-rdp-server/platforms/)
- wlroots: xdg-desktop-portal-hyprland PR #402 (RemoteDesktop + ConnectToEIS via a libeis server translating to `wlr-virtual-pointer-unstable-v1` / `virtual-keyboard-unstable-v1`) is **open, not merged**. It was opened 2026-05-29, the last comment was 2026-10-04, and it has no persistence support mentioned — [xdph PR #402](https://github.com/hyprwm/xdg-desktop-portal-hyprland/pull/402). Lamco says wlroots Flatpak input is "blocked pending portal-wlr PR #325" — [Lamco](https://lamco.ai/products/lamco-rdp-server/platforms/)
- COSMIC: one report says its RemoteDesktop portal "only landed in august 2026 via xdg-desktop-portal-cosmic#317" with no `persist_mode` yet, while Lamco lists COSMIC as having no RD portal or libei, and mouse only via uinput (conflict, likely timing) — [cosmic-comp#2869](https://github.com/pop-os/cosmic-comp/issues/2869); [Lamco](https://lamco.ai/products/lamco-rdp-server/platforms/)

**Screen capture protocols**
- `ext-image-copy-capture-v1` (+ `ext-image-capture-source-v1`) is the standardized successor, and `wlr-screencopy` is marked deprecated — [wayland.app ext-image-copy-capture](https://wayland.app/protocols/ext-image-copy-capture-v1); [wayland.app wlr-screencopy](https://wayland.app/protocols/wlr-screencopy-unstable-v1)
- Compositor status:
  - **Sway:** 1.11 (wlroots 0.19) added ext-image-copy-capture, output capture only initially — [sway PR #7976](https://github.com/swaywm/sway/pull/7976); [AlternativeTo](https://alternativeto.net/news/2025/6/sway-1-11-released-with-wlroots-0-19-new-wayland-protocols-and-explicit-sync-support/)
  - **niri:** merged output and cursor ext-image-copy-capture on 2026-09-12 (PR #4554). The toplevel capture PR #4599 is pending — [niri PR #4554](https://github.com/niri-wm/niri/pull/4554); [niri PR #4599](https://github.com/niri-wm/niri/pull/4599)
  - **Hyprland:** a feature request (#9916) asks for ext-image-copy-capture, since it supports only wlr-screencopy — [Hyprland#9916](https://github.com/hyprwm/Hyprland/issues/9916)
  - **KWin 6.6.6:** a probe found no ext-image-copy-capture and no foreign-toplevel globals — [trycua/cua#3972](https://github.com/trycua/cua/issues/3972)
- KDE alternative: KWin `ScreenShot2` D-Bus writes raw pixels into a caller-supplied fd. One tool reaches ~40 fps at 1440p with it — [kwcapture](https://github.com/tjandrasg/kwcapture)
- GNOME: since gnome-shell 41 (MR !1970), `org.gnome.Shell.Screenshot` is limited to an allowlist of well-known bus names (portals, gnome-screenshot), returning `AccessDenied: Screenshot is not allowed` otherwise. Unsafe mode (`global.context.unsafe_mode = true` via Looking Glass) bypasses it. The name check is weak because an unsandboxed client can own the name — [GIMP#7591](https://gitlab.gnome.org/GNOME/gimp/-/issues/7591); [gnome-shell MR !1970](https://gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/1970); [gnome-shell#4840](https://gitlab.gnome.org/GNOME/gnome-shell/-/issues/4840); [gnome-screenshot#179](https://gitlab.gnome.org/GNOME/gnome-screenshot/-/issues/179)

**Window enumeration**
- `ext-foreign-toplevel-list-v1` is intentionally minimal (handles only), and whether ordinary clients may bind it is compositor policy — [wayland.app ext-foreign-toplevel-list](https://wayland.app/protocols/ext-foreign-toplevel-list-v1)
- Hyprland reportedly doesn't advertise ext-foreign-toplevel-list — [chonkstep#77](https://github.com/iconidentify/chonkstep/issues/77)
- KWin doesn't expose wlr-foreign-toplevel-management or ext-foreign-toplevel-list to clients (Noctalia, cua probe). wayland.app lists KWin 6.6 for the wlr variant (conflict) — [Noctalia KDE notes](https://docs.noctalia.dev/noctalia/compositor-settings/kde/); [cua#3972](https://github.com/trycua/cua/issues/3972); [wayland.app wlr-foreign-toplevel](https://wayland.app/protocols/wlr-foreign-toplevel-management-unstable-v1)

**Prior art backend matrices**
- computer-use-linux (Rust MCP):
  - **Screenshots:** GNOME Shell D-Bus → Screenshot portal → X11 GetImage → gnome-screenshot.
  - **Wayland pointer:** RemoteDesktop portal, then ydotool/uinput fallback.
  - **Text:** KDE clipboard, `wtype` on wlroots, portal keysyms, then ydotool. Raw ydotool text is limited to printable ASCII, tab, and newline.
  - **Windows:** GNOME Shell extension → GNOME Shell Introspect → COSMIC helper → KWin D-Bus scripting → hyprctl → niri IPC → i3 IPC → EWMH. Sway/generic wlroots has no dedicated exact list/focus backend.
  - **Known issues:** black screenshots on multi-monitor, and niri omits window positions with mixed scaling.
  — [agent-sh/computer-use-linux](https://github.com/agent-sh/computer-use-linux)
- wdotool (Rust, xdotool-compatible):
  - **Backends:** libei via portal (preferred on GNOME/KDE), direct wlr-protocols (virtual keyboard/pointer + foreign-toplevel; preferred on Sway/Hyprland/river/Wayfire), KWin scripting over D-Bus for windows, a GNOME Shell extension for windows (Shell 45–48), and uinput fallback.
  - **Unicode:** the wlr backend handles arbitrary Unicode by uploading a transient xkb keymap per `type`. With libei "Characters not in the active layout are skipped." uinput uses the default xkb layout best-effort.
  - **Persistence:** caches the portal restore_token at `$XDG_STATE_HOME/wdotool/portal.token`.
  - **Testing status:** GNOME/KDE paths not yet smoke-tested.
  — [cushycush/wdotool](https://github.com/cushycush/wdotool)
- cua-driver (Rust port) added Wayland paths via wlroots, portal, and libei in June 2026. It autodiscovers XAUTHORITY for SSH-driven Wayland+Xwayland, fails loudly when X11 input can't be delivered on pure Wayland, and reports dead input backends on KDE/GNOME — [cua changelog 2026-06-22](https://cua.ai/changelog/2026-06-22); [cua-driver-rs v0.6.6](https://newreleases.io/project/github/trycua/cua/release/cua-driver-rs-v0.6.6)
- cua reports that on niri capture works but every input action was refused (issue), and on Plasma 6.6 the native Wayland input backend failed — [cua#3735](https://github.com/trycua/cua/issues/3735); [cua#3972](https://github.com/trycua/cua/issues/3972)
- Lamco RDP server (Rust) native paths:
  - **Sway 1.11/1.12 and Hyprland 0.55.4:** `wlr-screencopy-v1` + `wlr-virtual-keyboard/pointer` with "zero permission dialogs."
  - **GNOME 40–50:** Portal RD v2 + libei, plus "Mutter Direct API for dialog-free, per-connection sessions."
  - **KDE 6.6+:** Portal RD v2 + libei.
  - **niri:** via xdg-desktop-portal-gnome.
  — [Lamco platform matrix](https://lamco.ai/products/lamco-rdp-server/platforms/)

**Audio (PipeWire)**
- Native: set `stream.capture.sink=true` on a capture stream (optionally `target.object=<sink>`) to capture the sink monitor. Pulse-compat: record the `<sink>.monitor` source with `parec`/`parecord --device`. Pitfalls include `@DEFAULT_MONITOR@` unsupported in some versions (recording the mic instead), choppy audio when pointing pw-record at an output device, and notification sounds bleeding in — [flexaudio-os-linux docs](https://docs.rs/flexaudio-os-linux); [pipewire loopback man](https://manpages.opensuse.org/Tumbleweed/pipewire-modules-0_3/libpipewire-module-loopback.7.en.html); [PipeWire#3284](https://gitlab.freedesktop.org/pipewire/pipewire/-/issues/3284); [Fedora discussion](https://discussion.fedoraproject.org/t/what-is-the-equivalent-of-pulseaudios-monitor-sources-in-pipewire/68939); [ro-che.info guide](https://ro-che.info/articles/2017-07-21-record-audio-linux)

**Rust portal client**
- `ashpd` 0.13.13 (Jul 17, 2026) has feature flags `screenshot`, `screencast`, `remote_desktop`, `input_capture`, with tokio by default and async-io optional — [lib.rs ashpd](https://lib.rs/crates/ashpd)
- Python bindings for libei/libeis/liboeffis exist (python-libei), tested against GNOME Wayland on 2026-09-01 — [ctrondlp/python-libei](https://github.com/ctrondlp/python-libei)

### Inferences
- Wayland decision tree (runtime-probed, not by `XDG_CURRENT_DESKTOP` alone):

  **Screenshot**
  - wlroots/niri/COSMIC: `ext-image-copy-capture` if advertised (check `wayland-info`), else `wlr-screencopy`.
  - KDE: KWin `ScreenShot2` D-Bus. This likely needs a `.desktop` file with `X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2` (background, unverified).
  - GNOME: Screenshot portal (non-interactive after first grant), or keep a persistent ScreenCast portal session open and grab PipeWire frames for fast repeated shots. ScreenCast persist_mode=2 restore tokens work similarly (background).

  **Input**
  - GNOME/KDE: RemoteDesktop portal (`persist_mode=2`) + ConnectToEIS via libei. Fall back to `Notify*` D-Bus methods if EIS isn't available.
  - wlroots: `zwlr_virtual_pointer_v1` + `zwp_virtual_keyboard_v1`, uploading your own xkb keymap so Unicode works.
  - Last resort: uinput. It needs `/dev/uinput` access via the input group or a udev rule, is layout-dependent, and can't target windows.

  **Window list/focus**
  - GNOME: a small Shell extension exposing D-Bus (as computer-use-linux and wdotool do; the "Window Calls" extension is a popular third-party option, background).
  - KDE: load a KWin script via `org.kde.kwin.Scripting` D-Bus.
  - Sway: `swaymsg -t get_tree`.
  - Hyprland: `hyprctl clients -j`.
  - niri: `niri msg --json windows`.
  - Others: `ext-foreign-toplevel-list` when exposed.

  **A11y:** AT-SPI2 works on Wayland the same as X11, but AT-SPI component coordinates are often window-relative or unknown on Wayland since apps don't know their global position (background, unverified). Map them using window geometry from compositor IPC.

  **Video:**
  - Portal ScreenCast → PipeWire → encoder (GStreamer `pipewiresrc` or libavcodec).
  - wlroots: `wf-recorder` (wlr-screencopy) or `gpu-screen-recorder` (KMS/portal, VAAPI).
  - Background, unverified for exact tool capabilities.
- Coordinate mapping on Wayland: portal ScreenCast streams provide stream position and size in logical coordinates, while EIS absolute devices expose regions per output with scale (background, unverified). The toolkit needs one canonical "logical desktop" space plus per-output scale to convert screenshot pixels to input coordinates. Fractional scaling (1.25, 1.5) is common on GNOME/KDE.
- Keep a single long-lived daemon per session to hold the portal session and restore token, serializing token use with a lock. Spawning a new process per CLI call triggers a dialog each time on portals that don't persist.

### Gaps
- No official 2026 confirmation of merge status for xdg-desktop-portal-wlr PR #325 (RemoteDesktop/EIS). The Hyprland PR is confirmed open.
- Unresolved: whether GNOME 49/50 accepts RemoteDesktop restore tokens for non-Flatpak host apps (Lamco says rejected on GNOME 46; computer-use-linux says it works with persist_mode on SelectDevices).
- Not found: an official per-compositor support table for `ext-foreign-toplevel-list` and toplevel capture in Hyprland, KWin, and GNOME (Mutter doesn't implement the wlr/ext capture protocols, background).
- Not verified: current status of `wlr-screencopy` vs `ext-image-copy-capture` in Hyprland 0.56.x.
- Not verified: gpu-screen-recorder and wf-recorder 2026 versions.

---

## Cross-platform libraries and their 2026 maturity (Rust, Go, Python, Node/TS)

### Takeaway
No single library covers every OS and capability, Wayland included. Rust has the deepest and most actively maintained building blocks: xcap 0.9.8 (Aug 2026), windows-capture, screencapturekit 8.x, enigo (libei and Wayland experimental), atspi 0.30, ashpd 0.13, uiautomation. Most of the 2026 computer-use prior art is also Rust: cua-driver-rs, computer-use-linux, wdotool, Lamco. Python is strong for prototyping (mss 10.2.0, pywinauto/pyobjc/pyatspi) but weak on Wayland and awkward for macOS TCC. Node's nut.js is now commercial (paid prebuilt packages), and Go's robotgo has unclear 2026 Wayland status.

### Cited Findings
**Rust**
- `xcap` 0.9.8 (Aug 1, 2026; 47 releases). It supports screen capture, window capture, and screen recording on Windows ≥8.1, macOS, and X11. Wayland is marked "available, but not fully supported in some special scenarios," window recording is "to be developed," and it depends on `libwayshot-xcap`, `pipewire`, `zbus`, `xcb` — [lib.rs xcap](https://lib.rs/crates/xcap)
- `enigo`: Windows, macOS, and X11 (`xdo` feature needs libxdo-dev) mouse and text are supported. "Linux (Wayland) … (Experimental)" and "Linux (libei) … (Experimental)" are behind feature flags because "there are currently some bugs." Requires Rust 1.87+ — [enigo-rs/enigo](https://github.com/enigo-rs/enigo)
- `windows-capture` (WGC; Rust + Python) is at 1.5.0 on docs.rs. `uiautomation` (UIA wrapper) last pushed ~Mar 2026 — [docs.rs windows-capture](https://docs.rs/windows-capture); [gittrend uiautomation-rs](https://gittrend.io/repo/leexgone/uiautomation-rs)
- `scap` is split across forks (CapSoftware, helmerapp, Latias94). The helmerapp crate is "WIP. Unsuitable for production use," the docs.rs build failed for 0.0.8, and I found no 2026 activity — [helmerapp/scap](https://github.com/helmerapp/scap); [docs.rs scap](https://docs.rs/scap)
- `screencapturekit` crate 8.0.1 maps macOS features by OS version — [docs.rs](https://docs.rs/crate/screencapturekit/8.0.1)
- `atspi` 0.30.0 (May 2026), `ashpd` 0.13.13 (Jul 2026) — [lib.rs atspi](https://lib.rs/crates/atspi); [lib.rs ashpd](https://lib.rs/crates/ashpd)
- `uni-ocr` crate wraps Apple Vision, Windows OCR, and Tesseract — [docs.rs uni-ocr](https://docs.rs/crate/uni-ocr/latest)

**Python**
- `mss` 10.2.0 (Apr 23, 2026) introduces a unified `mss.MSS` class. The per-OS classes are deprecated, to be removed in 11.0 — [python-mss 10.2.0 notes](https://python-mss.readthedocs.io/stable/release-history/v10.2.0.html)
- `psutil` 7.2.2 (Jan 28, 2026) — [pepy.tech](https://pepy.tech/projects/psutil); [Arch package](https://archlinux.org/packages/extra/x86_64/python-psutil/)

**Node/TS**
- nut.js now requires buying a license to access its prebuilt packages (`@nut-tree/nut-js`). An open-source repo is still linked, but its 2026 maintenance is unclear — [nutjs.dev](https://nutjs.dev/); [getting started](https://nutjs.dev/docs/getting-started)
- `@jitsi/robotjs` 0.6.23 (registry updated Jul 2, 2026) is an MIT fork of robotjs that exists to ship prebuilt binaries, flagged pre-1.0 — [Socket.dev @jitsi/robotjs](https://socket.dev/npm/package/@jitsi/robotjs/overview/0.6.23)

**Go**
- robotgo: an indexed copy of newer docs claims Linux X11, Wayland (wlroots), and libei support plus experimental pure-Go (`purego`, `wayland` build tags). The cached master README still says "Linux(X11)," and I found no 2026 release — [algolia docsearch robotgo](https://docsearch.algolia.com/mcp/docs/repo/go-vgo/robotgo); [robotgo README](https://github.com/go-vgo/robotgo/blob/master/README.md)
- A cgo-free Go libei package exists (`github.com/leaanthony/robot-nocgo/libei`) — [pkg.go.dev](https://pkg.go.dev/github.com/leaanthony/robot-nocgo/libei)
- `gopsutil` v4 uses calendar tags (v4.25.8 latest on pkg.go.dev). Linux `VirtualMemoryStat.Used` moved to a MemAvailable basis — [pkg.go.dev gopsutil v4](https://pkg.go.dev/github.com/shirou/gopsutil/v4)

### Inferences
- **Wayland support:**
  - Proper portal/libei/wlr handling: none of the "classic" cross-platform input libraries (pyautogui, pynput, robotjs, nut.js) handle Wayland properly, to my knowledge (background, unverified for 2026).
  - enigo (experimental) and robotgo (unconfirmed) have started.
  - The serious Wayland implementations in 2026 are purpose-built Rust projects (wdotool, computer-use-linux, cua-driver-rs, Lamco) that combine ashpd/libei/wayland-client directly.
- **HiDPI:** xcap and mss return physical pixels (background). Input libraries typically take OS-native coordinates (points on macOS, physical pixels when DPI-aware on Windows). The toolkit must own the mapping layer rather than trust any library.
- Python `pyobjc` + `pyatspi` + `pywinauto` remain the most complete a11y-tree libraries for quick wins (background, unverified for 2026 releases). A Python interpreter as the TCC subject on macOS is fragile, as the cua#870 Python-helper case shows.

### Gaps
- I did not verify the 2026 status of pyautogui, pynput, pywinauto, pyatspi, node-screenshots, kbinani/screenshot, rdev, active-win-pos-rs, or cpal (release dates and Wayland support).
- crates.io/PyPI/npm pages weren't directly fetched for most packages. The dates come from lib.rs, docs.rs, and trackers.

---

## Process listing, app launching, opening URLs/files

### Takeaway
This is a solved problem. Use `sysinfo` (Rust), `psutil` (Python), or `gopsutil` (Go) for process enumeration, and OS launchers for apps and URLs. The only nuance is mapping PIDs to windows, which comes per-OS from the window APIs above.

### Cited Findings
- Rust `sysinfo` 0.37.2 is current in Fedora Rawhide/44/45. It covers processes, CPUs, disks, components, and networks — [Fedora packages rust-sysinfo](https://packages.fedoraproject.org/pkgs/rust-sysinfo/rust-sysinfo-devel/)
- psutil 7.2.2 (Jan 2026). 7.1.2 dropped prebuilt 32-bit wheels — [pepy.tech](https://pepy.tech/projects/psutil)
- gopsutil v4 (v4.25.x) — [pkg.go.dev](https://pkg.go.dev/github.com/shirou/gopsutil/v4)

### Inferences
- Launch/open per OS (background, unverified this session):
  - **Windows:** `ShellExecuteExW` (`open` verb) or `CreateProcessW`. Map PID to HWND via `GetWindowThreadProcessId`.
  - **macOS:** `NSWorkspace.openApplication(at:configuration:)` / `open -a` / `open -b <bundleid>`, and `NSWorkspace.open(URL)`. Map PID to windows via `kCGWindowOwnerPID`.
  - **Linux:** `xdg-open` / `gio launch` / `gtk-launch <desktop-id>`, or the D-Bus `org.freedesktop.Application` activation. Map PID to window on X11 via `_NET_WM_PID`. On Wayland, use compositor IPC: hyprctl, swaymsg, and niri report PIDs, and the GNOME extension can expose them.
- Launched GUI apps must inherit the session environment (DISPLAY, WAYLAND_DISPLAY, DBUS_SESSION_BUS_ADDRESS, XDG_RUNTIME_DIR). This is easiest if the daemon itself runs inside the session (see the headless section). Rust crate `open` is a common URL/file opener (background).

### Gaps
- No source fetched on the 2026 status of the `open` crate or Windows app-launch via AppUserModelID for packaged (Store) apps.

---

## OCR options per platform

### Takeaway
Native engines are the cheapest: Apple Vision on macOS, Windows.Media.Ocr on Windows. RapidOCR/PaddleOCR (ONNX) is the best cross-platform choice for UI screenshots, while Tesseract is fast on clean document-like images but often poor on real UI screenshots. No rigorous UI-screenshot benchmark across all four exists, so the toolkit should ship a pluggable OCR interface and benchmark locally.

### Cited Findings
- uni-ocr README (M4 Max): macOS Vision 3.2 images/s at 90.0% accuracy versus Windows OCR 1.2 images/s at 95.2%. The dataset is unspecified, and Tesseract is "tbd" — [docs.rs uni-ocr](https://docs.rs/crate/uni-ocr/latest)
- Tesseract took ~4 s per 1920×1080 screenshot on an i5-1235U (2024) — [tesseract-ocr Google Group](https://groups.google.com/g/tesseract-ocr/c/c_S7GG5njkw/m/OPQ6q5zBAQAJ)
- On an 800×600 invoice (Apple M-series), Tesseract ran 0.162 s with 3 errors and RapidOCR 0.212 s with 6 errors. That is a document, not UI — [invoicedataextraction.com](https://invoicedataextraction.com/blog/python-ocr-library-comparison-invoices)
- One developer switched from Tesseract to RapidOCR because Tesseract "produced garbage on real screenshots," reporting RapidOCR at 3–4 s on a full-resolution screenshot (CPU) — [Mic92 dotfiles live-text ocr.py](https://git.thalheim.io/Mic92/dotfiles/src/branch/main/pkgs/live-text/live_text/ocr.py)
- Fair OCR benchmarks must state CPU/GPU, cold vs warm, resolution, languages, and detector — [Codesota](https://codesota.com/ocr/best-for-python)
- SnipOCR pairs Windows.Media.Ocr with RapidOCR — [nuroctane/snipocr](https://github.com/nuroctane/snipocr)
- A RapidOCR PP-OCRv4 ONNX benchmark space exists — [HF RapidOCR benchmark](https://rbaks-rapidocr-benchmark.hf.space/)

### Inferences
- Default engine per OS: Apple Vision (`VNRecognizeTextRequest`, `.accurate` mode, via objc2 or pyobjc) on macOS. `Windows.Media.Ocr.OcrEngine` (WinRT, needs the OCR language pack installed) on Windows. RapidOCR (ONNX Runtime, PP-OCRv4/v5 models) on Linux and as a cross-platform fallback. Tesseract only as a dependency-light fallback, with upscaling ×2 and binarization for UI text (background, unverified).
- For computer-use, OCR is mainly for grounding text locations when the a11y tree is missing. Running OCR on crops (a window or region) rather than full 4K screens keeps latency well under 1 s.

### Gaps
- No credible head-to-head benchmark of Vision, Windows OCR, RapidOCR, and Tesseract on UI screenshots was found.
- Not checked: GPU/NPU-accelerated options (e.g., Windows AI "Text Recognition" APIs on Copilot+ PCs) or 2026 PaddleOCR v5 numbers.

---

## Remote/headless operation: daemon inside the graphical session, virtual displays, VNC/RDP

### Takeaway
The toolkit's daemon should run *inside* the user's graphical session, as a systemd `--user` service or autostart on Linux, a LaunchAgent/app on macOS, or a logon task in the interactive session on Windows. An SSH-connected agent then talks to it over a local socket rather than trying to borrow DISPLAY/XAUTHORITY/WAYLAND_DISPLAY/DBUS_SESSION_BUS_ADDRESS from an SSH shell. For CI or headless use:
- **X11:** Xvfb.
- **wlroots:** sway with `WLR_BACKENDS=headless` (+ wayvnc).
- **GNOME:** `mutter --wayland --headless --virtual-monitor WxH` / gnome-remote-desktop.
- **Weston, KWin, Mutter, gnome-kiosk, cage:** wlheadless-run.

### Cited Findings
- cua-driver-rs added XAUTHORITY autodiscovery for SSH-driven Wayland+Xwayland sessions and typed "no-display" errors — [cua-driver-rs v0.6.6](https://newreleases.io/project/github/trycua/cua/release/cua-driver-rs-v0.6.6); [cua changelog](https://cua.ai/changelog/2026-06-22)
- computer-use-linux runs `ydotoold` as a per-user service with the socket in `/run/user/$UID/` (mode 0600). It falls back to `gnome-screenshot` in background/systemd contexts where D-Bus paths are denied. AT-SPI and the extension expose data only to same-session clients — [agent-sh/computer-use-linux](https://github.com/agent-sh/computer-use-linux)
- Containers, system services, sudo, and unrelated SSH sessions don't inherit the graphical user's D-Bus/AT-SPI bus — [search synthesis; Xfce forum](https://forum.xfce.org/viewtopic.php?id=14239)
- Sway headless:
  - A FreeBSD ports commit shows sway launched with the headless backend set by environment variable.
  - `swaymsg create_output` adds `HEADLESS-N` virtual outputs.
  - wayvnc works headless but supports only wlroots compositors (not GNOME, KDE, Weston) and requires encryption by default.
  - A wlroots issue reports grey output over VNC with headless sway.
  — [FreeBSD ports commit](https://gitlab.com/FreeBSD/freebsd-ports/commit/a347cfee7327523b2a42ccc20b445c59658cf64a); [sway-vdctl](https://github.com/odincat/sway-vdctl); [wayvnc man](https://dyn.manpages.debian.org/bookworm/wayvnc/wayvnc.1.en.html); [wlroots#3712](https://gitlab.freedesktop.org/wlroots/wlroots/-/issues/3712)
- Mutter has a headless native backend with virtual monitors since GNOME 40 (`mutter --wayland --headless --virtual-monitor 1920x1080`). gnome-remote-desktop uses virtual monitors only for RDP. GDM's Wayland session launches gnome-session, so shell flags don't apply there — [Phoronix GNOME 40](https://www.phoronix.com/news/GNOME-40-Headless-Virtual); [Eclipse CI example](https://www.eclipse.org/lists/cbi-dev/msg02448.html); [openSUSE hackweek](https://hackweek.opensuse.org/projects/support-virtual-monitors-for-vnc-in-gnome-remote-desktop); [GNOME Discourse](https://discourse.gnome.org/t/how-to-make-gnome-shell-always-start-with-command-line-arguments-at-system-launch/18906)
- `wlheadless-run` (xwayland-run package, in Debian trixie) spawns clients on a headless weston (default), kwin, mutter, gnome-kiosk, or cage — [Debian manpage wlheadless-run](https://dyn.manpages.debian.org/trixie/xwayland-run/wlheadless-run.1.en.html)
- Headless KWin lacks a working VNC/RDP story (krfb-virtualmonitor crashes reported) — [KDE Discuss](https://discuss.kde.org/t/do-kde-developers-expect-everyone-to-just-use-waypipe-and-forget-about-using-vnc-rdp-if-kwin-is-running-in-headless-mode/27406)
- Lamco's RDP server uses GNOME's "Mutter Direct API for dialog-free, per-connection sessions" (i.e., the org.gnome.Mutter.RemoteDesktop/ScreenCast D-Bus APIs) — [Lamco](https://lamco.ai/products/lamco-rdp-server/platforms/)

### Inferences
- **Linux session discovery from SSH (fallback when no daemon is running):**
  - Find the user's session via `loginctl list-sessions` / `loginctl show-session <id> -p Display -p Type -p Leader`.
  - `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UID/bus`.
  - `WAYLAND_DISPLAY` is the socket name in `$XDG_RUNTIME_DIR` (`wayland-0`).
  - For X11, take `DISPLAY` from the session and `XAUTHORITY` from `/proc/<session-leader-pid>/environ`. On lightdm this is typically `~/.Xauthority` or `/var/run/lightdm/<user>/xauthority` (background, unverified).
  - `systemctl --user import-environment` / `dbus-update-activation-environment --systemd DISPLAY XAUTHORITY WAYLAND_DISPLAY` lets a systemd user service see the graphical session (background).
- **Daemon placement:** prefer a systemd user unit bound to `graphical-session.target` (GNOME/KDE start it; Xfce/lightdm may not activate `graphical-session.target`, so use an XDG autostart `.desktop` entry there; background, unverified). This makes portal app IDs, AT-SPI, and TCC-equivalent consents stable.
- **macOS:** SSH sessions have no WindowServer access to the console user's TCC grants. The daemon must be a LaunchAgent/app in the GUI session (Aqua). **Windows:** SSH (OpenSSH server) runs in session 0/a service context and can't capture or drive the interactive desktop. Use a scheduled task "run only when user is logged on" or a startup-app daemon in the user's session (background, unverified).
- **Alternatives:** a VNC/RDP-backed toolkit (connecting to x11vnc/wayvnc/gnome-remote-desktop/Windows RDP and doing computer-use over the RFB/RDP protocol) gives one uniform driver across OSes, but loses a11y trees and per-window capture. It works better as a fallback mode than as the primary architecture.

### Gaps
- Not verified: lightdm XAUTHORITY path conventions on Debian 13.
- Not verified: whether Xfce 4.20 activates `graphical-session.target`.
- No current (2026) source on GNOME 50 headless + gnome-remote-desktop "remote login" behavior beyond the Lamco GNOME 50 verification.

---

## Recommendation: implementation language and library stack

### Takeaway
**Rust** for the core daemon, MCP server, and CLI (one static binary per OS), with thin per-OS backends and capability probing at runtime. This choice rests on library maturity: Rust has the most-maintained crates for every hard piece:
- WGC/UIA on Windows: windows-rs, windows-capture, uiautomation.
- ScreenCaptureKit/AX/CGEvent on macOS: screencapturekit, objc2 bindings.
- Portals, AT-SPI, and EIS on Linux: ashpd, atspi, zbus, wayland-client, reis/libei bindings.

Nearly all serious 2026 computer-use prior art on Linux/Wayland is in Rust (cua-driver-rs, computer-use-linux, wdotool, Lamco). Python is a reasonable prototyping layer or optional plugin (OCR, quick a11y experiments). Go and Node lack maintained, Wayland-capable, a11y-capable stacks.

### Cited Findings
- Rust components with 2026 activity:
  - xcap 0.9.8 (Aug 2026) — [lib.rs xcap](https://lib.rs/crates/xcap)
  - ashpd 0.13.13 (Jul 2026) — [lib.rs ashpd](https://lib.rs/crates/ashpd)
  - atspi 0.30.0 (May 2026) — [lib.rs atspi](https://lib.rs/crates/atspi)
  - uiautomation (Mar 2026 push) — [gittrend](https://gittrend.io/repo/leexgone/uiautomation-rs)
  - windows-capture (Feb 2026 push, 1.5.0) — [docs.rs](https://docs.rs/windows-capture)
  - screencapturekit 8.0.1 — [docs.rs](https://docs.rs/crate/screencapturekit/8.0.1)
  - enigo (Rust 1.87+, libei experimental) — [GitHub](https://github.com/enigo-rs/enigo)
- Rust computer-use prior art:
  - computer-use-linux (Rust MCP server + CLI, npm wrapper) — [GitHub](https://github.com/agent-sh/computer-use-linux)
  - wdotool (Rust, `wdotool-core` crate) — [GitHub](https://github.com/cushycush/wdotool)
  - cua-driver-rs (Rust port of cua driver) — [newreleases](https://newreleases.io/project/github/trycua/cua/release/cua-driver-rs-v0.6.6)
  - Lamco RDP server (Rust 1.94+) — [Lamco](https://lamco.ai/products/lamco-rdp-server/platforms/)
- Node: nut.js is gated behind paid licenses for prebuilt packages — [nutjs.dev](https://nutjs.dev/docs/getting-started). Go: robotgo's Wayland/libei status is unconfirmed and it has no 2026 release found — [robotgo README](https://github.com/go-vgo/robotgo/blob/master/README.md)
- macOS TCC favors a stable signed .app over interpreter-hosted helpers (Python helper failure on Tahoe) — [cua#870](https://github.com/trycua/cua/issues/870); [openclaw#14138](https://github.com/openclaw/openclaw/issues/14138)

### Inferences
- **Suggested stack:**
  - **Core:** Rust + tokio. MCP via the official Rust MCP SDK (`rmcp`, background, unverified). CLI via clap. The daemon exposes a local socket, and the CLI and MCP server are thin clients.
  - **Windows:**
    - Capture/input/windows: `windows` crate (WGC, DXGI, SendInput, EnumWindows, DPI), or `windows-capture` for WGC.
    - A11y and audio: `uiautomation` for UIA, WASAPI via `windows` or `cpal` (cpal supports loopback on Windows, background).
    - Video: ffmpeg ddagrab subprocess or Media Foundation.
  - **macOS:**
    - Capture: `screencapturekit` crate, or objc2-screen-capture-kit.
    - Input/windows/a11y: `core-graphics` / objc2 for CGEvent, `accessibility-sys` / objc2 for AX (background), and Vision via objc2 for OCR.
    - Packaging: a signed .app bundle with LaunchAgent.
  - **Linux X11:** `x11rb` (XShm, XTest, RandR, EWMH) and `atspi`.
  - **Linux Wayland:**
    - `wayland-client` + `wayland-protocols(-wlr)` for screencopy, ext-image-copy-capture, virtual pointer/keyboard, and foreign-toplevel.
    - `ashpd` for portals, a libei client (`reis`, the pure-Rust EIS crate, background, unverified), and `pipewire` crate for frames and audio.
    - `zbus` for KWin/GNOME/compositor IPC, plus JSON IPC to hyprctl/swaymsg/niri.
  - **Cross-cutting:** `sysinfo`; `image` + `fast_image_resize` for downscaling screenshots to model-friendly sizes; ONNX Runtime (`ort`) + RapidOCR models for portable OCR; ffmpeg (libav* or a subprocess) for clip encoding.
- **Capability-probe architecture:** at startup, detect OS, session type (`XDG_SESSION_TYPE`), compositor (env + `wayland-info`-style registry scan + D-Bus names), and permissions (TCC preflight, UIPI integrity, portal versions). Expose a `capabilities` tool so the harness knows which actions are available (e.g., "window_list: unavailable on sway without IPC socket"). computer-use-linux's backend registry ("reports which one won or why each failed") is a good model.
- **For the user's immediate target (Debian 13 / Xfce / X11):** a Rust X11 backend (x11rb + XTest + EWMH + atspi + ffmpeg x11grab + PulseAudio/PipeWire monitor capture) gets every capability working with no permission prompts. Wayland backends can be added incrementally in this priority order:
  1. GNOME (portal + libei + extension)
  2. KDE (portal + libei + KWin script + ScreenShot2)
  3. wlroots (direct protocols)
- **Python alternative:** fastest to prototype (mss, pywinauto, pyobjc, pyatspi, python-xlib, dbus-next). Costs: packaging (PyInstaller/Nuitka), the macOS TCC subject being the Python binary, and weak Wayland input. TypeScript is viable only as the MCP front-end calling a native daemon.

### Gaps
- Not compared: binary size, startup time, or cross-compilation pain across Rust, Go, and Python packaging.
- Not verified: the 2026 status of the `reis` crate (pure-Rust libei), objc2-screen-capture-kit, or `rmcp`.
