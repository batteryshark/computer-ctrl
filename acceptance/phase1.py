#!/usr/bin/env python3
"""Phase 1 acceptance: drive `cctl mcp` over MCP stdio and edit+save a file in Mousepad, verified in code.

    python3 acceptance/phase1.py                                    # on the target machine
    python3 acceptance/phase1.py --cmd "ssh -T user@linux-vm ~/.local/bin/cctl mcp"   # from anywhere

Exits non-zero on any failure. Only touches windows and files it creates.
"""

import argparse
import json
import shlex
import subprocess
import sys
import time
import uuid

TEXT_ASCII = "Phase 1 acceptance: plain ASCII. "
TEXT_UNICODE = "Unicode: café — 日本語 ✓ 🙂"


class Mcp:
    def __init__(self, cmd: str):
        self.p = subprocess.Popen(shlex.split(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                  bufsize=1)
        self.n = 0
        init = self.req("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "phase1-acceptance", "version": "1"}})
        self.instructions = init.get("instructions", "")
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

    def req(self, method, params):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("server exited")
            msg = json.loads(line)
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def call(self, tool, **args):
        r = self.req("tools/call", {"name": tool, "arguments": args})
        texts = [c["text"] for c in r["content"] if c["type"] == "text"]
        images = [c for c in r["content"] if c["type"] == "image"]
        data = json.loads(texts[0]) if texts else {}
        return data, images, bool(r.get("isError")), r


results = []


def check(name, ok, **detail):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name} " + " ".join(f"{k}={v}" for k, v in detail.items()), flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="cctl mcp")
    a = ap.parse_args()
    m = Mcp(a.cmd)
    run_id = uuid.uuid4().hex[:6]
    d = f"/tmp/cctl-acc-{run_id}"
    note = f"{d}/note.txt"

    tools = [t["name"] for t in m.req("tools/list", {})["tools"]]
    check("tools_listed", {"doctor", "observe", "screenshot", "zoom", "click", "type_text"} <= set(tools),
          count=len(tools))
    sizes = [t for t in m.req("tools/list", {})["tools"]]
    check("schema_compact", len(json.dumps(sizes)) < 30000, bytes=len(json.dumps(sizes)))

    doc, _, err, _ = m.call("doctor")
    check("doctor_ok", not err and doc.get("status") == "ok", problems=doc.get("problems"))

    # Prepare an isolated editor (throwaway XDG dirs so the user's Mousepad state is untouched).
    m.call("run", command=f"mkdir -p {d}/c {d}/d {d}/s {d}/k && : > {note}")
    launched, _, err, _ = m.call("apps", action="launch", name="env", args=[
        f"XDG_CONFIG_HOME={d}/c", f"XDG_DATA_HOME={d}/d", f"XDG_STATE_HOME={d}/s", f"XDG_CACHE_HOME={d}/k",
        "mousepad", "--disable-server", note])
    wins = launched.get("windows") or []
    if not check("launch_editor", not err and bool(wins), pid=launched.get("pid")):
        return
    wid, pid = wins[0]["id"], launched["pid"]
    m.call("windows", action="focus", window=wid)

    obs, _, err, _ = m.call("observe", window=wid, query="text", windows=False)
    tok = next((line.split()[0] for line in obs.get("elements", []) if line.split()[1:2] == ["text"]), None)
    check("observe_text_element", bool(tok), token=tok)

    r1, _, e1, _ = m.call("type_text", element=tok, text=TEXT_ASCII)
    check("type_ascii_verified", not e1 and r1.get("verified") is True and r1.get("route") == "keys", **r1)
    r2, _, e2, _ = m.call("type_text", element=tok, text=TEXT_UNICODE)
    check("type_unicode_verified", not e2 and r2.get("verified") is True and r2.get("route") == "paste", **r2)

    m.call("key", keys="ctrl+s")
    time.sleep(0.5)
    out, _, _, _ = m.call("run", command=f"cat {note}")
    check("file_saved_exactly", out.get("stdout") == TEXT_ASCII + TEXT_UNICODE, got=repr(out.get("stdout")))

    shot, imgs, err, raw = m.call("screenshot", window=wid)
    check("screenshot_one_image_no_structured", not err and len(imgs) == 1 and "structuredContent" not in raw,
          frame=shot.get("frame"), size=f"{shot.get('width')}x{shot.get('height')}")

    zoom, zimgs, err, _ = m.call("zoom", region=[0, 0, 320, 25], frame=shot["frame"])
    check("zoom_magnifies", not err and len(zimgs) == 1 and zoom.get("magnification", 0) > 1.5,
          magnification=zoom.get("magnification"), size=f"{zoom.get('width')}x{zoom.get('height')}")

    # Click "Help" on the zoomed image by pixel; the menu popup must appear.
    obs2, _, _, _ = m.call("observe", window=wid, query="Help", windows=False)
    help_line = next((line for line in obs2.get("elements", []) if '"Help"' in line), "")
    x0, y0, x1, y1 = json.loads(help_line[help_line.rindex("["):]) if help_line else (0, 0, 0, 0)
    zx, zy = zoom["screen_origin"]
    zs = zoom["scale"]
    click, _, err, _ = m.call("click", x=((x0 + x1) / 2 - zx) / zs, y=((y0 + y1) / 2 - zy) / zs, frame=zoom["frame"])
    time.sleep(0.4)
    menu, _, _, _ = m.call("observe", window=wid, query="About", windows=False)
    m.call("key", keys="Escape")
    check("pixel_click_from_zoom_opens_menu", not err and any("About" in line for line in menu.get("elements", [])),
          clicked=click.get("clicked"))

    procs, _, err, _ = m.call("processes", action="list", filter="mousepad")
    check("processes_lists_editor", any(p["pid"] == pid for p in procs.get("processes", [])))

    q, _, err, _ = m.call("apps", action="quit", pid=pid)
    check("quit_editor", not err and q.get("exited") is True, **q)

    bad, _, err, _ = m.call("click", x=1, y=1, frame="nope")
    check("errors_are_actionable", err and bad.get("error") == "no_frame" and "message" in bad)

    m.call("run", command=f"rm -rf {d}")
    m.p.stdin.close()
    m.p.wait(timeout=10)
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
