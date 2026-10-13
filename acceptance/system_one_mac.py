#!/usr/bin/env python3
"""Exercise the public delegate tool against test-owned native macOS windows.

Run this same suite from each host harness. Every run launches fresh native
fixtures and invokes cctl over MCP; it never replays captured decisions.

    CCTL_EXECUTOR_ENABLED=true CCTL_DECISION_URL=http://127.0.0.1:18761 \
      CCTL_DECISION_PROTOCOL=d3 \
      python acceptance/system_one_mac.py --harness codex --output /tmp/result.json

The optional model proxy forwards to the configured endpoint and injects a
fixture reflow during one real inference request. No personal app is touched.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase1 import Mcp

ROOT = Path(__file__).resolve().parents[1]


def build_fixture(root: Path) -> Path:
    """Build an isolated app bundle, preserving Cua's existing TCC identity."""
    app = root / "cctl Delegate Acceptance.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>'
        '<key>CFBundleExecutable</key><string>fixture</string>'
        '<key>CFBundleIdentifier</key><string>local.cctl.delegate-acceptance</string>'
        '<key>CFBundleName</key><string>cctl Delegate Acceptance</string>'
        '<key>CFBundlePackageType</key><string>APPL</string>'
        '<key>NSHighResolutionCapable</key><true/>'
        '</dict></plist>')
    subprocess.run(["swiftc", str(ROOT / "acceptance" / "SystemOneFixture.swift"),
                    "-o", str(macos / "fixture")], check=True)
    return app


class ModelProxy:
    """Keep model execution real, with one reproducible UI change/failure."""

    def __init__(self, upstream: str):
        self.upstream = upstream.rstrip("/")
        self.swap: Path | None = None
        self.fail = False
        self.requests = 0
        self.swaps = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                owner.requests += 1
                if owner.swap is not None:
                    owner.swap.write_text("swap")
                    owner.swap = None
                    owner.swaps += 1
                    # Fixture's timer runs at 100 ms. This ensures the change
                    # has happened before a model response can reach cctl.
                    time.sleep(.2)
                if owner.fail:
                    self.send_error(503, "deliberate acceptance model outage")
                    return
                headers = {"Content-Type": "application/json"}
                if self.headers.get("Authorization"):
                    headers["Authorization"] = self.headers["Authorization"]
                req = urllib.request.Request(owner.upstream, data=body, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=30) as reply:
                        payload = reply.read()
                        self.send_response(reply.status)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(payload)
                except urllib.error.HTTPError as exc:
                    self.send_response(exc.code)
                    self.end_headers()
                    self.wfile.write(exc.read())
                except (OSError, TimeoutError):
                    self.send_error(502, "acceptance upstream unavailable")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def definitions(nonce: str) -> list[dict]:
    name, email = "Avery Chen " + nonce, "avery." + nonce + "@example.invalid"

    def field(key, label, value=""):
        return {"key": key, "label": label, "value": value}

    def box(key, label, checked=False):
        return {"key": key, "label": label, "checked": checked}

    def stage(fields=None, checks=None, button="Save draft"):
        result = {"fields": [{"label": label, "value": value} for label, value in (fields or {}).items()],
                  "checks": [{"label": label, "checked": checked} for label, checked in (checks or {}).items()]}
        if button:
            result["button"] = {"label": button}
        return result

    def case(case_id, pages, stages, expected_values, expected_checks=None, **extra):
        return {"id": case_id, "config": {"pages": pages}, "stages": stages,
                "expected_values": expected_values, "expected_checks": expected_checks or {}, **extra}

    basic = {"fields": [field("name", "Full name"), field("email", "Email address")],
             "checkboxes": [box("follow", "Allow follow-up")]}
    targets = {"Full name": name, "Email address": email}
    wanted = {"name": name, "email": email}
    return [
        case("canonical", [basic], [stage(targets, {"Allow follow-up": True})], wanted, {"follow": True}),
        case("preserve_existing", [{"fields": [field("name", "Account holder", "Wrong person"),
                                                field("email", "Receipt email", email),
                                                field("reference", "Internal reference", "KEEP-42")]}],
             [stage({"Account holder": name, "Receipt email": email})], {**wanted, "reference": "KEEP-42"}),
        case("negated_checkbox", [{"fields": [field("email", "Notification email")], "checkboxes": [
            box("marketing", "Marketing messages", True), box("security", "Security alerts", True)]}],
             [stage({"Notification email": email}, {"Marketing messages": False, "Security alerts": True})],
             {"email": email}, {"marketing": False, "security": True}),
        case("two_page_wizard", [{"fields": [field("name", "Full name")]},
                                 {"fields": [field("email", "Email address")],
                                  "checkboxes": [box("follow", "Allow follow-up")]}],
             [stage({"Full name": name}, button="Next"),
              stage({"Email address": email}, {"Allow follow-up": True})], wanted, {"follow": True}),
        case("required_target_missing", [{"fields": [field("name", "Full name")]}],
             [stage(targets)], wanted, expected_status="escalated", zero_mutations=True),
        case("ambiguous_recipient", [{"fields": [field("name", "Recipient"), field("email", "Recipient")]}],
             [stage({"Recipient": name})], wanted, expected_status="escalated", zero_mutations=True),
        case("reflow_during_inference", [basic], [stage(targets, {"Allow follow-up": True})], wanted,
             {"follow": True}, inject_swap=True),
        case("model_outage", [basic], [stage(targets, {"Allow follow-up": True})], wanted,
             {"follow": True}, model_outage=True, expected_status="escalated", zero_mutations=True),
    ]


