# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""Phase 0 acceptance smoke for Cua Driver on the Linux VM, over MCP via SSH.

Runs in one MCP connection (session-scoped ids live only that long) against the
daemon socket, using only windows and browsers it launches itself.

    uv run --script phase0/cua-smoke/smoke.py            # CUA_HOST=user@linux-vm by default

Each check prints PASS / FAIL / KNOWN (a known upstream defect we work around in
the wrapper). A JSON log goes to phase0/cua-smoke/results/<timestamp>.json.
"""

import base64
import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

from PIL import Image, ImageStat

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("CUA_MCP_CMD", "DISPLAY=:0 DO_NOT_TRACK=1 ~/.local/bin/cua-driver mcp "
                                     "--socket ~/.cache/cua-driver/cua-driver.sock")
from cua import sh  # noqa: E402
from mcp_session import Session  # noqa: E402

S = "smoke-" + uuid.uuid4().hex[:6]
results = []


def record(name, status, **detail):
    results.append({"check": name, "status": status, **detail})
    extra = " ".join(f"{k}={v}" for k, v in detail.items() if k != "raw")
    print(f"{status:5s} {name}  {extra}")


def raw_call(s, tool, args):
    """tools/call returning the raw MCP result (images included)."""
    return s.request("tools/call", {"name": tool, "arguments": {"session": S, **args}})


def data(r):
    if r.get("structuredContent"):
        return r["structuredContent"]
    for c in r.get("content", []):
        if c["type"] == "text":
            try:
                return json.loads(c["text"])
            except json.JSONDecodeError:
                return {"text": c["text"]}
    return {}


def image(r):
    for c in r.get("content", []):
        if c["type"] == "image":
            return Image.open(io.BytesIO(base64.b64decode(c["data"])))
    return None


def text_value(s, pid, wid, wait_s=8.0):
    """Token and current value of the window's text area, polling while the window finishes mapping."""
    deadline = time.monotonic() + wait_s
    while True:
        st = data(raw_call(s, "get_window_state", {"pid": pid, "window_id": wid, "include_screenshot": False}))
        el = next((e for e in st.get("elements", []) if e.get("role") == "text"), None)
        if el or time.monotonic() > deadline:
            break
        time.sleep(0.5)
    if el is None:
        raise RuntimeError(f"no text element in window {wid}: {str(st)[:300]}")
    return el["element_token"], el.get("value") or ""


def window_of(s, pid, title_part, wait_s=8.0):
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        ws = data(raw_call(s, "list_windows", {"pid": pid})).get("windows", [])
        hit = next((w for w in ws if title_part in (w.get("title") or "")), None)
        if hit:
            return hit["window_id"]
        time.sleep(0.5)
    raise RuntimeError(f"no window with {title_part!r} for pid {pid}")


