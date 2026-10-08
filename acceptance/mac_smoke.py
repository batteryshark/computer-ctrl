#!/usr/bin/env python3
"""macOS smoke over MCP (run on the Mac): doctor, windows, screenshot, and a TextEdit document it opens itself,
typed into by element, saved with window-targeted keys, verified on disk, then closed.

    python3 acceptance/mac_smoke.py [--cmd "cctl mcp"]

Keys and text are aimed at the test window only (never the focused app), so it is safe to run while working.
"""

import argparse
import sys
import time
import uuid
from pathlib import Path

from phase1 import Mcp, check, results

ASCII = "Mac smoke: plain ASCII. "
UNI = "Unicode: café — 日本語 ✓"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="cctl mcp")
    a = ap.parse_args()
    m = Mcp(a.cmd)
    doc, _, err, _ = m.call("doctor")
    check("doctor", not err, status=doc.get("status"), backend=doc.get("input_backend"), problems=doc.get("problems"))
    tools = {t["name"] for t in m.req("tools/list", {})["tools"]}
    check("personal_profile_hides_run", "run" not in tools)
    wins, _, err, _ = m.call("windows", action="list")
    check("windows_list", not err and len(wins.get("windows", [])) > 0, count=len(wins.get("windows", [])))
    shot, imgs, err, _ = m.call("screenshot", max_dim=1024)
    check("desktop_screenshot", not err and len(imgs) == 1, size=f"{shot.get('width')}x{shot.get('height')}",
          scale=shot.get("scale"))

    path = Path(f"/tmp/cctl-mac-{uuid.uuid4().hex[:6]}.txt")
    path.write_text("")
    before = {w["id"] for w in wins.get("windows", [])}
    m.call("apps", action="launch", name="TextEdit", urls=[str(path)])
    win = None
    for _ in range(20):
        ws, _, _, _ = m.call("windows", action="list")
        win = next((w for w in ws.get("windows", []) if w["id"] not in before and path.name in (w.get("title") or "")),
                   None)
        if win:
            break
        time.sleep(0.5)
    if not check("textedit_window", win is not None):
        return finish(m, None, path)
    obs, _, err, _ = m.call("observe", window=win["id"], windows=False, max_elements=80)
    tok = next((l.split()[0] for l in obs.get("elements", [])
                if l.split()[1:2] in (["AXTextArea"], ["AXTextField"], ["text"]) or " text area" in l), None)
    if not check("text_element", tok is not None, elements=obs.get("elements", [])[:6]):
        return finish(m, win, path)
    r1, _, e1, _ = m.call("type_text", element=tok, text=ASCII)
    check("type_ascii", not e1 and r1.get("verified") is not False, **r1)
    r2, _, e2, _ = m.call("type_text", element=tok, text=UNI)
    check("type_unicode", not e2 and r2.get("verified") is not False, **r2)
    k, _, e3, _ = m.call("menu", window=win["id"], path=["File", "Save"])
    check("menu_save", not e3, result=k)
    time.sleep(1.0)
    check("saved_file", path.read_text(encoding="utf-8", errors="replace") == ASCII + UNI,
          got=repr(path.read_text(encoding="utf-8", errors="replace")))
    return finish(m, win, path)


def finish(m, win, path):
    if win:
        c, _, err, _ = m.call("windows", action="close", window=win["id"])
        check("close_window", not err, result=c)
    path.unlink(missing_ok=True)
    m.p.stdin.close()
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
