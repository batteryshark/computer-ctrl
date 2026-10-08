### Primary area

Cua Driver

### Summary

On Linux/X11, `type_text` delivered as real key events (`route: global_input`, `path=mpx_uinput`) types every non-ASCII character as the **last** non-ASCII character in the string, and reports success. ASCII characters in the same call are correct.

This is a different path from #4754, which covers the AT-SPI route. The output looks like the spare-keycode remap from #2314 being observed after it has already been rebound for a later character, but we have not confirmed the cause.

### Reproduction

Deterministic: 3/3 strings, plus one earlier run.

1. Launch a GTK3 text editor: `mousepad --disable-server /tmp/t.txt`, a fresh instance with empty XDG dirs.
2. `get_window_state {pid, window_id}`, then `click` at a pixel inside the text view (x=300, y=37, with the returned `capture_id`) to place the caret.
3. `type_text {pid, window_id, x: 300, y: 37, text: <string>}` with default (background) delivery.
4. Read the text view's `value` via `get_window_state`; the saved file matches.

### Expected behavior

The text view contains exactly the input string. If a character cannot be delivered, the tool should return an error rather than success.

### Actual behavior

| Sent | Got |
|---|---|
| `Привет` | `тттттт` |
| `x→y←z` | `x←y←z` |
| `aé b日 c✓ d` | `✓a✓ b✓ c✓ d` (an extra `✓` also appeared at the start in this run) |
| `\| px-typed ASCII ok; é 日本 ✓` | `\| px-typed ASCII ok; ✓ ✓✓ ✓` |

Each call returns:

```json
{"delivery": {"mode": "background"}, "effect": "unverifiable", "route": "global_input",
 "summary": "Typed 6 character(s) as real key events through a virtual master keyboard (path=mpx_uinput, focus untouched) (delivery_mode=background); not verified — confirm with a screenshot."}
```

The keyboard layout is a plain `us`/`pc105` evdev map. `set_value`, and clipboard write + `ctrl+v`, both deliver the same strings correctly.

### Environment

- Cua component and version/commit: Cua Driver 0.34.0 (`cua-driver-rs-0.34.0-linux-x86_64` release tarball), daemon `serve --no-overlay`, standard permission mode, calls over MCP through the daemon socket
- Operating system and architecture: Debian 13 (trixie), x86_64, kernel 6.12
- Application/browser/window system/image: Xorg 21.1.16, Xfce 4.20 / xfwm4 4.20.0, Mousepad 0.6.3 (GTK 3.24.49, GtkSourceView 4.8.4), XKB `evdev`/`pc105`/`us`
