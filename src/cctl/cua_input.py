"""Input through Cua's own desktop-coordinate tools: the backend for macOS, Windows and Wayland.

Same interface as x11.X11, so the engine is backend-agnostic. Cua interprets scope="desktop" coordinates in
the pixels of the session's latest get_desktop_state capture; each pointer action therefore refreshes a
native-resolution desktop capture and scales logical screen points by its pixel density (2.0 on Retina).
"""

from __future__ import annotations

import sys

from .results import ToolError
from .x11 import normalize_keys

# xdotool-style names (from normalize_keys) -> Cua key names
KEY_NAMES = {"Return": "return", "Escape": "escape", "Tab": "tab", "BackSpace": "backspace", "Delete": "delete",
             "Insert": "insert", "Home": "home", "End": "end", "Prior": "pageup", "Next": "pagedown", "Up": "up",
             "Down": "down", "Left": "left", "Right": "right", "space": "space"}
MODIFIERS = ("ctrl", "shift", "alt", "super")


def cua_keys(keys: str, platform: str = sys.platform) -> tuple[list[str], str]:
    """'ctrl+shift+t' -> (['ctrl', 'shift'], 't'); 'super' becomes cmd on macOS."""
    parts = normalize_keys(keys).split("+")
    mods = [p for p in parts if p in MODIFIERS]
    rest = [p for p in parts if p not in MODIFIERS]
    if len(rest) != 1:
        raise ToolError("bad_arguments", f"expected modifiers plus one key, got {keys!r}")
    key = rest[0]
    key = KEY_NAMES.get(key, key.lower() if len(key) > 1 else key)
    if platform == "darwin":
        mods = ["cmd" if m == "super" else m for m in mods]
    return mods, key


