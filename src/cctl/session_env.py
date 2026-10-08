"""Find the graphical session to drive, and keep the Cua daemon running inside it.

Agents usually arrive over SSH with no DISPLAY. The session's environment is
copied from a process already running in it (Cua cannot do this itself:
trycua/cua#3047).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path

SESSION_VARS = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR",
                "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "XDG_SESSION_ID", "AT_SPI_BUS_ADDRESS")

# Processes that live for the whole graphical session, best first.
SESSION_PROCESSES = ("xfce4-session", "gnome-session-binary", "gnome-shell", "plasmashell", "ksmserver",
                     "kwin_wayland", "kwin_x11", "sway", "Hyprland", "niri", "labwc", "cinnamon-session",
                     "mate-session", "lxqt-session", "xfwm4", "openbox", "i3")


def _environ(pid: int) -> dict[str, str]:
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return {}
    out = {}
    for item in raw.split(b"\0"):
        k, sep, v = item.partition(b"=")
        if sep:
            out[k.decode(errors="replace")] = v.decode(errors="replace")
    return out


def discover() -> dict[str, str]:
    """Session variables for this user's graphical session. Existing env wins when DISPLAY/WAYLAND_DISPLAY is set."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return {k: os.environ[k] for k in SESSION_VARS if k in os.environ}
    uid = os.getuid()
    candidates: list[tuple[int, dict]] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
            name = (proc / "comm").read_text().strip()
        except OSError:
            continue
        if name in SESSION_PROCESSES:
            env = _environ(int(proc.name))
            if env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"):
                candidates.append((SESSION_PROCESSES.index(name), env))
    if not candidates:
        return {}
    env = sorted(candidates, key=lambda c: c[0])[0][1]
    found = {k: env[k] for k in SESSION_VARS if k in env}
    found.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    if "DBUS_SESSION_BUS_ADDRESS" not in found and Path(f"/run/user/{uid}/bus").exists():
        found["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
    return found


def child_env(session: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(session)
    env["DO_NOT_TRACK"] = "1"                   # Cua telemetry off
    env["CUA_DRIVER_RS_UPDATE_CHECK"] = "false"  # no update pings
    return env


def cua_daemon_running(cua_bin: str, env: dict) -> bool:
    try:
        out = subprocess.run([cua_bin, "status"], env=env, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "is running" in out.stdout


async def ensure_cua_daemon(cua_bin: str, socket: str, env: dict, log_path: Path) -> None:
    """Start `cua-driver serve` inside the session if it is not already running (trycua/cua#3957)."""
    if await asyncio.to_thread(cua_daemon_running, cua_bin, env):
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log:
        subprocess.Popen([cua_bin, "serve", "--no-overlay", "--socket", socket], env=env,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if Path(socket).exists() and await asyncio.to_thread(cua_daemon_running, cua_bin, env):
            return
        await asyncio.sleep(0.3)
    raise RuntimeError(f"cua-driver daemon did not start; see {log_path}")
