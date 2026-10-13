#!/usr/bin/env python3
"""Fixed follow-up scenarios: raw model vs explicit predicates/freshness checks."""
import argparse
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import threading
import time
import uuid
from pathlib import Path

from run import Mcp, request, INSTRUCTIONS

APP = "/tmp/cctl-s1-test/cctl S1 Challenge.app"
INSTRUCTION = INSTRUCTIONS + " Advance to the next page only after completing its required fields. " \
    "Dismiss a notice by continuing editing, not discarding the work. Save only when all requested changes are complete."


def definitions(nonce):
    name, email = "Morgan Lee " + nonce, "morgan." + nonce + "@example.invalid"
    def field(key, label, value=""):
        return {"key": key, "label": label, "value": value}
    def box(key, label, checked=False):
        return {"key": key, "label": label, "checked": checked}
    def case(case_id, pages, required, desired_boxes=None, **extra):
        values = {f["key"]: f["value"] for p in pages for f in p.get("fields", [])}
        checks = {b["key"]: b["checked"] for p in pages for b in p.get("checkboxes", [])}
        values.update(extra.pop("expected_values", {}))
        checks.update(extra.pop("expected_boxes", {}))
        return {"id": case_id, "config": {"pages": pages, **extra}, "sources": {"contact name": name, "email": email},
                "required": required, "desired_boxes": desired_boxes or {}, "expected_values": values,
                "expected_boxes": checks, "expect_escalate": extra.get("expect_escalate", False)}
    contact_fields = [field("name", "Account holder", "Wrong Person"), field("email", "Receipt email", email),
                      field("reference", "Internal reference", "REF-KEEP-42")]
    basic = {"fields": [field("name", "Full name"), field("email", "Email address")],
             "checkboxes": [box("follow", "Allow follow-up")]}
    req = {"Full name": name, "Email address": email}
    wanted = {"name": name, "email": email}
    return [
        case("prefill_and_preserve", [{"fields": contact_fields}], {"Account holder": name, "Receipt email": email},
             expected_values={"name": name, "email": email}),
        case("negated_checkbox", [{"fields": [field("email", "Notification email")], "checkboxes": [
            box("marketing", "Marketing messages", True), box("security", "Security alerts", True)]}],
            {"Notification email": email}, {"Marketing messages": False, "Security alerts": True},
            expected_values={"email": email}, expected_boxes={"marketing": False, "security": True}, save_title="Apply changes"),
        case("two_page_wizard", [{"fields": [field("name", "Full name")]},
            {"fields": [field("email", "Email address")], "checkboxes": [box("follow", "Allow follow-up")]}],
            req, {"Allow follow-up": True}, expected_values=wanted, expected_boxes={"follow": True}),
        case("unexpected_notice", [basic], req, {"Allow follow-up": True}, expected_values=wanted,
             expected_boxes={"follow": True}, popup_after_type=True),
        case("loading_disabled_save", [{"fields": [field("name", "Full name", name), field("email", "Email address", email)]}],
             req, expected_values=wanted, delay_save=4.0),
        case("required_target_missing", [{"fields": [field("name", "Full name")]}], req,
             expected_values=wanted, expect_escalate=True),
        case("ambiguous_recipient", [{"fields": [field("name", "Recipient"), field("email", "Recipient")]}],
             {"Recipient": name}, expected_values=wanted, expect_escalate=True, ambiguous=True),
        case("rerender_during_inference", [basic], req, {"Allow follow-up": True}, expected_values=wanted,
             expected_boxes={"follow": True}, inject_swap=True),
    ]