class CuaInput:
    def __init__(self, engine):
        self.e = engine

    @staticmethod
    def available() -> bool:
        return True

    async def _density(self) -> float:
        """Refresh the desktop capture context; return capture pixels per logical screen point."""
        d = (await self.e.cua.call("get_desktop_state", {"max_image_dimension": 0})).data
        sw, cw = d.get("screen_width") or 0, d.get("screenshot_width") or 0
        return (cw / sw) if sw and cw else float(d.get("scale_factor") or 1.0)

    def _mods(self, modifiers: list[str] | None) -> list[str]:
        out = []
        for m in modifiers or []:
            out.append("cmd" if (m == "super" and sys.platform == "darwin") else m)
        return out

    # ---- pointer ---------------------------------------------------------
    async def move(self, x: int, y: int) -> None:
        """Move the real pointer (hover). macOS: Cua's move_cursor at desktop scope, done by CuaDriver.app, which
        holds the Accessibility grant. Windows: SetCursorPos from cctl itself (it runs in the desktop session
        there; Cua's Windows move_cursor only moves its overlay)."""
        k = await self._density()
        if sys.platform == "win32":
            import ctypes
            if not ctypes.windll.user32.SetCursorPos(round(x * k), round(y * k)):
                raise ToolError("input_failed", "SetCursorPos failed (is cctl running in the desktop session?)")
            return
        if sys.platform != "darwin":
            raise ToolError("unsupported", "hover is not available with this input backend")
        await self.e.cua.call("move_cursor", {"scope": "desktop", "x": x * k, "y": y * k})

    async def pointer(self) -> tuple[int, int] | None:
        """Current real pointer position in logical screen points (for verifying a move)."""
        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes as wt
            pt = wt.POINT()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                k = await self._density()
                return round(pt.x / k), round(pt.y / k)
            return None
        d = (await self.e.cua.call("get_cursor_position", {}, check=False)).data
        return (d["x"], d["y"]) if "x" in d and "y" in d else None

    async def click(self, x: int, y: int, button: str = "left", count: int = 1,
                    modifiers: list[str] | None = None) -> None:
        k = await self._density()
        args = {"scope": "desktop", "x": x * k, "y": y * k, "button": button, "count": count}
        if modifiers:
            args["modifier"] = self._mods(modifiers)
        await self.e.cua.call("click", args)

    async def scroll(self, x: int, y: int, direction: str, amount: int) -> None:
        k = await self._density()
        await self.e.cua.call("scroll", {"scope": "desktop", "x": x * k, "y": y * k, "direction": direction,
                                         "amount": amount})

    async def drag(self, x0: int, y0: int, x1: int, y1: int, button: str = "left", steps: int = 12) -> None:
        k = await self._density()
        await self.e.cua.call("drag", {"scope": "desktop", "from_x": x0 * k, "from_y": y0 * k, "to_x": x1 * k,
                                       "to_y": y1 * k, "button": button})

    # ---- keyboard --------------------------------------------------------
    async def key(self, keys: str, repeat: int = 1, target: tuple[int, int] | None = None) -> None:
        mods, key = cua_keys(keys)
        where = {"pid": target[0], "window_id": target[1]} if target else {"scope": "desktop"}
        for _ in range(repeat):
            if mods:
                await self.e.cua.call("hotkey", {**where, "keys": [*mods, key]})
            else:
                await self.e.cua.call("press_key", {**where, "key": key})

    async def type_ascii(self, text: str) -> None:
        await self.e.cua.call("type_text", {"scope": "desktop", "text": text})

    # ---- windows ---------------------------------------------------------
    async def active_window(self) -> int | None:
        return None  # the engine falls back to the front-most window in the list

    async def activate(self, window_id: int, wait_s: float = 1.0) -> bool:
        w = await self.e._window(window_id)
        await self.e.cua.call("bring_to_front", {"pid": w["pid"], "window_id": window_id})
        return True

    @staticmethod
    def _win32(hwnd: int, msg: str) -> None:
        """Windows: window messages straight to the HWND (cctl runs in the desktop session there)."""
        import ctypes
        user32 = ctypes.windll.user32
        if msg == "close":
            user32.PostMessageW(hwnd, 0x0010, 0, 0)          # WM_CLOSE
        else:
            user32.ShowWindow(hwnd, {"minimize": 6, "maximize": 3}[msg])

    async def close(self, window_id: int) -> None:
        if sys.platform == "win32":  # Cua's alt+F4 goes through a UIA accelerator scan that can time out
            return self._win32(window_id, "close")
        w = await self.e._window(window_id)
        if sys.platform == "darwin":
            # Background-safe: press the window's own close button through accessibility. (Cua refuses process-
            # scoped cmd+w when the app has sibling windows, and won't raise over the user's front app.)
            st = (await self.e.cua.call("get_window_state", {"pid": w["pid"], "window_id": window_id,
                                                             "include_screenshot": False, "max_depth": 2})).data
            b = w["bounds"]
            btns = [e for e in st.get("elements", []) if e.get("role") == "AXButton" and e.get("frame")
                    and e["frame"]["y"] - b["y"] < 40 and e["frame"]["x"] - b["x"] < 40]
            if not btns:
                raise ToolError("unsupported", "could not find this window's close button")
            await self.e.cua.call("click", {"pid": w["pid"], "element_token": btns[0]["element_token"]})
            return
        await self.e.cua.call("bring_to_front", {"pid": w["pid"], "window_id": window_id})
        await self.e.cua.call("hotkey", {"pid": w["pid"], "window_id": window_id, "keys": ["alt", "f4"]})

    async def minimize(self, window_id: int) -> None:
        if sys.platform == "win32":
            return self._win32(window_id, "minimize")
        if sys.platform != "darwin":
            raise ToolError("unsupported", "minimize is not available on this platform yet")
        w = await self.e._window(window_id)
        await self.e.cua.call("hotkey", {"pid": w["pid"], "window_id": window_id, "keys": ["cmd", "m"]})

    async def maximize(self, window_id: int) -> None:
        if sys.platform == "win32":
            return self._win32(window_id, "maximize")
        raise ToolError("unsupported", "maximize is not available on this platform yet; use windows move with a size")

    async def geometry(self, window_id: int) -> dict | None:
        b = (await self.e._window(window_id))["bounds"]
        return {"x": b["x"], "y": b["y"], "width": b["width"], "height": b["height"]}

    async def frame_extents(self, window_id: int) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)

    async def dpms_monitor_on(self) -> bool | None:
        return None
