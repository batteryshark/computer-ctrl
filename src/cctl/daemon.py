"""Background service for the CLI: one Engine shared by successive `cctl <tool>` calls.

Frames, element tokens and the Cua connection persist between CLI calls,
so `cctl screenshot` followed by `cctl click --x 10 --y 20` works.
Protocol: one JSON request line {"tool", "args"} -> one JSON response line.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from .config import Config, load
from .engine import Engine

IDLE_EXIT_S = 30 * 60


def socket_path(cfg: Config) -> Path:
    return cfg.cache_dir / "cctl.sock"


async def serve(cfg: Config | None = None) -> None:
    cfg = cfg or load()
    engine = Engine(cfg)
    path = socket_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    last = time.monotonic()
    lock = asyncio.Lock()  # one action at a time: it is one desktop

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal last
        try:
            line = await reader.readline()
            req = json.loads(line)
            async with lock:
                result = await engine.dispatch(req["tool"], req.get("args") or {})
            last = time.monotonic()
            resp = {"data": result.data, "is_error": result.is_error}
            writer.write((json.dumps(resp, ensure_ascii=False) + "\n").encode())
            await writer.drain()
        except Exception as e:  # noqa: BLE001
            writer.write((json.dumps({"data": {"error": "daemon_error", "message": str(e)}, "is_error": True}) + "\n")
                         .encode())
        finally:
            writer.close()

    server = await asyncio.start_unix_server(handle, path=str(path), limit=64 * 1024 * 1024)
    os.chmod(path, 0o600)
    async with server:
        while time.monotonic() - last < IDLE_EXIT_S:
            await asyncio.sleep(30)
    await engine.close()
    path.unlink(missing_ok=True)


async def request(cfg: Config, tool: str, args: dict, timeout: float = 300) -> dict:
    reader, writer = await asyncio.open_unix_connection(str(socket_path(cfg)), limit=64 * 1024 * 1024)
    writer.write((json.dumps({"tool": tool, "args": args}) + "\n").encode())
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout)
    writer.close()
    return json.loads(line)
