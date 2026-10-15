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
    cctl --session NAME <tool> ...  use a configured isolated desktop (optional companion).
    cctl --session NAME session start|status|stop
                                     acquire/resume, inspect or release that isolated desktop.

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


def parse_args(argv: list[str], schema: dict | None = None) -> dict:
    """--key value pairs; values are JSON-decoded unless the tool's schema says the parameter is a string
    (so `key --keys 4` stays "4" and `type_text --text true` stays "true")."""
    props = (schema or {}).get("properties", {})

    def is_string(key: str) -> bool:
        t = props.get(key, {}).get("type")
        return t == "string" or (isinstance(t, list) and "string" in t and "integer" not in t)

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
        if is_string(key):
            args[key] = raw
            continue
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
    if sys.platform == "win32" and cfg.session:
        from .private_paths import create_private_directory
        create_private_directory(cfg.state_dir)
        start_isolated_controller(cfg)
    elif sys.platform == "win32":
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        start_in_desktop_session(cfg)
    else:
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        with open(cfg.state_dir / "daemon.log", "ab") as log:
            kwargs = ({"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                       | subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32"
                      else {"start_new_session": True})
            subprocess.Popen([sys.executable, "-m", "cctl.cli", "serve"], stdin=subprocess.DEVNULL, stdout=log,
                             stderr=log, **kwargs)
    for _ in range(300 if sys.platform == "win32" else 100):
        if sock.exists() and daemon_alive(sock):
            return
        time.sleep(0.1)
    raise SystemExit(f"cctl service did not start; see {cfg.state_dir / 'daemon.log'}")


def start_isolated_controller(cfg) -> None:
    """Escape the SSH job with a one-shot Limited task, scoped to this target.

    The controller only calls the isolated provider. It never discovers/drives
    the host desktop. The task has no trigger and is removed after dispatch.
    """
    import hashlib
    py = str(Path(sys.executable).with_name("pythonw.exe"))
    if not Path(py).exists():
        py = sys.executable
    env = {k: os.environ[k] for k in ("CCTL_CONFIG", "PYTHONPATH") if k in os.environ}
    env["CCTL_SESSION"] = cfg.session
    launcher = cfg.state_dir / "controller-launch.py"
    log = cfg.state_dir / "daemon.log"
    launcher.write_text("import os,sys\n" + f"os.environ.update({env!r})\n"
                        + "sys.path[:0]=[p for p in os.environ.get('PYTHONPATH','').split(os.pathsep) if p]\n"
                        + f"log=open({str(log)!r}, 'a', encoding='utf-8')\n"
                        + "sys.stdout=log;sys.stderr=log\nfrom cctl.cli import main\nmain(['serve'])\n", encoding="utf-8")
    task = "cctl-isolated-" + hashlib.sha256(str(cfg.state_dir).encode()).hexdigest()[:16]
    ps = f"""$ErrorActionPreference='Stop'
$tn={ps_quote(task)}
$a=New-ScheduledTaskAction -Execute {ps_quote(py)} -Argument {ps_quote('"' + str(launcher) + '"')}
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$p=New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Limited
$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Days 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $tn -Action $a -Principal $p -Settings $s -Force | Out-Null
try {{ Start-ScheduledTask -TaskName $tn; Start-Sleep -Seconds 2 }}
finally {{ Unregister-ScheduledTask -TaskName $tn -Confirm:$false }}
"""
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise SystemExit("Isolated controller launch failed: " + result.stderr.strip())


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


PATH_KEYS = ("path", "sheet_path", "waveform_path")


def remote_target(host: str) -> tuple[list[str], str, bool]:
    """(ssh args, remote cctl command, remote is Windows) for a host, from the `hosts` table in config.toml."""
    # Session names resolve on the target machine, not in the SSH caller's config.
    entry = load(select_session=False).hosts.get(host, {})
    ssh_args = [os.path.expanduser(a) for a in entry.get("ssh_args", [])]
    windows = entry.get("os", "").lower() == "windows"
    default_bin = "cctl" if windows else "~/.local/bin/cctl"
    return ssh_args, entry.get("remote_bin") or os.environ.get("CCTL_REMOTE_BIN", default_bin), windows


def ps_quote(arg: str) -> str:
    """Single-quote for PowerShell (the default OpenSSH shell on Windows): '' escapes a quote."""
    return "'" + arg.replace("'", "''") + "'"


def run_remote(host: str, argv: list[str]) -> int:
    ssh_args, remote_bin, windows = remote_target(host)
    quote = ps_quote if windows else shlex.quote
    cmd = (f"& {quote(remote_bin)} " if windows and " " in remote_bin else remote_bin + " ") + \
        " ".join(quote(a) for a in argv)
    p = subprocess.run(["ssh", "-T", "-o", "BatchMode=yes", *ssh_args, host, cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = p.stdout.strip()
    try:
        data = json.loads(out.splitlines()[-1]) if out else {}
    except json.JSONDecodeError:
        sys.stdout.write(p.stdout)
        sys.stderr.write(p.stderr)
        return p.returncode
    local_dir = Path(tempfile.gettempdir()) / "cctl-remote"
    if argv[:1] == ["--session"] and len(argv) > 1:
        import hashlib
        target = hashlib.sha256(json.dumps([host, remote_bin, argv[1]]).encode()).hexdigest()[:16]
        local_dir = local_dir / "sessions" / target
    local_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    for key in PATH_KEYS:
        remote = data.get(key)
        if isinstance(remote, str) and remote:
            src = remote.replace("\\", "/") if windows else remote
            local = local_dir / f"{host.replace('@', '_')}-{Path(src).name}"
            if subprocess.run(["scp", "-q", "-o", "BatchMode=yes", *ssh_args, f"{host}:{src}", str(local)]
                              ).returncode == 0:
                data[f"remote_{key}"] = remote
                data[key] = str(local)
    print(json.dumps(data, ensure_ascii=False))
    return p.returncode


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252; titles and text are Unicode
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    host = os.environ.get("CCTL_HOST")
    session = os.environ.get("CCTL_SESSION", "")
    while argv[:1] and argv[0] in ("--host", "--session"):
        if len(argv) < 2:
            raise SystemExit(f"{argv[0]} needs a value")
        if argv[0] == "--host":
            host = argv[1]
        else:
            session = argv[1]
        argv = argv[2:]
    if session:
        os.environ["CCTL_SESSION"] = session
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("tools: " + ", ".join(contract.tool_names()))
        return
    if host and argv[0] == "mcp":
        # Remote MCP: stdio passes straight through SSH to cctl on the target.
        ssh_args, remote_bin, windows = remote_target(host)
        quote = ps_quote if windows else shlex.quote
        tail = ["--session", session, "mcp"] if session else ["mcp"]
        remote = (f"& {quote(remote_bin)} " if windows and " " in remote_bin else remote_bin + " ")
        remote += " ".join(quote(a) for a in tail)
        os.execvp("ssh", ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=30", *ssh_args, host,
                          remote])
    if host and argv[0] != "serve":
        raise SystemExit(run_remote(host, (["--session", session] if session else []) + argv))
    if not host:
        session = load().session
    cmd = argv[0]
    if cmd == "mcp":
        from .server import main as mcp_main
        if (session or sys.platform == "win32") and "--direct" not in argv:
            ensure_daemon(load())  # the engine lives in the desktop session; this process only relays MCP
            mcp_main(via_daemon=True)
        else:
            mcp_main()
    elif cmd == "serve":
        from .daemon import serve
        asyncio.run(serve())
    elif cmd == "tools":
        from .providers import create_engine
        supported = create_engine(load()).supported_tools if session else contract.tool_names()
        for t in contract.tools():
            if t['name'] in supported:
                print(f"{t['name']:12s} {t['description'].split('. ')[0]}")
    elif cmd == "session":
        if not session or len(argv) != 2 or argv[1] not in ("start", "status", "stop"):
            raise SystemExit("Use cctl --session NAME session start|status|stop")
        raise SystemExit(run_local("_session", {"action": argv[1]}))
    elif cmd in contract.tool_names():
        raise SystemExit(run_local(cmd, parse_args(argv[1:], contract.schema(cmd))))
    else:
        raise SystemExit(f"unknown command {cmd!r}; try `cctl tools`")


if __name__ == "__main__":
    main()
