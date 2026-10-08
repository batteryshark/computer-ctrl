Additional repro on 0.34.0 with a multi-line GtkTextView (GtkSourceView 4). This answers the version, app and sample-string questions above.

**Environment**
- Cua Driver 0.34.0 (`cua-driver-rs-0.34.0-linux-x86_64`, `serve --no-overlay`, standard mode)
- Debian 13 (trixie), x86_64, Xorg 21.1.16, Xfce 4.20 / xfwm4 4.20.0, at-spi2-core 2.56.2
- GTK 3.24.49, Mousepad 0.6.3 (GtkSourceView 4.8.4 text view), launched fresh with `--disable-server`

**Steps.** These use the same session label on every call, over MCP via the daemon socket.
1. `get_window_state` on the Mousepad window; take the `text` element's `element_token`.
2. `type_text {pid, element_token, text}`, using the default background delivery.
3. Read back via `get_window_state` (element `value`) and via the saved file.

**Results**

| Input | Read back | Tool summary |
|---|---|---|
| `Hello, World! … ünïcödé — 日本語 ✓` (127 chars) | `Hello, World! … ünïcödé —` (121 chars). Truncated at the first CJK char; the saved file matches | `Typed 127 character(s) (via targeted AT-SPI).`, `effect: unverifiable` |
| ` \| 日本語 ✓ é` appended to existing text | nothing inserted, not even the leading ASCII ` \| ` | same shape |

Unlike the GtkEntry case in the report, the GtkTextView result included **no readback warning**. It reported success with `effect: unverifiable` only.

**Controls:** `set_value` with `set_value: ünïcödé — 日本語 ✓ 🙂 end` round-trips exactly (`effect: confirmed`). Clipboard write + `ctrl+v` also preserves the full string, including emoji.
