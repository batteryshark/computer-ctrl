"""Load the tool contract (contract/tools.json), the single source of truth for tool names and schemas."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path


@cache
def load() -> dict:
    packaged = resources.files("cctl").joinpath("tools.json")
    if packaged.is_file():
        return json.loads(packaged.read_text())
    # Editable install / source checkout: <repo>/src/cctl/contract.py -> <repo>/contract/tools.json
    return json.loads((Path(__file__).resolve().parents[2] / "contract" / "tools.json").read_text())


def tools() -> list[dict]:
    return load()["tools"]


def tool_names() -> list[str]:
    return [t["name"] for t in tools()]


def schema(name: str) -> dict:
    for t in tools():
        if t["name"] == name:
            return t["inputSchema"]
    raise KeyError(name)
