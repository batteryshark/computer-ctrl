"""Choosing how to enter text.

Phase 0 showed synthetic key events cannot be trusted with non-ASCII text on
X11: Cua's AT-SPI route drops it and its key route types the wrong
characters, both while reporting success. Plain ASCII goes as key events;
anything else is pasted (or set as the element's value when asked).
"""

from __future__ import annotations

TERMINAL_APPS = {
    "zutty", "xfce4-terminal", "gnome-terminal", "gnome-terminal-server", "konsole", "xterm", "uxterm",
    "alacritty", "kitty", "wezterm", "wezterm-gui", "foot", "tilix", "terminator", "urxvt", "rxvt",
    "st", "lxterminal", "mate-terminal", "qterminal", "terminology", "ghostty", "ptyxis", "kgx",
}


def is_key_safe(text: str) -> bool:
    """Printable ASCII plus newline/tab: the characters every keyboard map can produce directly."""
    return all(c in "\n\t" or 0x20 <= ord(c) < 0x7F for c in text)


def choose_route(text: str, mode: str = "auto", has_element: bool = False) -> str:
    if mode in ("keys", "paste", "set_value"):
        if mode == "set_value" and not has_element:
            raise ValueError("mode=set_value needs an element")
        return mode
    return "keys" if is_key_safe(text) else "paste"


def paste_keys(app_name: str | None) -> str:
    """Terminals paste with ctrl+shift+v; everything else with ctrl+v."""
    name = (app_name or "").lower()
    return "ctrl+shift+v" if name in TERMINAL_APPS or "term" in name else "ctrl+v"
