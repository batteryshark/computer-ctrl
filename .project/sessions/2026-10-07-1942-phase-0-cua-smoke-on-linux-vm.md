# Session: Phase 0 Cua smoke on Linux VM

Date: 2026-10-07 19:42 (VM clock 23:4x UTC)

## Starting context

The user unlocked the VM (light-locker off, DPMS off). `loginctl activate` was used to switch seat0 back to the admin session. Cua Driver 0.34.0 daemon was already running (`serve --no-overlay`).

## Work performed

- Probed Cua interactively with `cua-driver call` over SSH. Helper: `phase0/cua-smoke/cua.py`; it passes args base64-encoded, and `--screenshot-out-file` makes the CLI write images to disk.
- Drove `cua-driver mcp --socket ~/.cache/cua-driver/cua-driver.sock` over SSH with a minimal MCP client (`phase0/cua-smoke/mcp_session.py`).
- Codified the checks into `phase0/cua-smoke/smoke.py`. It uses one MCP connection and only launches its own windows. Test Mousepad runs with throwaway XDG dirs.

## Evidence and results

Final run log: `phase0/cua-smoke/results/20261007-194215.json`. Result: 10 PASS, 1 KNOWN, 9.2 s total.

| Check | Result |
|---|---|
| Desktop capture (1568 cap) | 71 ms CLI; 1568×882, `frame_scale` 1.2245. Black while session locked; `doctor` did not notice |
| `list_apps` | All ~270 processes (incl. non-GUI), no CPU/mem fields |
| a11y tree | Mousepad 20 elements / 30 ms walk; Thunar 303 / 315 ms; Firefox 95 / 94 ms; OpenChamber (Electron) **1 element** |
| `type_text` ASCII by element token | Exact |
| `type_text` Unicode, a11y route | **Silently drops**. Run 1 truncated at the first CJK char yet reported "Typed 127 character(s)". Run 2 inserted nothing |
| `type_text` Unicode, pixel/key route | **Corrupts**: `é 日本 ✓` came out as `✓ ✓✓ ✓` |
| `set_value` Unicode | Exact; Cua itself reads back (`effect: confirmed`) |
| clipboard_write + ctrl+v | Exact Unicode incl. emoji |
| Pixel click on menu bar (#3237) | Lands exactly; **offset not reproduced** on xfwm4 (window frames are client-area) |
| `zoom` | Crop only: 200×25 region returned 240×35 JPEG (20% pad), no magnification; no file-out arg (CLI flag works) |
| `start_recording` video | 1920×1080 H.264 MP4 + per-turn before/after PNG + a11y JSON; 1.7 s start |
| Browser | `browser_prepare` isolated Chromium 0.7 s; navigate OK; `semantic_v2` snapshot: example.com 17 ms / 8 KB, Wikipedia ~3.7 s / 65 KB (~16k tokens, paginated), `query` cuts to ~4 KB |
| `run_actions` | **Not present** in the Linux 0.34.0 tool list |
| #3871 desktop freeze | Not seen |

Other facts:

- MCP `tools/list` is 62 tools / **199 KB of schema (~50k tokens)**.
- Browser snapshot payload is only in `structuredContent`; the text block is a one-line summary.
- Session labels end when their connection closes. Browser target/tab ids are re-minted per bind. In standard mode `kill_app` refuses processes launched from another connection. CLI one-shots therefore can't chain stateful steps; MCP (one connection) can.
- `cua-driver mcp` without `--socket` starts its own runtime with the X11 overlay. With `--socket` it proxies to the daemon.
- Mousepad's crash-restore prompt appeared after test instances were killed. Tests now isolate XDG dirs.

## Decisions and pivots

- Go: Cua is the Linux engine. Clicks, a11y, capture, recording and browser all work on Debian 13 / xfwm4. Text-entry defects have in-engine workarounds.

## Artifacts

- `phase0/cua-smoke/{cua.py,mcp_session.py,smoke.py,results/}`
- `phase0/media-probe/{server.py,run.sh}` (now 7 probes, incl. `probe_structured_only`)

## Open questions

- Does each harness show `structuredContent`-only data to the model? This matters for browser snapshots. The probe covers it once a harness can run.
- Should we file the `type_text` Unicode bug upstream (trycua/cua)? It needs the user's OK, since filing is public.

## Next actions

- Wrapper requirements: see tracker Decisions ("Phase 0 wrapper requirements").
- Get one harness with a vision model running, then run the media probe.
