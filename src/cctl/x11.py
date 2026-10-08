"""X11 helpers: real input via xdotool, EWMH window ops, and display/session health.

On X11, xdotool's real pointer/keyboard events reach every app (canvas,
Electron, games) the way a person's input does, so pixel actions use it.
Element actions and capture stay with Cua.
"""

from __future__ import annotations

import asyncio
import re
import shutil

BUTTONS = {"left": 1, "middle": 2, "right": 3}
WHEEL = {"up": 4, "down": 5, "left": 6, "right": 7}
MODIFIER_KEYS = {"ctrl": "ctrl", "shift": "shift", "alt": "alt", "super": "super"}


# No `mousemove --sync`: it waits for a core-pointer motion event and, with Cua's XInput2 virtual pointers
# present, routinely times out after ~15 s. A short sleep after moving is enough for the server to settle.
SETTLE = "0.03"


class X11:
    def __init__(self, env: dict):
        self.env = env

    @staticmethod
    def available() -> bool:
        return shutil.which("xdotool") is not None

    async def run(self, *args: str, timeout: float = 30, check: bool = True) -> str:
        proc = await asyncio.create_subprocess_exec(*args, env=self.env, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
        if check and proc.returncode != 0:
            raise RuntimeError(f"{args[0]} {' '.join(args[1:3])}…: {err.decode().strip() or proc.returncode}")
        return out.decode()

    # ---- pointer ---------------------------------------------------------
    async def move(self, x: int, y: int) -> None:
        await self.run("xdotool", "mousemove", str(x), str(y), "sleep", SETTLE)

    async def click(self, x: int, y: int, button: str = "left", count: int = 1,
                    modifiers: list[str] | None = None) -> None:
        mods = [MODIFIER_KEYS[m] for m in modifiers or []]
        args = ["xdotool", "mousemove", str(x), str(y), "sleep", SETTLE]
        if mods:
            args += ["keydown", "+".join(mods)]
        args += ["click", "--repeat", str(count), "--delay", "80", str(BUTTONS[button])]
        if mods:
            args += ["keyup", "+".join(mods)]
        await self.run(*args)

    async def pointer(self) -> tuple[int, int] | None:
        out = await self.run("xdotool", "getmouselocation", "--shell", check=False)
        g = dict(line.split("=", 1) for line in out.split() if "=" in line)
        return (int(g["X"]), int(g["Y"])) if "X" in g and "Y" in g else None

    async def scroll(self, x: int, y: int, direction: str, amount: int) -> None:
        await self.run("xdotool", "mousemove", str(x), str(y), "sleep", SETTLE,
                       "click", "--repeat", str(amount), "--delay", "30", str(WHEEL[direction]))

    async def drag(self, x0: int, y0: int, x1: int, y1: int, button: str = "left", steps: int = 12) -> None:
        b = str(BUTTONS[button])
        await self.run("xdotool", "mousemove", str(x0), str(y0), "sleep", SETTLE, "mousedown", b)
        for i in range(1, steps + 1):
            await self.run("xdotool", "mousemove",
                           str(round(x0 + (x1 - x0) * i / steps)), str(round(y0 + (y1 - y0) * i / steps)))
            await asyncio.sleep(0.01)
        await self.run("xdotool", "mouseup", b)

    # ---- keyboard --------------------------------------------------------
    async def key(self, keys: str, repeat: int = 1, target: tuple[int, int] | None = None) -> None:
        if target:  # focus the window first; real key events go to the focused window on X11
            await self.activate(target[1])
        await self.run("xdotool", "key", "--clearmodifiers", "--repeat", str(repeat), "--delay", "40",
                       normalize_keys(keys))

    async def type_ascii(self, text: str) -> None:
        await self.run("xdotool", "type", "--clearmodifiers", "--delay", "8", "--", text,
                       timeout=30 + len(text) * 0.05)

    # ---- windows ---------------------------------------------------------
    async def active_window(self) -> int | None:
        out = await self.run("xdotool", "getactivewindow", check=False)
        return int(out.strip()) if out.strip().isdigit() else None

    async def activate(self, window_id: int, wait_s: float = 1.0) -> bool:
        """Ask the WM to activate a window and wait briefly for it. Not `--sync`: for transient dialogs some
        WMs never report the dialog itself as active, and `--sync` then blocks for ~15 s."""
        await self.run("xdotool", "windowactivate", str(window_id), check=False, timeout=5)
        deadline = asyncio.get_running_loop().time() + wait_s
        while asyncio.get_running_loop().time() < deadline:
            if await self.active_window() == window_id:
                return True
            await asyncio.sleep(0.05)
        return False

    async def geometry(self, window_id: int) -> dict | None:
        """Client-area geometry straight from the X server (Cua's list can briefly echo a requested move)."""
        out = await self.run("xdotool", "getwindowgeometry", "--shell", str(window_id), check=False)
        g = dict(line.split("=", 1) for line in out.split() if "=" in line)
        try:
            return {"x": int(g["X"]), "y": int(g["Y"]), "width": int(g["WIDTH"]), "height": int(g["HEIGHT"])}
        except (KeyError, ValueError):
            return None

    async def frame_extents(self, window_id: int) -> tuple[int, int, int, int]:
        """(left, right, top, bottom) decoration sizes the WM reports via _NET_FRAME_EXTENTS; zeros if none."""
        out = await self.run("xprop", "-id", str(window_id), "_NET_FRAME_EXTENTS", check=False)
        m = re.search(r"=\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)", out)
        return tuple(int(v) for v in m.groups()) if m else (0, 0, 0, 0)

    async def minimize(self, window_id: int) -> None:
        await self.run("xdotool", "windowminimize", str(window_id))

    async def close(self, window_id: int) -> None:
        if shutil.which("wmctrl"):
            await self.run("wmctrl", "-ic", hex(window_id))
        else:
            await self.run("xdotool", "windowclose", str(window_id))

    async def maximize(self, window_id: int) -> None:
        await self.run("wmctrl", "-ir", hex(window_id), "-b", "add,maximized_vert,maximized_horz")

    # ---- health ----------------------------------------------------------
    async def dpms_monitor_on(self) -> bool | None:
        out = await self.run("xset", "q", check=False)
        m = re.search(r"Monitor is (\w+)", out)
        return None if not m else m.group(1).lower() == "on"


KEY_ALIASES = {
    "enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape", "tab": "Tab",
    "backspace": "BackSpace", "delete": "Delete", "del": "Delete", "space": "space", "up": "Up",
    "down": "Down", "left": "Left", "right": "Right", "home": "Home", "end": "End", "pageup": "Prior",
    "pagedown": "Next", "pgup": "Prior", "pgdn": "Next", "insert": "Insert", "cmd": "super", "win": "super",
    "meta": "super", "control": "ctrl", "option": "alt",
}


def normalize_keys(keys: str) -> str:
    """'Ctrl+Shift+T' / 'cmd+s' / 'enter' -> xdotool names ('ctrl+shift+t', 'super+s', 'Return')."""
    parts = [p.strip() for p in keys.replace(" ", "").split("+") if p.strip()]
    out = []
    for p in parts:
        low = p.lower()
        if low in ("ctrl", "shift", "alt", "super"):
            out.append(low)
        elif low in KEY_ALIASES:
            out.append(KEY_ALIASES[low])
        elif re.fullmatch(r"f\d{1,2}", low):
            out.append(low.upper())
        elif len(p) == 1:
            out.append(p.lower() if len(parts) > 1 else p)
        else:
            out.append(p)
    return "+".join(out)


async def session_state(display: str, env: dict) -> dict:
    """Which logind session owns `display`, and whether it is the active (unlocked, foreground) one."""
    async def run(*args: str) -> str:
        proc = await asyncio.create_subprocess_exec(*args, env=env, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL)
        out, _ = await proc.communicate()
        return out.decode()

    listing = await run("loginctl", "list-sessions", "--no-legend")
    for line in listing.splitlines():
        sid = line.split()[0] if line.split() else None
        if not sid:
            continue
        props = await run("loginctl", "show-session", sid, "-p", "Display", "-p", "Active", "-p", "LockedHint",
                          "-p", "Type", "-p", "Name")
        kv = dict(p.split("=", 1) for p in props.splitlines() if "=" in p)
        if kv.get("Display") == display:
            return {"session": sid, "user": kv.get("Name"), "type": kv.get("Type"),
                    "active": kv.get("Active") == "yes", "locked": kv.get("LockedHint") == "yes"}
    return {}
