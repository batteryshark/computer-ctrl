"""cctl command line.

    cctl mcp                         MCP server on stdio (point a harness at this)
    cctl serve                       background service used by the CLI verbs (auto-started)
    cctl tools                       list tools
    cctl <tool> [JSON] [--key value ...]
                                     run one tool; prints one JSON line. Images are saved to disk
                                     and their path is in the JSON ("path").
    cctl --host USER@HOST <tool> ... run on a remote machine over SSH; images are copied back
                                     and "path" points at the local copy.
    cctl --host USER@HOST mcp        MCP server for a remote machine (stdio relayed over SSH).

Values after --key are parsed as JSON when possible (numbers, true/false, [1,2,3]),
otherwise taken as strings: cctl click --x 412 --y 300, cctl zoom --region [0,0,400,200].
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import contract
from .config import load


def parse_args(argv: list[str]) -> dict:
    args: dict = {}
    i = 0
    if argv and argv[0].startswith("{"):
        args.update(json.loads(argv[0]))
        i = 1
    while i < len(argv):
        tok = argv[i]
        if not tok.startswith("--"):
            raise SystemExit(f"unexpected argument {tok!r}; use --key value or a JSON object")
        key = tok[2:].replace("-", "_")
        if "=" in key:
            key, raw = key.split("=", 1)
            i += 1
        elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            raw = argv[i + 1]
            i += 2
        else:
            raw = "true"
            i += 1
        try:
            args[key] = json.loads(raw)
        except json.JSONDecodeError:
            args[key] = raw
    return args


def daemon_alive(sock: Path) -> bool:
    import socket as s
    from .daemon import USE_TCP
    try:
        if USE_TCP:
            port = json.loads(sock.read_text())["port"]
            with s.create_connection(("127.0.0.1", port), timeout=1):
                return True
        c = s.socket(s.AF_UNIX)
        c.connect(str(sock))
        c.close()
        return True
    except (OSError, ValueError, KeyError):
        return False


def ensure_daemon(cfg) -> None:
    from .daemon import socket_path
    sock = socket_path(cfg)
    if sock.exists():
        if daemon_alive(sock):
            return
        sock.unlink(missing_ok=True)
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        start_in_desktop_session(cfg)
    else:
        with open(cfg.state_dir / "daemon.log", "ab") as log:
            subprocess.Popen([sys.executable, "-m", "cctl.cli", "serve"], stdin=subprocess.DEVNULL, stdout=log,
                             stderr=log, start_new_session=True)
    for _ in range(300 if sys.platform == "win32" else 100):
        if sock.exists() and daemon_alive(sock):
            return
        time.sleep(0.1)
    raise SystemExit(f"cctl service did not start; see {cfg.state_dir / 'daemon.log'}")


def start_in_desktop_session(cfg) -> None:
    """Windows: SSH sessions are not the interactive desktop session, and processes they start die with them.
    Start `cctl serve` in the logged-in user's desktop session through a one-shot scheduled task (removed again
    right away), so it can drive the desktop and outlive the SSH connection."""
    log = cfg.state_dir / "daemon.log"
    py = sys.executable.replace("python.exe", "pythonw.exe") if sys.executable.endswith("python.exe") else sys.executable
    ps = f"""
$tn = 'cctl-serve-once'
$a = New-ScheduledTaskAction -Execute '{py}' -Argument '-m cctl.cli serve'
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Days 30) -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $tn -Action $a -Principal $p -Settings $s -Force | Out-Null
Start-ScheduledTask -TaskName $tn
Start-Sleep -Seconds 2
Unregister-ScheduledTask -TaskName $tn -Confirm:$false
"""
    with open(log, "ab") as f:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], stdout=f, stderr=f, check=False)


def run_local(tool: str, args: dict) -> int:
    from .daemon import request
    cfg = load()
    ensure_daemon(cfg)
    resp = asyncio.run(request(cfg, tool, args))
    print(json.dumps(resp["data"], ensure_ascii=False))
    return 1 if resp.get("is_error") else 0


def run_remote(host: str, argv: list[str]) -> int:
    remote_bin = os.environ.get("CCTL_REMOTE_BIN", "~/.local/bin/cctl")
    cmd = remote_bin + " " + " ".join(shlex.quote(a) for a in argv)
    p = subprocess.run(["ssh", "-T", "-o", "BatchMode=yes", host, cmd], capture_output=True, text=True)
    out = p.stdout.strip()
    try:
        data = json.loads(out.splitlines()[-1]) if out else {}
    except json.JSONDecodeError:
        sys.stdout.write(p.stdout)
        sys.stderr.write(p.stderr)
        return p.returncode
    for key in ("path",):
        remote = data.get(key)
        if isinstance(remote, str):
            local_dir = Path(tempfile.gettempdir()) / "cctl-remote"
            local_dir.mkdir(exist_ok=True)
            local = local_dir / f"{host.replace('@', '_')}-{Path(remote).name}"
            if subprocess.run(["scp", "-q", f"{host}:{remote}", str(local)]).returncode == 0:
                data["remote_path"] = remote
                data[key] = str(local)
    print(json.dumps(data, ensure_ascii=False))
    return p.returncode


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252; titles and text are Unicode
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    host = os.environ.get("CCTL_HOST")
    if argv[:1] == ["--host"]:
        host, argv = argv[1], argv[2:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("tools: " + ", ".join(contract.tool_names()))
        return
    if host and argv[0] == "mcp":
        # Remote MCP: stdio passes straight through SSH to cctl on the target.
        remote_bin = os.environ.get("CCTL_REMOTE_BIN", "~/.local/bin/cctl")
        os.execvp("ssh", ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=30", host,
                          f"{remote_bin} mcp"])
    if host and argv[0] != "serve":
        raise SystemExit(run_remote(host, argv))
    cmd = argv[0]
    if cmd == "mcp":
        from .server import main as mcp_main
        if sys.platform == "win32" and "--direct" not in argv:
            ensure_daemon(load())  # the engine lives in the desktop session; this process only relays MCP
            mcp_main(via_daemon=True)
        else:
            mcp_main()
    elif cmd == "serve":
        from .daemon import serve
        asyncio.run(serve())
    elif cmd == "tools":
        for t in contract.tools():
            print(f"{t['name']:12s} {t['description'].split('. ')[0]}")
    elif cmd in contract.tool_names():
        raise SystemExit(run_local(cmd, parse_args(argv[1:])))
    else:
        raise SystemExit(f"unknown command {cmd!r}; try `cctl tools`")


if __name__ == "__main__":
    main()
