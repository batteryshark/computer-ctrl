#!/usr/bin/env python3
"""Clip-with-audio smoke (macOS / Windows), through the CLI.

Opens its own browser window on web/av_sync.html, which flashes white and plays a tone together once a second. The
window runs in a throwaway Chromium profile with autoplay allowed. The test records that window with
record_clip audio=true, then checks:
  - the MP4 has an audio track, and it has sound;
  - the result's audio summary agrees;
  - the flashes and the tones line up: the A/V offset is measured from the MP4 itself.
Only touches the window it opens.

    python3 acceptance/clip_audio_smoke.py                                    # this Mac
    python3 acceptance/clip_audio_smoke.py --host user@windows-pc --home 'C:\\Users\\<user>'
"""

import argparse
import array
import json
import math
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from phase1 import check, results

HERE = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FLAGS = ["--no-first-run", "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required",
         "--window-position=120,120", "--window-size=520,360"]


def cctl(host, tool, **args):
    cmd = ["cctl", *(["--host", host] if host else []), tool, json.dumps(args)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"error": "bad_output", "stdout": p.stdout[-400:], "stderr": p.stderr[-400:]}


def find_window(host, before, title="cctl av sync"):
    for _ in range(30):
        ws = cctl(host, "windows", action="list").get("windows", [])
        w = next((w for w in ws if w["id"] not in before and title in (w.get("title") or "")), None)
        if w:
            return w
        time.sleep(0.5)
    return None


def video_onsets(mp4):
    """Times the picture turns bright (flash on), from per-frame average luma."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-an", "-vf",
                          "signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", out)]
    yavg = [float(v) for v in re.findall(r"YAVG=([\d.]+)", out)]
    if not yavg:
        return []
    mid = (min(yavg) + max(yavg)) / 2
    return [t for i, (t, y) in enumerate(zip(times, yavg)) if i and y > mid and yavg[i - 1] <= mid]


def audio_onsets(mp4, tmp):
    """Times a tone starts, from 5 ms RMS windows of the soundtrack."""
    wav = Path(tmp) / "a.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4), "-vn", "-ac", "1", "-ar",
                    "16000", "-c:a", "pcm_s16le", str(wav)], check=True)
    with wave.open(str(wav)) as w:
        s = array.array("h", w.readframes(w.getnframes()))
    step = 80  # 5 ms
    rms = [math.sqrt(sum(x * x for x in s[i:i + step]) / step) for i in range(0, len(s) - step, step)]
    if not rms or max(rms) == 0:
        return []
    thr, onsets, last = max(rms) * 0.25, [], -1.0
    for i, r in enumerate(rms):
        t = i * step / 16000
        if r > thr and (i == 0 or rms[i - 1] <= thr) and t - last > 0.5:
            onsets.append(t)
            last = t
    return onsets


def pair_offsets(flashes, tones, tol=0.06):
    """Audio-minus-video offset per flash, under the single shift that pairs up the most flashes with tones (the
    page's intervals are irregular, so only the true shift lines the sequences up)."""
    def fit(shift):
        return [a - t for t in flashes for a in tones if abs(a - t - shift) < tol]
    shifts = [a - t for t in flashes for a in tones if abs(a - t) < 1.0]
    if not shifts:
        return []
    best = max(shifts, key=lambda sh: (len(fit(sh)), -abs(sh)))
    return sorted(round(o, 3) for o in fit(best))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", help="remote Windows host (user@host) driven through cctl --host")
    ap.add_argument("--home", help="Windows: the user's home on the host (where computer-ctrl/ is deployed)")
    a = ap.parse_args()
    before = {w["id"] for w in cctl(a.host, "windows", action="list").get("windows", [])}
    tmp = tempfile.mkdtemp(prefix="cctl-avsync-")
    browser, pid = None, None
    if a.host:
        page = f"{a.home}\\computer-ctrl\\acceptance\\web\\av_sync.html"
        prof = f"{a.home}\\AppData\\Local\\Temp\\cctl-avsync"
        la = cctl(a.host, "apps", action="launch", name="msedge.exe",
                  args=[f"--user-data-dir={prof}", *FLAGS, "--app=file:///" + page.replace("\\", "/")])
        pid = la.get("pid")
    else:
        browser = subprocess.Popen([CHROME, f"--user-data-dir={tmp}/profile", *FLAGS,
                                    f"--app=file://{HERE / 'web' / 'av_sync.html'}"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    win = find_window(a.host, before)
    if not check("test_window", win is not None):
        return finish(a, win, browser, pid)
    time.sleep(1.5)  # let the page start ticking

    st = cctl(a.host, "record_clip", action="start", window=win["id"], fps=30, audio=True)
    check("clip_start", st.get("recording"), detail=st)
    time.sleep(4.5)
    sp = cctl(a.host, "record_clip", action="stop", frames=9)
    au = sp.get("audio") or {}
    check("clip_stop", sp.get("duration_s", 0) > 3 and sp.get("has_audio"), duration=sp.get("duration_s"),
          has_audio=sp.get("has_audio"), error=sp.get("message"))
    check("audio_summary", au.get("silent") is False and len(au.get("sound", [])) >= 3,
          peak=au.get("peak_dbfs"), sound=au.get("sound"))
    mp4 = Path(sp.get("path", ""))
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,duration",
                              "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout.split()
    check("mp4_streams", any(s.startswith("aac,audio") for s in streams) and any("video" in s for s in streams),
          streams=streams)
    v, s = video_onsets(mp4), audio_onsets(mp4, tmp)
    offs = pair_offsets(v, s)
    med = offs[len(offs) // 2] if offs else None
    check("av_sync", len(offs) >= 3 and abs(med) <= 0.15, flashes=[round(t, 2) for t in v],
          tones=[round(t, 2) for t in s], offsets_s=offs, median_s=med)
    return finish(a, win, browser, pid)


def finish(a, win, browser, pid):
    if win:
        q = cctl(a.host, "windows", action="close", window=win["id"])
        check("close_window", "error" not in q, result=q)
    if browser:
        browser.terminate()
    elif pid:  # the throwaway Edge profile may linger in the background
        time.sleep(1)
        cctl(a.host, "processes", action="kill", pid=pid)
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
