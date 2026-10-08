#!/usr/bin/env python3
"""Windows smoke over MCP: doctor, windows, screenshot, and Calculator driven by UIA elements, verified in code.

    python3 acceptance/windows_smoke.py --cmd "ssh -i ~/.ssh/key -o BatchMode=yes user@windows-pc cctl mcp"

Only touches a Calculator window it opens itself.
"""

import argparse
import re
import sys
import time

from phase1 import Mcp, check, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", required=True)
    a = ap.parse_args()
    m = Mcp(a.cmd)

    doc, _, err, _ = m.call("doctor")
    check("doctor", not err, status=doc.get("status"), backend=doc.get("input_backend"), engine=doc.get("engine"),
          problems=doc.get("problems"))
    wins, _, err, _ = m.call("windows", action="list")
    check("windows_list", not err and len(wins.get("windows", [])) > 0, count=len(wins.get("windows", [])))
    shot, imgs, err, _ = m.call("screenshot", max_dim=1024)
    check("desktop_screenshot", not err and len(imgs) == 1, size=f"{shot.get('width')}x{shot.get('height')}",
          scale=shot.get("scale"))

    before = {w["id"] for w in wins.get("windows", [])}
    la, _, err, _ = m.call("apps", action="launch", name="calc.exe")
    calc = None
    for _ in range(20):
        ws, _, _, _ = m.call("windows", action="list")
        calc = next((w for w in ws.get("windows", []) if w["id"] not in before and
                     "calc" in f"{w.get('app')} {w.get('title')}".lower()), None)
        if calc:
            break
        time.sleep(0.5)
    if not check("launch_calculator", calc is not None, launched=la):
        return finish(m)
    obs, _, err, _ = m.call("observe", window=calc["id"], windows=False, max_elements=200)
    lines = obs.get("elements", [])
    check("calculator_uia_tree", not err and len(lines) > 10, elements=obs.get("window", {}).get("elements_total"))

    def button(name):
        pat = re.compile(rf'button "{re.escape(name)}"', re.I)
        return next((l.split()[0] for l in lines if pat.search(l)), None)

    names = ["One", "Two", "Three", "Multiply by", "Four", "Five", "Six", "Equals"]
    toks = [button(n) for n in names]
    if not check("found_buttons", all(toks), missing=[n for n, t in zip(names, toks) if not t]):
        return finish(m, calc)
    for n in names:
        # tokens go stale after each observe, so re-read before each press
        obs, _, _, _ = m.call("observe", window=calc["id"], windows=False, max_elements=200)
        lines = obs.get("elements", [])
        r, _, err, _ = m.call("click", element=button(n))
        if err:
            check(f"press_{n}", False, error=r)
            return finish(m, calc)
    time.sleep(0.5)
    obs, _, _, _ = m.call("observe", window=calc["id"], windows=False, query="Display")
    text = " ".join(obs.get("elements", []))
    check("calculator_result", "56,088" in text or "56088" in text, display=text[:160])
    return finish(m, calc)


def finish(m, calc=None):
    if calc:
        q, _, err, _ = m.call("windows", action="close", window=calc["id"])
        check("close_calculator", not err, result=q)
    m.p.stdin.close()
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
