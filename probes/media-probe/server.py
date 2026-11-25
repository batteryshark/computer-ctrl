# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.3,<3", "pillow>=10"]
# ///
"""Media-probe MCP server.

Measures what a harness actually forwards to its model from MCP tool results.
Each tool hides a fresh random code inside one kind of media; the model can only
report the code if that media reached it. Codes are written to $PROBE_CODES_FILE
(JSON) so a runner can grade the transcript afterwards.
"""

import asyncio
import base64
import io
import json
import os
import random
import shutil
import string
import subprocess
import tempfile
from pathlib import Path

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from PIL import Image, ImageDraw, ImageFont

NATO = {c: w for c, w in zip(string.ascii_uppercase, (
    "alfa bravo charlie delta echo foxtrot golf hotel india juliett kilo lima mike "
    "november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu").split())}
DIGITS = "zero one two three four five six seven eight nine".split()

WORK = Path(tempfile.mkdtemp(prefix="media-probe-"))
CODES_FILE = Path(os.environ.get("PROBE_CODES_FILE", WORK / "codes.json"))


def new_code() -> str:
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L confusion
    return "".join(random.choice(alphabet) for _ in range(5))


TOOLS = {
    "probe_image": "Image content + text. Media: PNG with the code.",
    "probe_image_structured": "Image content + text + structuredContent (outputSchema declared).",
    "probe_audio": "Audio content (WAV). The code is spoken using the NATO alphabet.",
    "probe_video_blob": "Embedded resource blob, mimeType video/mp4, showing the code.",
    "probe_resource_link": "resource_link to a PNG file containing the code.",
    "probe_image_path": "Text only: a file path to a PNG with the code (CLI pattern; view it with your own image tool).",
    "probe_structured_only": "The code is only in structuredContent; the text block is a one-line summary (Cua's browser-snapshot shape).",
}
CODES = {name: new_code() for name in TOOLS}
CODES_FILE.write_text(json.dumps(CODES, indent=2))


def font(size: int):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def code_png(code: str, label: str) -> bytes:
    img = Image.new("RGB", (800, 300), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 30), f"{label}: the code is", fill="black", font=font(36))
    d.text((40, 110), code, fill="#c00000", font=font(120))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def spoken(code: str) -> str:
    return "The code is: " + ", ".join(NATO.get(c) or DIGITS[int(c)] for c in code) + "."


def code_wav(code: str) -> bytes | None:
    out = WORK / "code.wav"
    text = spoken(code)
    if shutil.which("say"):
        cmd = ["say", "-o", str(out), "--data-format=LEI16@16000", text]
    elif shutil.which("espeak-ng"):
        cmd = ["espeak-ng", "-w", str(out), text]
    else:
        return None
    subprocess.run(cmd, check=True, capture_output=True)
    return out.read_bytes()


def code_mp4(code: str) -> bytes | None:
    if not shutil.which("ffmpeg"):
        return None
    png = WORK / "frame.png"
    png.write_bytes(code_png(code, "video"))
    out = WORK / "code.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", str(png), "-t", "3",
                    "-r", "10", "-pix_fmt", "yuv420p", "-c:v", "libx264", str(out)],
                   check=True, capture_output=True)
    return out.read_bytes()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


INSTRUCTION = "Report the code contained in the attached media. If no media reached you, say NONE. Do not guess."

async def list_tools(ctx, params) -> types.ListToolsResult:
    tools = []
    for name, desc in TOOLS.items():
        extra = {}
        if name in ("probe_image_structured", "probe_structured_only"):
            extra["outputSchema"] = {"type": "object", "properties": {"note": {"type": "string"}, "code": {"type": "string"}},
                                     "required": ["note"]}
        tools.append(types.Tool(name=name, description=desc,
                                inputSchema={"type": "object", "properties": {}}, **extra))
    return types.ListToolsResult(tools=tools)


async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    return types.CallToolResult(**content_for(params.name))


def content_for(name: str) -> dict:
    code = CODES[name]
    text = types.TextContent(type="text", text=INSTRUCTION)
    if name == "probe_image":
        return {"content": [text, types.ImageContent(type="image", data=b64(code_png(code, name)), mimeType="image/png")]}
    if name == "probe_image_structured":
        return {"content": [text, types.ImageContent(type="image", data=b64(code_png(code, name)), mimeType="image/png")],
                "structuredContent": {"note": "The code is only in the image, not in this object."}}
    if name == "probe_audio":
        wav = code_wav(code)
        if wav is None:
            return {"content": [types.TextContent(type="text", text="SKIPPED: no TTS available on this host")]}
        return {"content": [text, types.AudioContent(type="audio", data=b64(wav), mimeType="audio/wav")]}
    if name == "probe_video_blob":
        mp4 = code_mp4(code)
        if mp4 is None:
            return {"content": [types.TextContent(type="text", text="SKIPPED: no ffmpeg on this host")]}
        return {"content": [text, types.EmbeddedResource(type="resource", resource=types.BlobResourceContents(
            uri=f"file://{WORK / 'code.mp4'}", mimeType="video/mp4", blob=b64(mp4)))]}
    if name == "probe_resource_link":
        p = WORK / "link.png"
        p.write_bytes(code_png(code, name))
        return {"content": [text, types.ResourceLink(type="resource_link", uri=f"file://{p}", name="link.png",
                                                     mimeType="image/png")]}
    if name == "probe_image_path":
        p = WORK / "path.png"
        p.write_bytes(code_png(code, name))
        return {"content": [types.TextContent(type="text", text=json.dumps(
            {"screenshot_path": str(p), "width": 800, "height": 300,
             "hint": "View this file with your image-viewing tool, then report the code."}))]}
    if name == "probe_structured_only":
        return {"content": [types.TextContent(type="text", text="probe result: 1 code available in structured output")],
                "structuredContent": {"note": "This is the code.", "code": code}}
    raise ValueError(f"unknown tool {name}")


server = Server("media-probe", on_list_tools=list_tools, on_call_tool=call_tool)


async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
