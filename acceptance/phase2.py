#!/usr/bin/env python3
"""Phase 2 acceptance: screen clips, audio capture/transcription and OCR over MCP, verified in code.

    python3 acceptance/phase2.py [--cmd "cctl --host user@linux-vm mcp"]

Audio is produced on the target with espeak-ng + paplay, so the system-audio path is exercised end to end.
"""

import argparse
import base64
import io
import json
import sys
import time
import uuid

from phase1 import Mcp, check, results

WORD = "pineapple"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="cctl mcp")
    a = ap.parse_args()
    m = Mcp(a.cmd)
    d = f"/tmp/cctl-p2-{uuid.uuid4().hex[:6]}"
    m.call("run", command=f"mkdir -p {d}/c {d}/d {d}/s {d}/k && : > {d}/n.txt")
    launched, _, err, _ = m.call("apps", action="launch", name="env", args=[
        f"XDG_CONFIG_HOME={d}/c", f"XDG_DATA_HOME={d}/d", f"XDG_STATE_HOME={d}/s", f"XDG_CACHE_HOME={d}/k",
        "mousepad", "--disable-server", f"{d}/n.txt"])
    wid, pid = launched["windows"][0]["id"], launched["pid"]

    # --- clip around typing
    st, _, err, _ = m.call("record_clip", action="start", window=wid, fps=10)
    check("clip_start", not err and st.get("recording"), clip=st.get("clip"))
    obs, _, _, _ = m.call("observe", window=wid, query="text", windows=False)
    tok = next(line.split()[0] for line in obs["elements"] if line.split()[1:2] == ["text"])
    for word in ("Contact ", "sheet ", "shows ", "typing ", "over ", "time"):
        m.call("type_text", element=tok, text=word)
        obs, _, _, _ = m.call("observe", window=wid, query="text", windows=False)
        tok = next(line.split()[0] for line in obs["elements"] if line.split()[1:2] == ["text"])
        time.sleep(0.3)
    sp, imgs, err, _ = m.call("record_clip", action="stop", frames=6)
    check("clip_stop_sheet", not err and len(imgs) == 1 and sp.get("duration_s", 0) > 1,
          duration=sp.get("duration_s"), path=sp.get("path"))
    check("clip_detects_change", bool(sp.get("most_change")),
          changes=[t["changed"] for t in sp.get("timeline", [])])

    bc, bimgs, err, _ = m.call("record_clip", seconds=2, region=[0, 0, 640, 360], frames=4)
    check("clip_blocking_region", not err and len(bimgs) == 1 and 1.5 <= bc.get("duration_s", 0) <= 2.5,
          duration=bc.get("duration_s"))

    # --- OCR on the window, boxes usable for clicks
    shot, _, _, _ = m.call("screenshot", window=wid)
    o, _, err, _ = m.call("ocr", frame=shot["frame"], words=True)
    line = next((l for l in o.get("lines", []) if "Contact sheet" in l), None)
    check("ocr_reads_typed_text", not err and line is not None, line=line and line[:80])
    blob = "\n".join(o.get("lines", []))
    at = blob.find('"Help"[') if '"Help"[' in blob else blob.find('"Help" [')
    if at >= 0:
        start = blob.index("[", at)
        x0, y0, x1, y1 = json.loads(blob[start:blob.index("]", start) + 1])
        m.call("click", x=(x0 + x1) / 2, y=(y0 + y1) / 2, frame=o["frame"])
        time.sleep(0.4)
        menu, _, _, _ = m.call("observe", window=wid, query="About", windows=False)
        m.call("key", keys="Escape")
        check("ocr_word_box_clickable", any("About" in l for l in menu.get("elements", [])))
    else:
        check("ocr_word_box_clickable", False, reason="no Help word", lines=o.get("lines", [])[:3])

    # --- audio: silence, then speech played on the system output
    sil, _, err, _ = m.call("audio_capture", seconds=1.5)
    check("audio_silence_detected", not err and sil.get("silent") is True, rms=sil.get("rms_dbfs"))

    cap, _, err, _ = m.call("audio_capture", action="start")
    check("audio_start", not err and cap.get("recording"), device=cap.get("device"))
    m.call("run", command=f"espeak-ng -s 140 -w {d}/say.wav 'The secret word is {WORD}.' && paplay {d}/say.wav")
    time.sleep(0.5)
    au, aimgs, err, raw = m.call("audio_capture", action="stop", transcribe=True, waveform=True)
    check("audio_sound_detected", not err and au.get("silent") is False, sound=au.get("sound"),
          peak=au.get("peak_dbfs"))
    check("audio_transcribed", WORD in (au.get("transcript") or "").lower(), transcript=au.get("transcript"),
          backend=(au.get("transcript_info") or {}).get("backend"))
    check("audio_waveform_image", len(aimgs) == 1)

    inl, _, err, raw = m.call("audio_capture", seconds=1, inline=True)
    kinds = [c["type"] for c in raw.get("content", [])]
    check("audio_inline_content", not err and "audio" in kinds, content=kinds)

    m.call("apps", action="quit", pid=pid)
    m.call("run", command=f"pkill -f '[m]ousepad --disable-server {d}'; rm -rf {d}")
    m.p.stdin.close()
    m.p.wait(timeout=10)
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
