"""MCP stdio front-end. Tool list comes straight from the contract.

Results are one text block (JSON) plus at most one image, and never use
structuredContent/outputSchema: the shape every harness forwards intact.
"""

from __future__ import annotations

import asyncio
import base64
import json

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import __version__, contract
from .config import load
from .engine import Engine
from .results import ToolResult


def render(result: ToolResult) -> types.CallToolResult:
    content: list = [types.TextContent(type="text", text=json.dumps(result.data, ensure_ascii=False))]
    if result.image is not None:
        content.append(types.ImageContent(type="image", data=base64.b64encode(result.image).decode(),
                                          mimeType=result.mime))
    if result.audio is not None:
        content.append(types.AudioContent(type="audio", data=base64.b64encode(result.audio).decode(),
                                          mimeType=result.audio_mime))
    return types.CallToolResult(content=content, isError=result.is_error)


def build(engine: Engine) -> Server:
    visible = [t for t in contract.tools() if engine.cfg.shell_enabled or t["name"] != "run"]

    async def list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[
            types.Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"]) for t in visible])

    async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        return render(await engine.dispatch(params.name, params.arguments or {}))

    conventions = contract.load()["conventions"]
    instructions = "Computer-use tools for one desktop. " + " ".join(conventions.values())
    return Server("cctl", version=__version__, instructions=instructions,
                  on_list_tools=list_tools, on_call_tool=call_tool)


async def serve_stdio() -> None:
    engine = Engine(load())
    server = build(engine)
    try:
        async with stdio_server() as (r, w):
            await server.run(r, w, server.create_initialization_options())
    finally:
        await engine.close()


def main() -> None:
    asyncio.run(serve_stdio())
