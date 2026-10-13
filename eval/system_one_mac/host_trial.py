#!/usr/bin/env python3
"""Same native form driven by a real host harness, verified independently on disk."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "acceptance"))
from phase1 import Mcp

ap = argparse.ArgumentParser()
ap.add_argument("--harness", choices=["codex", "claude"], required=True)
ap.add_argument("--output", required=True)
a = ap.parse_args()
os.environ["CCTL_PROFILE"] = "personal"
tag = "s1-host-" + a.harness + "-" + uuid.uuid4().hex[:8]
work = Path("/tmp/cctl-s1-test/harness") / tag
work.mkdir(parents=True)
name, email = "Avery Chen " + tag[-4:], "avery." + tag[-4:] + "@example.invalid"
title = "cctl S1 Lab " + tag
spec, actual_file = work / "fixture.json", work / "actual.json"
spec.write_text(json.dumps({"title": title, "fields": [{"key": "name", "label": "Full name"},
                           {"key": "email", "label": "Electronic mail"}],
                           "checkbox": "Contact me with updates"}))
subprocess.run(["open", "-n", "/tmp/cctl-s1-test/cctl S1 Lab.app", "--args", str(spec), str(actual_file)], check=True)
m = Mcp("cctl mcp")
win = None
for _ in range(30):
    wins, _, _, _ = m.call("windows", action="list")
    win = next((w for w in wins.get("windows", []) if w.get("title") == title), None)
    if win:
        break
    time.sleep(.2)
if not win:
    raise RuntimeError("fixture not found")
prompt = (f"Perform this GUI task ONLY with the cctl MCP tools, without shell or file tools. "
          f"The experiment's own native test window has id {win['id']} and title {title!r}. "
          f"Start by observing that window with windows=false and max_elements=8. "
          f"Set the contact name to {name!r} and email address to {email!r}. Enable follow-up. "
          "Save a draft without sending it. Use observed element tokens, mode=set_value for text, "
          "and the click tool for checkbox/button. Only act on that test window. Reply DONE when finished.")
env = {**os.environ, "CCTL_RUN_TAG": tag}
cctl = str(Path.home() / ".local/bin/cctl")
if a.harness == "codex":
    cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--approve-for-me",
           "-c", f'mcp_servers.cctl.command="{cctl}"', "-c", 'mcp_servers.cctl.args=["mcp"]',
           "-c", 'mcp_servers.cctl.env.CCTL_PROFILE="personal"',
           "-c", f'mcp_servers.cctl.env.CCTL_RUN_TAG="{tag}"',
           "-c", 'mcp_servers.cctl.tool_timeout_sec=120', prompt]
else:
    mcp_config = work / "mcp.json"
    mcp_config.write_text(json.dumps({"mcpServers": {"cctl": {"command": cctl, "args": ["mcp"],
                                     "env": {"CCTL_PROFILE": "personal", "CCTL_RUN_TAG": tag}}}}))
    cmd = ["claude", "-p", "--strict-mcp-config", "--mcp-config", str(mcp_config),
           "--allowedTools", "mcp__cctl", "--permission-prompts", "none", "--output-format", "json", prompt]
t0 = time.perf_counter()
try:
    with (work / "transcript.txt").open("w") as transcript:
        process = subprocess.run(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                 stdout=transcript, stderr=subprocess.STDOUT, timeout=240)
    elapsed = time.perf_counter() - t0
    actual = json.loads(actual_file.read_text()) if actual_file.exists() else None
    events = []
    log = Path.home() / ".local/state/cctl/events.jsonl"
    if log.exists():
        for line in log.read_text().splitlines():
            try:
                e = json.loads(line)
                if e.get("tag") == tag:
                    events.append(e)
            except json.JSONDecodeError:
                pass
    expected = {"action": "saved", "values": {"name": name, "email": email}, "follow_up": True}
    transcript = (work / "transcript.txt").read_text()
    trace_calls = re.findall(r"mcp: cctl/([a-z_]+) \(completed\)", transcript)
    calls = [e["tool"] for e in events] if events else trace_calls
    result = {"harness": a.harness, "elapsed_s": elapsed, "exit_code": process.returncode,
              "success": actual == expected and "type_text" in calls,
              "tool_calls": calls, "trace_source": "tagged_events" if events else "cli_transcript",
              "actual": actual, "events": events, "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    Path(a.output).write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "events"}, indent=2), flush=True)
    print("cctl tool calls", len(events), flush=True)
finally:
    m.call("windows", action="close", window=win["id"])
    m.p.stdin.close()
    m.p.wait(timeout=10)
