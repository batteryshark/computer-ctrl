"""Background service for the CLI: one Engine shared by successive `cctl <tool>` calls.

Frames, element tokens and the Cua connection persist between CLI calls,
so `cctl screenshot` followed by `cctl click --x 10 --y 20` works.
Protocol: one JSON request line {"tool", "args"} -> one JSON response line.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path

from .config import Config, load
from .engine import Engine

IDLE_EXIT_S = 30 * 60


USE_TCP = sys.platform == "win32"  # asyncio has no Unix sockets on Windows: loopback TCP + token instead


def socket_path(cfg: Config) -> Path:
    return cfg.cache_dir / ("cctl.port" if USE_TCP else "cctl.sock")


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
            if USE_TCP and req.get("token") != token:
                raise PermissionError("bad token")
            async with lock:
                result = await engine.dispatch(req["tool"], req.get("args") or {})
            last = time.monotonic()
            resp = {"data": result.data, "is_error": result.is_error}
            if req.get("inline"):  # an MCP front-end proxying to this daemon wants the media itself
                import base64
                if result.image is not None:
                    resp["image"], resp["mime"] = base64.b64encode(result.image).decode(), result.mime
                if result.audio is not None:
                    resp["audio"], resp["audio_mime"] = base64.b64encode(result.audio).decode(), result.audio_mime
            writer.write((json.dumps(resp, ensure_ascii=False) + "\n").encode())
            await writer.drain()
        except Exception as e:  # noqa: BLE001
            writer.write((json.dumps({"data": {"error": "daemon_error", "message": str(e)}, "is_error": True}) + "\n")
                         .encode())
        finally:
            writer.close()

    token = secrets.token_urlsafe(24)
    if USE_TCP:
        server = await asyncio.start_server(handle, host="127.0.0.1", port=0, limit=64 * 1024 * 1024)
        port = server.sockets[0].getsockname()[1]
        path.write_text(json.dumps({"port": port, "token": token}))
    else:
        server = await asyncio.start_unix_server(handle, path=str(path), limit=64 * 1024 * 1024)
    os.chmod(path, 0o600)
    async with server:
        while time.monotonic() - last < IDLE_EXIT_S:
            await asyncio.sleep(30)
    await engine.close()
    path.unlink(missing_ok=True)


async def request(cfg: Config, tool: str, args: dict, timeout: float = 300, inline: bool = False) -> dict:
    msg = {"tool": tool, "args": args, **({"inline": True} if inline else {})}
    if USE_TCP:
        info = json.loads(socket_path(cfg).read_text())
        msg["token"] = info["token"]
        reader, writer = await asyncio.open_connection("127.0.0.1", info["port"], limit=64 * 1024 * 1024)
    else:
        reader, writer = await asyncio.open_unix_connection(str(socket_path(cfg)), limit=64 * 1024 * 1024)
    writer.write((json.dumps(msg) + "\n").encode())
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout)
    writer.close()
    return json.loads(line)


class RemoteEngine:
    """Engine stand-in that forwards tool calls to the session-resident daemon (used by `cctl mcp` on Windows,
    where an SSH session cannot see the interactive desktop)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    async def dispatch(self, name: str, args: dict | None):
        import base64
        from .results import ToolResult
        resp = await request(self.cfg, name, args or {}, inline=True)
        return ToolResult(data=resp.get("data", {}), is_error=bool(resp.get("is_error")),
                          image=base64.b64decode(resp["image"]) if resp.get("image") else None,
                          mime=resp.get("mime", "image/png"),
                          audio=base64.b64decode(resp["audio"]) if resp.get("audio") else None,
                          audio_mime=resp.get("audio_mime", "audio/wav"))

    async def close(self) -> None:
        pass
