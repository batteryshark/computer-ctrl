"""Async MCP client for `cua-driver mcp --socket ...`.

One long-lived connection per agent session: Cua's session labels, element
tokens and browser ids only live as long as the connection.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

PROTOCOL = "2025-06-18"
STREAM_LIMIT = 256 * 1024 * 1024  # native screenshots arrive as one base64 line


class CuaError(RuntimeError):
    def __init__(self, tool: str, message: str, data: dict | None = None):
        super().__init__(f"{tool}: {message}")
        self.tool = tool
        self.data = data or {}


@dataclass
class CuaResult:
    text: list[str] = field(default_factory=list)
    images: list[tuple[str, str]] = field(default_factory=list)  # (mime, base64)
    structured: dict | None = None
    is_error: bool = False

    @property
    def data(self) -> dict:
        """structuredContent, or the first text block parsed as JSON."""
        if self.structured is not None:
            return self.structured
        for t in self.text:
            try:
                value = json.loads(t)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return {"text": "\n".join(self.text)}

    @property
    def summary(self) -> str:
        return self.data.get("summary") or "\n".join(self.text)[:500]


class CuaClient:
    def __init__(self, cua_bin: str, socket: str, env: dict, stderr_log: Path):
        self.cmd = [cua_bin, "mcp", "--socket", socket]
        self.env = env
        self.stderr_log = stderr_log
        self.session = "cctl-" + uuid.uuid4().hex[:8]
        self._proc: asyncio.subprocess.Process | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next = 0
        self._reader: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.server_info: dict = {}

    async def start(self) -> None:
        self.stderr_log.parent.mkdir(parents=True, exist_ok=True)
        err = open(self.stderr_log, "ab")
        self._proc = await asyncio.create_subprocess_exec(
            *self.cmd, env=self.env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=err, limit=STREAM_LIMIT)
        self._reader = asyncio.create_task(self._read_loop())
        init = await self._request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                                  "clientInfo": {"name": "cctl", "version": "0.1.0"}})
        self.server_info = init.get("serverInfo", {})
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def _send(self, msg: dict) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self._proc.stdin.drain()

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                fut = self._pending.pop(msg["id"], None)
                if fut and not fut.done():
                    fut.set_result(msg)
            elif "id" in msg and "method" in msg:
                # Server-to-client request (roots, elicitation, ...): not supported.
                await self._send({"jsonrpc": "2.0", "id": msg["id"],
                                  "error": {"code": -32601, "message": "not supported by cctl"}})
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError("cua-driver mcp exited"))
        self._pending.clear()

    async def _request(self, method: str, params: dict, timeout: float = 120) -> dict:
        self._next += 1
        rid = self._next
        fut = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        msg = await asyncio.wait_for(fut, timeout)
        if "error" in msg:
            raise CuaError(method, msg["error"].get("message", str(msg["error"])), msg["error"])
        return msg["result"]

    async def call(self, tool: str, args: dict | None = None, timeout: float = 120,
                   check: bool = True) -> CuaResult:
        args = {"session": self.session, **(args or {})}
        async with self._lock:
            if not self.alive:
                await self.start()
        r = await self._request("tools/call", {"name": tool, "arguments": args}, timeout)
        if r.get("isError") and "session has ended" in json.dumps(r.get("content", [])):
            # Cua ends idle lifecycle sessions and ordinary actions never revive them; start_session does.
            await self._request("tools/call", {"name": "start_session", "arguments": {"session": self.session}}, 30)
            r = await self._request("tools/call", {"name": tool, "arguments": args}, timeout)
        out = CuaResult(structured=r.get("structuredContent"), is_error=bool(r.get("isError")))
        for c in r.get("content", []):
            if c.get("type") == "text":
                out.text.append(c["text"])
            elif c.get("type") == "image":
                out.images.append((c.get("mimeType", "image/png"), c["data"]))
        if check:
            d = out.data if isinstance(out.data, dict) else {}
            # Cua reports refusals three ways: isError, {"refusal": {...}} / status=refused, and
            # {"effect": "refused", "error": {...}} (browser tools).
            problem = d.get("refusal") or (d.get("error") if isinstance(d.get("error"), dict) else None)
            if out.is_error or problem or d.get("status") == "refused" or d.get("effect") == "refused":
                message = (problem or {}).get("message") or d.get("message") or d.get("summary") or "\n".join(out.text)
                raise CuaError(tool, message or "failed", d)
        return out

    async def close(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.stdin.close()
            try:
                await asyncio.wait_for(self._proc.wait(), 5)
            except asyncio.TimeoutError:
                self._proc.kill()
