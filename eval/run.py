#!/usr/bin/env python3
"""Run cctl eval tasks through a real harness on the controlled machine and score them in code.

    python3 eval/run.py --harness codex [--tasks all|id,category,...] [--repeat N] [--label NAME] -- <harness args>

Examples (on the VM, harness binaries on PATH):
    python3 eval/run.py --harness codex -- -m gpt-6.1-sol -c 'model_reasoning_effort="medium"' \\
        --dangerously-bypass-approvals-and-sandbox
    python3 eval/run.py --harness opencode --tasks browser,editor -- --model zai/glm-5.3

Writes eval/results/<timestamp>-<label>.jsonl and a markdown summary next to it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tasks import Ctx, by_id, used  # noqa: E402

CCTL = os.environ.get("CCTL_BIN", str(Path.home() / ".local/bin/cctl"))
EVENTS = Path.home() / ".local/state/cctl/events.jsonl"
ROOT = Path("/tmp/cctl-eval")


def session_env() -> dict:
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    env.setdefault("XAUTHORITY", str(Path.home() / ".Xauthority"))
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
    return env


def shell(cmd: str, env: dict, timeout: float = 60) -> None:
    if cmd.strip():
        subprocess.run(["bash", "-c", cmd], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=timeout)


def harness_cmd(harness: str, run: Path, prompt: str, extra: list[str]) -> tuple[list[str], Path | None]:
    if harness == "codex":
        last = run / "answer.txt"
        return (["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-o", str(last),
                 "-c", f'mcp_servers.cctl.command="{CCTL}"', "-c", 'mcp_servers.cctl.args=["mcp"]',
                 "-c", "mcp_servers.cctl.tool_timeout_sec=180", *extra, prompt], last)
    if harness == "opencode":
        (run / "opencode.json").write_text(json.dumps({"$schema": "https://opencode.ai/config.json", "mcp": {
            "cctl": {"type": "local", "command": [CCTL, "mcp"], "timeout": 180000}}}))
        return (["opencode", "run", "--auto", *extra, prompt], None)
    if harness == "claude":
        (run / "mcp.json").write_text(json.dumps({"mcpServers": {"cctl": {"command": CCTL, "args": ["mcp"]}}}))
        return (["claude", "-p", "--mcp-config", str(run / "mcp.json"), "--strict-mcp-config",
                 "--allowedTools", "mcp__cctl", *extra, "--", prompt], None)
    raise SystemExit(f"unknown harness {harness}")


def answer_text(harness: str, transcript: str, last: Path | None) -> str:
    if last and last.exists():
        return last.read_text(errors="replace")
    clean = re.sub(r"\x1b\[[0-9;]*m", "", transcript)
    if harness == "opencode":  # drop tool-call echo lines, keep the model's prose
        clean = "\n".join(l for l in clean.splitlines() if not l.lstrip().startswith(("⚙", "✗", "→", "✱", ">")))
    return clean[-3000:]


ALLOWED_SHELL = re.compile(r"^\s*(cctl\b|which cctl\b|~?/?[\w/.-]*cctl\b)")


def harness_shell_commands(harness: str, transcript: str) -> list[str]:
    """Shell commands the model ran through the harness itself (not through cctl's run tool)."""
    clean = re.sub(r"\x1b\[[0-9;]*m", "", transcript)
    if harness == "opencode":
        return [l[2:] for l in clean.splitlines() if l.startswith("$ ")]
    if harness == "codex":
        return re.findall(r"^exec\n(?:/bin/bash -lc )?'?(.+?)'? in /", clean, re.M)
    return []


def harness_shell_used(harness: str, transcript: str) -> list[str]:
    """Commands other than the cctl CLI: using `cctl <tool>` from a shell is the toolkit's CLI path, not a bypass."""
    return [c for c in harness_shell_commands(harness, transcript) if not ALLOWED_SHELL.match(c)]


def tokens_used(transcript: str) -> int | None:
    m = re.search(r"tokens used\s*\n?\s*([\d,]+)", transcript)
    return int(m.group(1).replace(",", "")) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", required=True, choices=["codex", "opencode", "claude"])
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--label", default="")
    ap.add_argument("extra", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    extra = a.extra[1:] if a.extra[:1] == ["--"] else a.extra
    tasks = by_id(a.tasks.split(","))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    label = a.label or a.harness
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{stamp}-{label}.jsonl"
    env = session_env()
    os.environ.update(env)  # checks shell out (xdotool, pgrep) and need the desktop session too
    rows = []
    for rep in range(a.repeat):
        for t in tasks:
            run = ROOT / stamp / f"{t.id}-{rep}"
            run.mkdir(parents=True, exist_ok=True)
            ctx = Ctx(run=run)
            shell(t.setup(ctx), env)
            prompt = t.prompt(ctx)
            argv, last = harness_cmd(a.harness, run, prompt, extra)
            start = time.time()
            t0 = time.monotonic()
            try:
                # PWD too: opencode takes its project directory (and so its opencode.json) from $PWD, not the cwd.
                p = subprocess.run(argv, cwd=run, env={**env, "PWD": str(run)}, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, timeout=t.timeout_s)
                transcript, timed_out = p.stdout + p.stderr, False
            except subprocess.TimeoutExpired as e:
                transcript = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
                timed_out = True
            seconds = round(time.monotonic() - t0, 1)
            (run / "transcript.txt").write_text(transcript)
            calls = [json.loads(l) for l in EVENTS.read_text().splitlines() if json.loads(l)["ts"] >= start] \
                if EVENTS.exists() else []
            answer = answer_text(a.harness, transcript, last)
            try:
                res = t.check(ctx, answer, calls)
                ok, detail = res.ok, res.detail
            except Exception as e:  # noqa: BLE001
                ok, detail = False, {"check_error": repr(e)}
            tools = used(calls)
            violations = []
            if t.gui_only and "run" in tools:
                violations.append("used run tool")
            other_shell = harness_shell_used(a.harness, transcript)
            if t.gui_only and other_shell:
                violations.append(f"shell outside cctl: {other_shell[:3]}")
            ok = ok and not violations and not timed_out
            shell(t.teardown(ctx), env)
            row = {"task": t.id, "category": t.category, "rep": rep, "ok": ok, "seconds": seconds,
                   "timed_out": timed_out, "calls": len(calls), "errors": sum(not c["ok"] for c in calls),
                   "tools": sorted(tools), "tokens": tokens_used(transcript), "violations": violations,
                   "detail": detail, "answer": answer.strip()[-300:], "run": str(run)}
            rows.append(row)
            with open(out, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{'PASS' if ok else 'FAIL'} {t.id:24s} {seconds:6.1f}s calls={len(calls):3d} "
                  f"errors={row['errors']} {'TIMEOUT ' if timed_out else ''}{violations or ''} {json.dumps(detail, ensure_ascii=False)[:120]}",
                  flush=True)
    passed = sum(r["ok"] for r in rows)
    md = [f"# Eval {stamp} — {label}", "", f"Harness: `{a.harness} {' '.join(shlex.quote(x) for x in extra)}`", "",
          f"**{passed}/{len(rows)} passed**", "", "| task | category | ok | s | calls | errors | tokens |",
          "|---|---|---|---|---|---|---|"]
    md += [f"| {r['task']} | {r['category']} | {'✅' if r['ok'] else '❌'} | {r['seconds']} | {r['calls']} | "
           f"{r['errors']} | {r['tokens'] or ''} |" for r in rows]
    out.with_suffix(".md").write_text("\n".join(md) + "\n")
    print(f"\n{passed}/{len(rows)} passed → {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
