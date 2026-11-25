"""Minimal MCP stdio client that drives `cua-driver mcp` over SSH in one connection.

Session-scoped ids (browser targets, tabs, element tokens) only live as long as
the connection, so multi-step checks run here rather than through `cua-driver call`.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

HOST = os.environ.get("CUA_HOST", "user@linux-vm")
CMD = os.environ.get("CUA_MCP_CMD", "DISPLAY=:0 DO_NOT_TRACK=1 ~/.local/bin/cua-driver mcp")


class Session:
    def __init__(self):
        self.p = subprocess.Popen(["ssh", "-T", "-o", "BatchMode=yes", HOST, CMD],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.next_id = 0
        self.server = self.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "computer-ctrl-smoke", "version": "0"}})
        self.notify("notifications/initialized")

    def notify(self, method, params=None):
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n")

    def request(self, method, params=None):
        self.next_id += 1
        rid = self.next_id
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}) + "\n")
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("server closed the connection")
            msg = json.loads(line)
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def call(self, tool, args=None) -> dict:
        """Returns {'text': [...], 'images': [(mime, b64len)], 'structured': {...}, 'is_error': bool, 'ms': int}."""
        t0 = time.monotonic()
        r = self.request("tools/call", {"name": tool, "arguments": args or {}})
        out = {"text": [], "images": [], "structured": r.get("structuredContent"),
               "is_error": r.get("isError", False), "ms": round((time.monotonic() - t0) * 1000)}
        for c in r.get("content", []):
            if c["type"] == "text":
                out["text"].append(c["text"])
            elif c["type"] == "image":
                out["images"].append((c.get("mimeType"), len(c.get("data", ""))))
        return out

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)