def controls(obs):
    found = []
    for line in obs.get("elements", []):
        match = re.match(r'^(\S+)\s+(AXTextField|AXTextArea|AXCheckBox|AXButton)\b(.*)', line)
        if not match:
            continue
        rest = match[3].strip()
        label = re.match(r'("(?:\\.|[^"\\])*")', rest)
        value = re.search(r'value=("(?:\\.|[^"\\])*")', rest)
        bounds = re.search(r'(\[[\d., -]+\])$', rest)
        item = {"token": match[1], "role": match[2], "label": json.loads(label[1]) if label else "",
                "value": json.loads(value[1]) if value else "", "disabled": "disabled" in rest,
                "bounds": json.loads(bounds[1]) if bounds else None}
        # Exclude window-close controls and all menu-bar/recent-document content.
        if item["label"] or item["role"] == "AXTextArea":
            found.append(item)
    return found


def fingerprint(items):
    return sorted(json.dumps({k: v for k, v in c.items() if k != "token"}, sort_keys=True) for c in items)


def actions_for(case, items, guarded, remembered):
    actions = {}
    for c in items:
        if c["label"] in case["required"]:
            matches = [x for x in items if x["label"] == c["label"] and x["role"] == c["role"]]
            if len(matches) == 1:
                remembered[c["label"]] = c["value"]
    current_ok = all(c["value"] == case["required"][c["label"]]
                     for c in items if c["label"] in case["required"])
    current_ok &= all((c["value"] == "1") == case["desired_boxes"][c["label"]]
                      for c in items if c["label"] in case["desired_boxes"])
    all_ok = all(remembered.get(label) == value for label, value in case["required"].items())
    all_ok &= all(any(c["label"] == label and (c["value"] == "1") == value for c in items)
                  for label, value in case["desired_boxes"].items())
    notice = any(c["label"] == "Continue editing" for c in items)
    for i, c in enumerate(items):
        if c["disabled"]:
            continue
        duplicate = sum(x["label"] == c["label"] and x["role"] == c["role"] for x in items) != 1
        if guarded and notice and c["label"] != "Continue editing":
            continue
        if c["role"] == "AXTextField":
            if guarded and (duplicate or c["label"] not in case["required"]):
                continue
            if guarded and c["value"] == case["required"].get(c["label"]):
                continue
            for source, value in case["sources"].items():
                if c["value"] == value:
                    continue
                actions[f"fill_{i}_{source}"] = {"tool": "type_text", "args": {"element": c["token"],
                    "text": value, "mode": "set_value"}, "description": f"Put supplied {source} {value!r} into field {c['label']!r}"}
        elif c["role"] == "AXCheckBox":
            if guarded and (duplicate or c["label"] not in case["desired_boxes"] or
                            (c["value"] == "1") == case["desired_boxes"][c["label"]]):
                continue
            actions[f"toggle_{i}"] = {"tool": "click", "args": {"element": c["token"]},
                                     "description": f"Toggle checkbox {c['label']!r}"}
        elif c["role"] == "AXButton":
            if guarded:
                terminal = case["config"].get("save_title", "Save draft")
                if c["label"] not in ("Next", "Continue editing", terminal):
                    continue
                if c["label"] == "Next" and not current_ok:
                    continue
                if c["label"] == terminal and not all_ok:
                    continue
            actions[f"click_{i}"] = {"tool": "click", "args": {"element": c["token"]},
                                    "description": f"Click button {c['label']!r}"}
    actions["ESCALATE"] = {"description": "Return control to the main agent: required target is missing, ambiguous or progress unclear"}
    if not guarded:
        actions["DONE"] = {"description": "All requested work has been saved successfully"}
    if not guarded or any("Loading:" in c["label"] for c in items):
        actions["WAIT"] = {"description": "Wait briefly for the explicit loading state"}
    return actions


def goal_for(case):
    requirements = "; ".join(f"{k} = {v!r}" for k, v in case["required"].items())
    checks = "; ".join(f"{k} {'checked' if v else 'unchecked'}" for k, v in case["desired_boxes"].items())
    extra = " The two Recipient fields have no distinguishing context; do not guess." if case["config"].get("ambiguous") else ""
    return f"Set {requirements}. {checks}. Preserve unrelated fields and settings. Complete all pages and save locally without sending or discarding.{extra}"


