#!/usr/bin/env python3
"""Grounding accuracy of `locate`, scored against accessibility bounds (ground truth) on live apps.

    python3 eval/grounding_bench.py [--cmd "cctl mcp"] [--no-refine]

Opens a few apps the toolkit controls, takes a desktop screenshot, asks `locate` for every labeled
button / menu / tab / check box, and counts a hit when the point falls inside the element's bounds.
Prints accuracy and latency; writes eval/results/<ts>-grounding.json.
"""

import argparse
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "acceptance"))
from phase1 import Mcp  # noqa: E402

ROLES = {"push button", "button", "menu", "menu item", "check box", "radio button", "page tab", "toggle button",
         "combo box", "link"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="cctl mcp")
    ap.add_argument("--no-refine", action="store_true")
    ap.add_argument("--max", type=int, default=40)
    a = ap.parse_args()
    m = Mcp(a.cmd)
    d = f"/tmp/cctl-gb-{uuid.uuid4().hex[:6]}"
    m.call("run", command=f"mkdir -p {d}/c {d}/d {d}/s {d}/k {d}/files/sub && : > {d}/n.txt")
    pids = []
    for name, args in (("env", [f"XDG_CONFIG_HOME={d}/c", f"XDG_DATA_HOME={d}/d", f"XDG_STATE_HOME={d}/s",
                                f"XDG_CACHE_HOME={d}/k", "mousepad", "--disable-server", f"{d}/n.txt"]),
                       ("galculator", [])):
        r, _, _, _ = m.call("apps", action="launch", name=name, args=args)
        pids.append(r["pid"])
        time.sleep(1.5)
    cases = []
    for pid in pids:
        wins, _, _, _ = m.call("windows", action="list")
        win = next(w for w in wins["windows"] if w["pid"] == pid)
        m.call("windows", action="focus", window=win["id"])
        obs, _, _, _ = m.call("observe", window=win["id"], windows=False, max_elements=300)
        shot, _, _, _ = m.call("screenshot")  # desktop frame: what is actually visible
        k = shot["scale"]
        for line in obs["elements"]:
            parts = line.split()
            role = " ".join(p for p in parts[1:3] if not p.startswith('"'))
            if '"' not in line or "[" not in line:
                continue
            label = line[line.index('"') + 1:line.index('"', line.index('"') + 1)]
            role = line.split('"')[0].split(None, 1)[1].strip()
            if role not in ROLES or not label.strip():
                continue
            x0, y0, x1, y1 = json.loads(line[line.rindex("["):])  # screen coords (bounds_frame=screen)
            if (x1 - x0) < 4 or (y1 - y0) < 4:
                continue
            cases.append({"app": win["app"], "role": role, "label": label, "screen": [x0, y0, x1, y1],
                          "frame": shot["frame"], "k": k})
    cases = cases[:a.max]
    hits, lat = 0, []
    for c in cases:
        t0 = time.monotonic()
        r, _, err, _ = m.call("locate", target=f'the "{c["label"]}" {c["role"]} in {c["app"]}', frame=c["frame"],
                              refine=not a.no_refine, mark=False)
        lat.append(time.monotonic() - t0)
        if err:
            c["error"] = r
            continue
        sx, sy = r["x"] * c["k"], r["y"] * c["k"]  # frame -> screen (desktop frame origin is 0,0)
        x0, y0, x1, y1 = c["screen"]
        c["hit"] = x0 <= sx <= x1 and y0 <= sy <= y1
        c["point"] = [round(sx), round(sy)]
        hits += c["hit"]
        print(f"{'HIT ' if c['hit'] else 'MISS'} {c['app']:10s} {c['role']:12s} {c['label'][:28]:28s} "
              f"point={c['point']} box={c['screen']} {lat[-1]:.1f}s", flush=True)
    for pid in pids:
        m.call("processes", action="kill", pid=pid)
    m.call("run", command=f"rm -rf {d}")
    n = len(cases)
    summary = {"cases": n, "hits": hits, "accuracy": round(hits / n, 3) if n else None,
               "refine": not a.no_refine, "latency_median_s": round(statistics.median(lat), 2) if lat else None,
               "latency_p90_s": round(sorted(lat)[int(0.9 * (len(lat) - 1))], 2) if lat else None}
    print(json.dumps(summary))
    out = Path(__file__).resolve().parent / "results" / time.strftime("%Y%m%d-%H%M%S-grounding.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "cases": cases}, indent=1, ensure_ascii=False))
    m.p.stdin.close()


if __name__ == "__main__":
    main()
