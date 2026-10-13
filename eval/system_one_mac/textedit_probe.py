#!/usr/bin/env python3
"""Own-document TextEdit tasks selected by d3-mini, independently checked on disk."""
import argparse
import json
import os
import random
import time
import uuid
from pathlib import Path

from challenge import controls, fingerprint
from run import Mcp, request, INSTRUCTIONS


def run_case(m, prefix, payload):
    path = Path("/tmp/cctl-s1-test") / ("s1-textedit-" + uuid.uuid4().hex[:8] + ".txt")
    path.write_text(prefix)
    expected = prefix + payload
    before, _, _, _ = m.call("windows", action="list")
    prior = {w["id"] for w in before["windows"]}
    _, _, error, _ = m.call("apps", action="launch", name="TextEdit", urls=[str(path)])
    if error:
        raise RuntimeError("TextEdit failed to open the test file")
    win = None
    for _ in range(30):
        data, _, _, _ = m.call("windows", action="list")
        win = next((w for w in data["windows"] if w["id"] not in prior and path.name in (w.get("title") or "")), None)
        if win:
            break
        time.sleep(.2)
    if win is None:
        raise RuntimeError("test document window missing")
    rows, outcome, history = [], "step_limit", []
    goal = "Keep the existing document prefix, append the supplied text exactly, and save this test document."
    started = time.perf_counter()
    try:
        for step in range(6):
            obs, _, error, _ = m.call("observe", window=win["id"], windows=False, max_elements=15)
            if error:
                outcome = "observe_error"; break
            editable = [c for c in controls(obs) if c["role"] in ("AXTextArea", "AXTextField")]
            if len(editable) != 1:
                outcome = "ambiguous_editor"; break
            field = editable[0]
            actions = {
                "write": {"tool": "type_text", "args": {"element": field["token"], "text": expected, "mode": "set_value"},
                          "description": "Replace the observed document contents with the original prefix plus the supplied appended text"},
                "save": {"tool": "menu", "args": {"window": win["id"], "path": ["File", "Save"]},
                         "description": "Save the current test document using its File > Save menu"},
                "ESCALATE": {"description": "Return to the main agent if the document or progress is unclear"},
            }
            ready = field["value"] == expected
            if ready:
                actions.pop("write")
            else:
                actions.pop("save")
            criteria = {k: v["description"] for k, v in actions.items()}
            state = {"goal": goal, "original_prefix": prefix, "append_text": payload,
                     "observed_editor": field, "recent_actions": history}
            response, dt = request("d3-mini", state, criteria, instructions=INSTRUCTIONS)
            answer = response["result"]["answers"]["next"]
            choice = answer["choice"]
            row = {"request": {"state": state, "criteria": criteria}, "answer": answer, "roundtrip_s": dt}
            rows.append(row)
            print("TEXTEDIT", step, choice, round(dt, 3), flush=True)
            if choice == "ESCALATE":
                outcome = "escalated"; break
            fresh, _, err, _ = m.call("observe", window=win["id"], windows=False, max_elements=15)
            if err or fingerprint([c for c in controls(fresh) if c["role"] in ("AXTextArea", "AXTextField")]) != fingerprint(editable):
                row["stale_rejected"] = True; continue
            action = actions[choice]
            data, _, err, _ = m.call(action["tool"], **action["args"], intent=goal)
            row.update({"tool": action["tool"], "result": data, "error": err})
            if err:
                outcome = "tool_error"; break
            history.append(action["description"])
            if choice == "save":
                for _ in range(10):
                    if path.read_text() == expected:
                        outcome = "verified"; break
                    time.sleep(.1)
                break
        return {"prefix": prefix, "payload": payload, "success": outcome == "verified", "outcome": outcome,
                "elapsed_s": time.perf_counter() - started, "file_content": path.read_text(), "steps": rows}
    finally:
        # Save only this test document's pending changes before closing, even on a failed trial.
        m.call("menu", window=win["id"], path=["File", "Save"])
        m.call("windows", action="close", window=win["id"])
        path.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--output", required=True); a = ap.parse_args()
    os.environ["CCTL_PROFILE"] = "personal"
    m = Mcp("cctl mcp")
    result = {"scope": "two short own-document tasks in existing TextEdit; caller supplies exact data/predicates", "trials": []}
    try:
        for prefix, payload in [("", "Local model test — café 日本語 ✓"),
                                ("Keep this prefix. ", "Append: Morgan Lee ✓")]:
            result["trials"].append(run_case(m, prefix, payload))
            Path(a.output).write_text(json.dumps(result, indent=2))
    finally:
        m.p.stdin.close(); m.p.wait(timeout=10)
    print(json.dumps([{k: v[k] for k in ["success", "outcome", "elapsed_s"]} for v in result["trials"]]), flush=True)


if __name__ == "__main__":
    main()