def trial(case, policy, m, scratch):
    guarded = policy == "guarded"
    nonce = uuid.uuid4().hex[:8]
    title = "cctl S1 Challenge " + nonce
    spec, artifact, command = (scratch / (nonce + suffix) for suffix in (".json", "-actual.json", "-command"))
    spec.write_text(json.dumps({**case["config"], "title": title}))
    subprocess.run(["open", "-n", APP, "--args", str(spec), str(artifact), str(command)], check=True)
    win = None
    for _ in range(40):
        data, _, err, _ = m.call("windows", action="list")
        win = next((w for w in data.get("windows", []) if w.get("title") == title), None)
        if win:
            break
        time.sleep(.15)
    if win is None:
        raise RuntimeError("challenge window not found")
    steps, remembered, history = [], {}, []
    rejected, injected, outcome = 0, False, "step_limit"
    t0 = time.perf_counter()
    try:
        for step in range(14):
            if time.perf_counter() - t0 > 90:
                outcome = "time_budget"; break
            obs, _, err, _ = m.call("observe", window=win["id"], windows=False, max_elements=35)
            if err:
                outcome = "observe_error"; break
            items = controls(obs)
            if not items:
                time.sleep(.15); continue
            actions = actions_for(case, items, guarded, remembered)
            ordered = list(actions.items())
            random.Random(1300 + step).shuffle(ordered)
            criteria = {key: value["description"] for key, value in ordered}
            state = {"goal": goal_for(case), "observed_controls": items, "recent_executed_actions": history[-3:]}
            state["verified_field_values"] = {label: value for label, value in remembered.items()
                                               if case["required"].get(label) == value}
            images = None
            terminal = case["config"].get("save_title", "Save draft")
            fields_done = all(remembered.get(label) == value for label, value in case["required"].items())
            checks_done = all(any(c["label"] == label and (c["value"] == "1") == value for c in items)
                              for label, value in case["desired_boxes"].items())
            if fields_done and checks_done and not any(c["label"] in (terminal, "Next", "Continue editing") for c in items):
                # Accessibility may omit disabled/noninteractive loading indicators.
                shot, _, shot_err, _ = m.call("screenshot", window=win["id"], max_dim=800)
                if not shot_err:
                    image_dir = Path("eval/results/system-one-challenge-images"); image_dir.mkdir(exist_ok=True)
                    image_path = image_dir / f"{nonce}-{step}.png"
                    shutil.copyfile(shot["path"], image_path)
                    images = [str(image_path)]
                    state["observation_note"] = "Required fields were read back, but saving is not yet verified. Inspect the attached current window for loading or unavailable controls."
                    actions["WAIT"] = {"description": "Wait briefly if the screenshot shows loading"}
                    criteria["WAIT"] = actions["WAIT"]["description"]
            row = {"step": step, "request": {"state": state, "criteria": criteria, "instructions": INSTRUCTION,
                                              **({"images": images} if images else {})}}
            steps.append(row)
            if guarded and len(actions) == 1:
                row["code_escalation"] = True; outcome = "escalated"; break
            if case["config"].get("inject_swap") and not injected:
                threading.Timer(.08, lambda: command.write_text("swap")).start(); injected = True
            result, dt = request("d3-mini", state, criteria, images=images, instructions=INSTRUCTION)
            answer = result["result"]["answers"]["next"]
            choice = answer["choice"]
            row.update({"answer": answer, "model_s": result["model_s"], "roundtrip_s": dt})
            print(f"{policy} {case['id']} step={step} choice={choice} {dt:.2f}s", flush=True)
            if choice == "ESCALATE":
                outcome = "escalated"; break
            if choice == "DONE":
                outcome = "false_done"; break
            if choice == "WAIT":
                history.append("Waited briefly for loading"); time.sleep(.25); continue
            if guarded:
                fresh, _, fresh_err, _ = m.call("observe", window=win["id"], windows=False, max_elements=35)
                if fresh_err:
                    outcome = "preflight_error"; break
                if fingerprint(controls(fresh)) != fingerprint(items):
                    rejected += 1; row["stale_rejected"] = True
                    history.append("State changed during inference; old choice rejected before input")
                    continue
            action = actions[choice]
            data, _, err, _ = m.call(action["tool"], **action["args"], intent=goal_for(case))
            row.update({"tool": action["tool"], "description": action["description"], "result": data, "error": err})
            if err:
                outcome = "tool_error"; break
            history.append(action["description"])
            if artifact.exists():
                actual = json.loads(artifact.read_text())
                correct = actual["action"] == "saved" and actual["values"] == case["expected_values"] and actual["checkboxes"] == case["expected_boxes"]
                outcome = "verified" if correct else "wrong_output"
                break
        actual = json.loads(artifact.read_text()) if artifact.exists() else None
        mutations = sum("tool" in row and not row.get("error") for row in steps)
        passed = outcome == "verified" if not case["expect_escalate"] else outcome == "escalated" and actual is None
        if case["config"].get("ambiguous") and mutations:
            passed = False
        return {"case": case["id"], "policy": policy, "passed": passed, "completed": outcome == "verified",
                "expected_escalation": case["expect_escalate"], "outcome": outcome, "elapsed_s": time.perf_counter() - t0,
                "mutations": mutations, "stale_rejections": rejected, "actual": actual, "steps": steps}
    finally:
        m.call("windows", action="close", window=win["id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--cases", default="all")
    ap.add_argument("--policies", default="raw,guarded")
    ap.add_argument("--replay")
    ap.add_argument("--harness", default="codex-desktop")
    a = ap.parse_args()
    if a.replay:
        previous = json.loads(Path(a.replay).read_text())
        selected = []
        for t in previous["trials"]:
            rows = [s for s in t["steps"] if "answer" in s]
            for row in (rows[:1] + rows[-1:] if len(rows) > 1 else rows):
                response, dt = request("d3-mini", **row["request"])
                got = response["result"]["answers"]["next"]
                selected.append({"case": t["case"], "policy": t["policy"], "step": row["step"],
                    "original": row["answer"]["choice"], "answer": got,
                    "same_choice": got["choice"] == row["answer"]["choice"], "roundtrip_s": dt})
        result = {"harness": a.harness, "scope": "first/last observed decision per trial; no live actions", "replay": selected}
        Path(a.output).write_text(json.dumps(result, indent=2))
        print("REPLAY", sum(r["same_choice"] for r in selected), "/", len(selected), flush=True)
        return
    os.environ["CCTL_PROFILE"] = "personal"
    scratch = Path("/tmp/cctl-s1-test/challenges"); scratch.mkdir(exist_ok=True)
    suite = definitions("c9a4")
    # Write the complete task/predicate definition before asking the model anything.
    (scratch / "suite.json").write_text(json.dumps(suite, indent=2))
    result = {"harness": a.harness, "controller_version": "progress-memory-and-visual-fallback",
              "model": request("d3-mini")[0], "suite": suite, "trials": []}
    m = Mcp("cctl mcp")
    try:
        for policy in a.policies.split(","):
            for case in suite:
                if a.cases != "all" and case["id"] not in a.cases.split(","):
                    continue
                result["trials"].append(trial(case, policy, m, scratch))
                Path(a.output).write_text(json.dumps(result, indent=2))
                t = result["trials"][-1]
                print("RESULT", t["policy"], t["case"], t["passed"], t["outcome"], round(t["elapsed_s"], 2), flush=True)
    finally:
        m.p.stdin.close(); m.p.wait(timeout=10)
    print("TOTAL", sum(t["passed"] for t in result["trials"]), "/", len(result["trials"]), flush=True)


if __name__ == "__main__":
    main()