def main():
    s = Session()
    t0 = time.monotonic()

    # Display is live (a locked session or DPMS-off monitor yields black frames).
    r = raw_call(s, "get_desktop_state", {"max_image_dimension": 1568})
    img = image(r)
    mean = sum(ImageStat.Stat(img.convert("L")).mean) if img else 0
    record("desktop_capture_not_black", "PASS" if img and mean > 5 else "FAIL",
           size=img.size if img else None, mean_luma=round(mean, 1))

    apps = data(raw_call(s, "list_apps", {}))
    apps = apps.get("apps", apps) if isinstance(apps, dict) else apps
    running = [a for a in apps if a.get("running")]
    record("list_apps_includes_non_gui", "PASS" if any(a.get("name") == "systemd" for a in running) else "FAIL",
           running=len(running))

    # Isolated Mousepad on a scratch file.
    # Throwaway XDG dirs keep the test editor's session/restore state away from the user's own Mousepad.
    x = f"/tmp/{S}"
    sh(f"mkdir -p {x}/config {x}/data {x}/state {x}/cache && : > {x}/typing.txt")
    la = data(raw_call(s, "launch_app", {"name": "env", "additional_arguments": [
        f"XDG_CONFIG_HOME={x}/config", f"XDG_DATA_HOME={x}/data", f"XDG_STATE_HOME={x}/state",
        f"XDG_CACHE_HOME={x}/cache", "mousepad", "--disable-server", "--opening-mode=window", f"{x}/typing.txt"]}))
    pid = la["pid"]
    wid = window_of(s, pid, "Mousepad")
    tok, _ = text_value(s, pid, wid)
    record("a11y_text_element_found", "PASS", pid=pid, window_id=wid)

    ascii_text = "ASCII ok: ~`!@#$%^&*()_+-={}[]|\\:;\"'<>,.?/"
    raw_call(s, "type_text", {"pid": pid, "element_token": tok, "text": ascii_text})
    tok, v = text_value(s, pid, wid)
    record("type_text_ascii", "PASS" if v == ascii_text else "FAIL", got=len(v), want=len(ascii_text))

    uni = " | 日本語 ✓ é"
    raw_call(s, "type_text", {"pid": pid, "element_token": tok, "text": uni})
    tok, v2 = text_value(s, pid, wid)
    record("type_text_unicode", "PASS" if v2 == v + uni else "KNOWN",
           note="type_text drops/corrupts non-Latin-1 while reporting success", tail=repr(v2[len(v):]))

    target = "set_value: 日本語 ✓ 🙂"
    raw_call(s, "set_value", {"pid": pid, "element_token": tok, "value": target})
    tok, v3 = text_value(s, pid, wid)
    record("set_value_unicode", "PASS" if v3 == target else "FAIL", got=repr(v3))

    raw_call(s, "clipboard_write", {"text": " | paste: 日本 ✓"})
    raw_call(s, "hotkey", {"pid": pid, "window_id": wid, "keys": ["ctrl", "v"]})
    time.sleep(0.4)
    tok, v4 = text_value(s, pid, wid)
    record("clipboard_paste_unicode", "PASS" if v4.endswith(" | paste: 日本 ✓") else "FAIL", got=repr(v4[-20:]))

    # Pixel click on the Help menu (#3237 title-bar offset check).
    st = data(raw_call(s, "get_window_state", {"pid": pid, "window_id": wid}))
    help_el = next(e for e in st["elements"] if e.get("role") == "menu" and e.get("label") == "Help")
    f = help_el["screenshot_frame"]
    c = raw_call(s, "click", {"pid": pid, "window_id": wid, "x": f["x"] + f["w"] / 2, "y": f["y"] + f["h"] / 2,
                              "capture_id": st["capture_id"]})
    summary = " ".join(x.get("text", "") for x in c.get("content", []))
    record("pixel_click_menu_bar", "PASS" if "menu" in summary and "Help" in json.dumps(help_el) else "FAIL",
           summary=summary[:120])
    raw_call(s, "press_key", {"pid": pid, "window_id": wid, "key": "Escape"})

    z = raw_call(s, "zoom", {"pid": pid, "window_id": wid, "x1": 0, "y1": 25, "x2": 200, "y2": 50})
    zi = image(z)
    record("zoom_returns_crop", "PASS" if zi else "FAIL", size=zi.size if zi else None,
           note="crop only, no magnification")

    rec_dir = f"/tmp/smoke-rec-{S}"
    raw_call(s, "start_recording", {"output_dir": rec_dir, "record_video": True})
    time.sleep(2)
    raw_call(s, "stop_recording", {})
    dur = sh(f"ffprobe -v error -show_entries format=duration -of csv=p=0 {rec_dir}/recording.mp4").stdout.strip()
    record("record_video_mp4", "PASS" if dur and float(dur) > 1 else "FAIL", duration_s=dur)

    # Isolated browser via CDP.
    p = data(raw_call(s, "browser_prepare", {"allow_launch": True, "profile": {"mode": "isolated_new"}}))
    bpid = p["prepared_pid"]
    bwid = window_of(s, bpid, "Chromium")
    b = data(raw_call(s, "get_browser_state", {"pid": bpid, "window_id": bwid}))
    nav = data(raw_call(s, "browser_navigate", {"target_id": b["target_id"], "tab_id": b["tabs"][0]["tab_id"],
                                                "url": "https://example.com"}))
    time.sleep(1.5)
    t1 = time.monotonic()
    snap = raw_call(s, "get_browser_state", {"target_id": b["target_id"], "tab_id": nav["tab_id"],
                                             "snapshot_format": "semantic_v2"})
    sd = snap.get("structuredContent") or {}
    text_chars = sum(len(c.get("text", "")) for c in snap.get("content", []))
    record("browser_semantic_snapshot", "PASS" if sd.get("page", {}).get("title") == "Example Domain" else "FAIL",
           ms=round((time.monotonic() - t1) * 1000), structured_bytes=len(json.dumps(sd)), text_chars=text_chars)

    for victim in (pid, bpid):
        raw_call(s, "kill_app", {"pid": victim})
    s.close()
    print(f"total {time.monotonic() - t0:.1f}s")

    out = HERE / "results" / time.strftime("%Y%m%d-%H%M%S.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"session": S, "server": "cua-driver 0.34.0", "results": results}, indent=2,
                              ensure_ascii=False))
    print("log:", out.relative_to(HERE.parent.parent))
    sys.exit(1 if any(r["status"] == "FAIL" for r in results) else 0)


if __name__ == "__main__":
    main()
