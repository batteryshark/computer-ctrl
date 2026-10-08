#!/usr/bin/env python3
"""Run a PowerShell script on a Windows host over SSH without quoting pain.

    python3 phase4/winps.py 'Get-Process | Select -First 3'      # script as an argument
    python3 phase4/winps.py - < script.ps1                       # or from stdin

Env: WIN_HOST (default user@windows-pc), WIN_KEY (default ~/.ssh/id_ed25519).
The script is sent as -EncodedCommand (UTF-16LE base64); PowerShell's CLIXML progress noise is stripped.
"""

import base64
import os
import re
import subprocess
import sys

HOST = os.environ.get("WIN_HOST", "user@windows-pc")
KEY = os.path.expanduser(os.environ.get("WIN_KEY", "~/.ssh/id_ed25519"))


def run(script: str, timeout: float = 600) -> subprocess.CompletedProcess:
    script = "$ProgressPreference='SilentlyContinue'\n$PSStyle.OutputRendering='PlainText'\n" + script
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    cmd = ["ssh", "-i", KEY, "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=10", HOST,
           f"powershell -NoProfile -NonInteractive -EncodedCommand {enc}"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def clean(text: str) -> str:
    text = text.replace("#< CLIXML", "")
    return re.sub(r"<Objs Version=.*?</Objs>", "", text, flags=re.S).strip()


if __name__ == "__main__":
    src = sys.stdin.read() if sys.argv[1:] == ["-"] else " ".join(sys.argv[1:])
    p = run(src)
    if p.stdout.strip():
        print(clean(p.stdout))
    err = clean(p.stderr)
    if err:
        print(err, file=sys.stderr)
    sys.exit(p.returncode)