def trial(case: dict, m: Mcp, app: Path, work: Path, proxy: ModelProxy) -> dict:
    nonce = uuid.uuid4().hex[:8]
    title = "cctl Delegate Acceptance " + nonce
    spec, artifact, command = (work / (nonce + suffix) for suffix in (".json", "-actual.json", "-command"))
    spec.write_text(json.dumps({**case["config"], "title": title}))
    subprocess.run(["open", "-n", str(app), "--args", str(spec), str(artifact), str(command)], check=True)
    win = None
    for _ in range(40):
        data, _, err, _ = m.call("windows", action="list")
        win = next((w for w in data.get("windows", []) if w.get("title") == title), None)
        if win:
            break
        time.sleep(.15)
    if win is None:
        raise RuntimeError("acceptance fixture window not found")
    first_request, first_swap = proxy.requests, proxy.swaps
    proxy.swap = command if case.get("inject_swap") else None
    proxy.fail = bool(case.get("model_outage"))
    start = time.perf_counter()
    row = None
    try:
        task = "Fill only the supplied fields/settings, preserve unrelated values, and save this local test draft."
        result, _, err, _ = m.call("delegate", task=task, window=win["id"], stages=case["stages"],
                                   success=[{"label": "Saved draft", "role": "AXButton"}],
                                   max_steps=32, timeout_ms=45000, intent=task)
        actual = json.loads(artifact.read_text()) if artifact.exists() else None
        expected = case.get("expected_status", "completed")
        exact = (actual is not None and actual.get("action") == "saved"
                 and actual.get("values") == case["expected_values"]
                 and actual.get("checkboxes") == case["expected_checks"])
        passed = not err and result.get("status") == expected and (exact if expected == "completed" else actual is None)
        if case.get("zero_mutations"):
            passed &= not result.get("actions")
        if case.get("inject_swap"):
            passed &= bool(actual and actual.get("rerendered")) and result.get("stale_rejections", 0) >= 1
        row = {"case": case["id"], "passed": bool(passed), "expected_status": expected,
                "elapsed_s": round(time.perf_counter() - start, 3), "model_requests": proxy.requests - first_request,
                "swap_injections": proxy.swaps - first_swap, "result": result, "is_error": err,
                "artifact_exact": exact, "actual": actual}
        return row
    finally:
        proxy.swap, proxy.fail = None, False
        closed, _, close_error, _ = m.call("windows", action="close", window=win["id"])
        if close_error:
            raise RuntimeError(f"test window cleanup failed: {closed.get('error')}")
        for _ in range(20):
            remaining, _, list_error, _ = m.call("windows", action="list")
            if list_error:
                raise RuntimeError("could not verify test window cleanup")
            if not any(w["id"] == win["id"] for w in remaining.get("windows", [])):
                if row is not None:
                    row["cleanup_verified"] = True
                break
            time.sleep(.1)
        else:
            raise RuntimeError("test-owned window remained after close")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmd", default="cctl mcp")
    parser.add_argument("--app", type=Path, help="Existing acceptance fixture bundle; otherwise build in /tmp")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--cases", default="all")
    parser.add_argument("--model-url", default=os.environ.get("CCTL_DECISION_URL", ""))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("this native acceptance suite requires macOS")
    if not args.model_url:
        parser.error("--model-url or CCTL_DECISION_URL is required for the real model test")
    work = Path(tempfile.mkdtemp(prefix="cctl-delegate-acceptance-"))
    app = args.app or build_fixture(work)
    proxy = ModelProxy(args.model_url)
    os.environ["CCTL_CONFIG"] = str(work / "isolated-config.toml")
    os.environ["CCTL_PROFILE"] = "personal"
    os.environ["CCTL_EXECUTOR_ENABLED"] = "true"
    os.environ["CCTL_DECISION_URL"] = proxy.url
    os.environ["CCTL_STATE_DIR"] = str(work / "state")
    os.environ["CCTL_CACHE_DIR"] = str(work / "cache")
    # Path configuration is read from TOML on versions predating env support.
    (work / "isolated-config.toml").write_text(f'state_dir = "{work / "state"}"\ncache_dir = "{work / "cache"}"\n')
    os.environ["CCTL_RUN_TAG"] = "delegate-acceptance-" + uuid.uuid4().hex[:8]
    suite = definitions(uuid.uuid4().hex[:6])
    result = {"harness": args.harness, "scope": "live native GUI via public delegate MCP tool; independently checked artifacts",
              "trials": []}
    m = None
    try:
        m = Mcp(args.cmd)
        names = {t["name"] for t in m.req("tools/list", {})["tools"]}
        if "delegate" not in names:
            raise RuntimeError("delegate is not enabled/listed in the MCP server")
        for case in suite:
            if args.cases != "all" and case["id"] not in args.cases.split(","):
                continue
            result["trials"].append(trial(case, m, app, work, proxy))
            result["passed"] = all(row["passed"] for row in result["trials"])
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            row = result["trials"][-1]
            print(f"{'PASS' if row['passed'] else 'FAIL'} {case['id']} "
                  f"{row['result'].get('status')} {row['elapsed_s']:.2f}s", flush=True)
    finally:
        if m:
            m.p.stdin.close()
            try:
                m.p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                m.p.terminate()
                m.p.wait(timeout=5)
        proxy.close()
    print(f"{sum(row['passed'] for row in result['trials'])}/{len(result['trials'])} passed", flush=True)
    return 0 if result["trials"] and all(row["passed"] for row in result["trials"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
