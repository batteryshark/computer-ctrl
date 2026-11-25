"""Call cua-driver tools on a remote host over SSH.

Arguments travel base64-encoded so arbitrary JSON (quotes, Unicode) survives
shell quoting. Results come back parsed; files named in `screenshot_out_file`
can be pulled with fetch().
"""

from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
import time

HOST = os.environ.get("CUA_HOST", "user@linux-vm")
BIN = os.environ.get("CUA_BIN", "~/.local/bin/cua-driver")
SSH = ["ssh", "-o", "BatchMode=yes", HOST]


def sh(cmd: str, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=timeout)


def call(tool: str, args: dict | None = None, timeout: float = 120, out_file: str | None = None) -> dict:
    """Run one tool. out_file asks the CLI to write image content there instead of base64."""
    payload = base64.b64encode(json.dumps(args or {}).encode()).decode()
    cmd = f'{BIN} call {shlex.quote(tool)} "$(echo {payload} | base64 -d)"'
    if out_file:
        cmd += f" --screenshot-out-file {shlex.quote(out_file)}"
    t0 = time.monotonic()
    p = sh(cmd, timeout)
    ms = round((time.monotonic() - t0) * 1000)
    out = p.stdout.strip()
    try:
        result = json.loads(out) if out else {}
    except json.JSONDecodeError:
        result = {"_raw": out}
    if p.returncode != 0 or p.stderr.strip():
        result.setdefault("_stderr", p.stderr.strip())
        result.setdefault("_exit", p.returncode)
    result["_ms"] = ms
    return result


def fetch(remote_path: str, local_path: str) -> str:
    subprocess.run(["scp", "-q", f"{HOST}:{remote_path}", local_path], check=True)
    return local_path
