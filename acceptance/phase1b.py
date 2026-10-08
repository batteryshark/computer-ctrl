#!/usr/bin/env python3
"""Phase 1b acceptance: browser tools over MCP against a local test page, verified in code.

    python3 acceptance/phase1b.py                       # on the target machine
    python3 acceptance/phase1b.py --cmd "cctl --host user@linux-vm mcp"

The page (acceptance/web/form.html) is served by `python3 -m http.server` started through the run tool.
"""

import argparse
import json
import sys
import time

from phase1 import Mcp, check, results

PORT = 8765


def fnv_confirmation(s: str) -> str:
    h = 2166136261
    for c in s:
        h ^= ord(c)
        h = (h * 16777619) & 0xFFFFFFFF
    return f"CONF-{h % 1000000:06d}"


def ref_of(lines, *needles):
    for line in lines:
        if all(n in line for n in needles):
            return line.split()[0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="cctl mcp")
    ap.add_argument("--web-dir", default="~/computer-ctrl/acceptance/web")
    a = ap.parse_args()
    m = Mcp(a.cmd)
    m.call("run", command=f"cd {a.web_dir} && (setsid python3 -m http.server {PORT} --bind 127.0.0.1 "
                          f">/tmp/cctl-web.log 2>&1 &) ; sleep 0.5")
    url = f"http://127.0.0.1:{PORT}/form.html"

    o, _, err, _ = m.call("browser_open", url=url)
    check("browser_open", not err and o.get("title") == "cctl acceptance form", **o)

    s, _, err, raw = m.call("browser_snapshot")
    acts = s.get("actions", [])
    code_ref, agree_ref = ref_of(acts, "textbox", "Code word"), ref_of(acts, "checkbox")
    check("snapshot_lists_refs", not err and code_ref and agree_ref and "structuredContent" not in raw,
          refs=len(acts), code=code_ref, agree=agree_ref)

    code = "café-日本-✓"
    t, _, err, _ = m.call("browser_act", action="type", ref=code_ref, text=code)
    check("type_unicode", not err, **{k: t.get(k) for k in ("done", "target")})
    c, _, err, _ = m.call("browser_act", action="click", ref=agree_ref)
    check("click_checkbox", not err)

    s, _, _, _ = m.call("browser_snapshot", query="Submit")
    go = ref_of(s.get("actions", []), "button", "Submit")
    m.call("browser_act", action="click", ref=go)
    time.sleep(0.3)
    r, _, _, _ = m.call("browser_snapshot", query="Accepted")
    text = json.dumps(r, ensure_ascii=False)
    want = fnv_confirmation(code)
    check("form_result_verified", want in text, want=want)

    sc, imgs, err, _ = m.call("browser_snapshot", screenshot=True)
    check("viewport_screenshot", not err and len(imgs) == 1 and sc.get("frame", "").startswith("v"),
          frame=sc.get("frame"), size=f"{sc.get('width')}x{sc.get('height')}")

    sc2, _, _, _ = m.call("browser_act", action="scroll", dy=2000, x=200, y=200)
    f, _, err, _ = m.call("browser_snapshot", query="ZEBRA-42")
    check("scroll_then_query_footer", "ZEBRA-42" in json.dumps(f), err=err)

    bad, _, err, _ = m.call("click", x=5, y=5, frame=sc["frame"])
    check("desktop_click_rejects_viewport_frame", err and bad.get("error") == "bad_frame")

    n, _, err, _ = m.call("browser_navigate", url="about:blank")
    n2, _, err2, _ = m.call("browser_navigate", history="back")
    check("navigate_and_back", not err and not err2 and n2.get("url") == url, back=n2.get("url"))

    cl, _, err, _ = m.call("browser_close")
    check("browser_close", not err)
    m.call("run", command=f"pkill -f '[h]ttp.server {PORT}'")
    m.p.stdin.close()
    m.p.wait(timeout=10)
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
