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
        raise ToolError("unsupported", "hover (pointer move without click) is not available on this platform yet")

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
    async def key(self, keys: str, repeat: int = 1) -> None:
        mods, key = cua_keys(keys)
        for _ in range(repeat):
            if mods:
                await self.e.cua.call("hotkey", {"scope": "desktop", "keys": [*mods, key]})
            else:
                await self.e.cua.call("press_key", {"scope": "desktop", "key": key})

    async def type_ascii(self, text: str) -> None:
        await self.e.cua.call("type_text", {"scope": "desktop", "text": text})

    # ---- windows ---------------------------------------------------------
    async def active_window(self) -> int | None:
        return None  # the engine falls back to the front-most window in the list

    async def activate(self, window_id: int, wait_s: float = 1.0) -> bool:
        w = await self.e._window(window_id)
        await self.e.cua.call("bring_to_front", {"pid": w["pid"], "window_id": window_id})
        return True

    async def close(self, window_id: int) -> None:
        w = await self.e._window(window_id)
        await self.e.cua.call("bring_to_front", {"pid": w["pid"], "window_id": window_id})
        keys = ["cmd", "w"] if sys.platform == "darwin" else ["alt", "f4"]
        await self.e.cua.call("hotkey", {"pid": w["pid"], "window_id": window_id, "keys": keys})

    async def minimize(self, window_id: int) -> None:
        if sys.platform != "darwin":
            raise ToolError("unsupported", "minimize is not available on this platform yet")
        w = await self.e._window(window_id)
        await self.e.cua.call("hotkey", {"pid": w["pid"], "window_id": window_id, "keys": ["cmd", "m"]})

    async def maximize(self, window_id: int) -> None:
        raise ToolError("unsupported", "maximize is not available on this platform yet; use windows move with a size")

    async def geometry(self, window_id: int) -> dict | None:
        b = (await self.e._window(window_id))["bounds"]
        return {"x": b["x"], "y": b["y"], "width": b["width"], "height": b["height"]}

    async def frame_extents(self, window_id: int) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)

    async def dpms_monitor_on(self) -> bool | None:
        return None
