#!/usr/bin/env python3
"""Native Windows regression: direct logging followed by a Limited controller.

Use a fresh --root on an explicitly available Windows machine. The controller
has a fake companion command, so this checks real ACL/task/daemon behavior
without acquiring, capturing or injecting input into any desktop.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from cctl.cli import daemon_alive, ps_quote, start_isolated_controller
from cctl.config import load
from cctl.daemon import socket_path
from cctl.isolated import IsolatedEngine
from cctl.private_paths import create_private_directory


def powershell(script):
    p = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
    return json.loads(p.stdout) if p.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This acceptance check requires explicitly available Windows")
    root = args.root.absolute()
    if root.exists():
        parser.error("Use a fresh owned root; existing permissions are never changed")
    create_private_directory(root)
    config = root / "config.toml"
    config.write_text('profile = "personal"\nstate_dir = ' + json.dumps(str(root / "state"))
                      + '\ncache_dir = ' + json.dumps(str(root / "cache"))
                      + '\n[sessions.startup]\ncommand = ["unused-companion"]'
                      + '\nid = "owned"\nacquire = "attach"\n', encoding="utf-8")
    os.environ.update(CCTL_CONFIG=str(config), CCTL_SESSION="startup")
    cfg = load()
    engine = IsolatedEngine(cfg)
    # This real dispatch logs an error without ever invoking a provider. It must
    # leave state accessible to the same user's subsequent Limited controller.
    result = asyncio.run(engine.dispatch("unsupported_startup_probe", {}))
    assert result.is_error and result.data["error"] == "unsupported_capability"
    assert (cfg.state_dir / "events.jsonl").is_file()
    report = {"directDispatchLogged": True, "desktopAcquired": False}
    controller = None
    try:
        start_isolated_controller(cfg)
        path = socket_path(cfg)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if path.exists() and daemon_alive(path):
                break
            time.sleep(.1)
        report.update(logExists=(cfg.state_dir / "daemon.log").is_file(),
                      daemonReady=path.exists() and daemon_alive(path))
        assert report["daemonReady"], "Limited controller cannot start after direct logging"
        port = json.loads(path.read_text())["port"]
        controller = powershell(
            "$c=Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort " + str(port)
            + " -State Listen;$ids=@($c|Select-Object -ExpandProperty OwningProcess -Unique);"
            + "if($ids.Count -ne 1){throw 'Unexpected controller identity'};"
            + "$p=Get-Process -Id $ids[0];$w=Get-CimInstance Win32_Process -Filter "
            + "('ProcessId='+$p.Id);@{pid=$p.Id;birth=$p.StartTime.ToUniversalTime().Ticks;"
            + "windowless=($p.MainWindowHandle -eq 0);pythonw=($p.ProcessName -eq 'pythonw');"
            + "expectedLauncher=$w.CommandLine.Contains("
            + ps_quote(str(cfg.state_dir / "controller-launch.py")) + ")}|ConvertTo-Json -Compress")
        assert controller["windowless"] and controller["pythonw"] and controller["expectedLauncher"]
        report.update(windowlessController=True, passed=True)
    finally:
        if controller and controller["expectedLauncher"]:
            powershell("$p=Get-Process -Id " + str(controller["pid"])
                       + ";if($p.StartTime.ToUniversalTime().Ticks -ne " + str(controller["birth"])
                       + "){throw 'Controller identity changed'};Stop-Process -Id $p.Id")
            socket_path(cfg).unlink(missing_ok=True)
            report["ownedControllerRemoved"] = True
        (root / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
