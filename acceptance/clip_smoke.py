#!/usr/bin/env python3
"""Screen-clip smoke (macOS / Windows): record a window this test opens while its content changes, then check
the contact sheet and per-frame OCR (text_changes) show the change. Only touches windows it opens itself.

    python3 acceptance/clip_smoke.py --app textedit [--cmd "cctl mcp"]
    python3 acceptance/clip_smoke.py --app calc --cmd "ssh ... user@windows-pc cctl mcp"
"""

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from phase1 import Mcp, check, results


def new_window(m, before, match):
    for _ in range(20):
        ws, _, _, _ = m.call("windows", action="list")
        w = next((w for w in ws.get("windows", []) if w["id"] not in before and match(w)), None)
        if w:
            return w
        time.sleep(0.5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", choices=["textedit", "calc"], required=True)
    ap.add_argument("--cmd", default="cctl mcp")
    a = ap.parse_args()
    m = Mcp(a.cmd)
    ws, _, _, _ = m.call("windows", action="list")
    before = {w["id"] for w in ws.get("windows", [])}
    path = None
    if a.app == "textedit":
        path = Path(f"/tmp/cctl-clip-{uuid.uuid4().hex[:6]}.txt")
        path.write_text("")
        m.call("apps", action="launch", name="TextEdit", urls=[str(path)])
        win = new_window(m, before, lambda w: path.name in (w.get("title") or ""))
        if win:  # put it where it is visible; a brief activation by the test itself (not by cctl)
            m.call("windows", action="move", window=win["id"], x=200, y=200, width=700, height=300)
            subprocess.run(["osascript", "-e", 'tell application "TextEdit" to activate'], check=False)
            time.sleep(0.5)
            ws, _, _, _ = m.call("windows", action="list")
            win = next((w for w in ws.get("windows", []) if w["id"] == win["id"]), win)  # bounds after the move
    else:
        m.call("apps", action="launch", name="calc.exe")
        win = new_window(m, before, lambda w: "calc" in f"{w.get('app')} {w.get('title')}".lower())
    if not check("test_window", win is not None):
        return finish(m, None, path)

    st, _, err, _ = m.call("record_clip", action="start", window=win["id"], fps=6)
    check("clip_start", not err and st.get("recording"), detail=st if err else st.get("clip"))
    time.sleep(1.0)
    if a.app == "textedit":
        obs, _, _, _ = m.call("observe", window=win["id"], windows=False, max_elements=20)
        tok = next(l.split()[0] for l in obs["elements"] if "AXTextArea" in l)
        for word in ("CLIP", "TEST", "WORKS"):
            m.call("type_text", element=tok, text=word + " ")
            obs, _, _, _ = m.call("observe", window=win["id"], windows=False, max_elements=20)
            tok = next(l.split()[0] for l in obs["elements"] if "AXTextArea" in l)
            time.sleep(0.8)
        expect = ["CLIP", "WORKS"]
    else:
        for digit in "789":  # typed digits work in every Calculator mode; aimed at its window only
            r, _, kerr, _ = m.call("key", keys=digit, window=win["id"])
            if kerr:
                check(f"press_{digit}", False, error=r)
            time.sleep(0.8)
        expect = ["7", "789"]
    time.sleep(0.8)
    sp, imgs, err, _ = m.call("record_clip", action="stop", frames=8, ocr=True)
    check("clip_stop_sheet", not err and len(imgs) == 1 and sp.get("duration_s", 0) > 2,
          duration=sp.get("duration_s"), error=sp.get("message") if err else None)
    texts = " | ".join(c.get("text", "") for c in sp.get("text_changes", []))
    check("clip_shows_change", all(e in texts.replace(" ", "").replace(",", "") or e in texts for e in expect),
          text_changes=texts[:300])
    check("clip_cropped_to_window", sp.get("screen_rect") == win["bounds"], rect=sp.get("screen_rect"),
          window=win["bounds"])
    return finish(m, win, path)


def finish(m, win, path):
    if win:
        m.call("windows", action="close", window=win["id"])
        if path:  # TextEdit may ask to save the edited untitled-ish doc; it's a temp file, so dismiss by saving
            time.sleep(0.5)
    if path:
        path.unlink(missing_ok=True)
    m.p.stdin.close()
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
