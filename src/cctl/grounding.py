"""Grounding sidecar: turn "the Save button" into a point, via any OpenAI-compatible vision model.

Contract (H Company's element localization, also fits Qwen3-VL-family grounders): send one image and
a target description at temperature 0; get JSON {"x": int, "y": int} in 0-1000, relative to the exact
image sent. An optional second pass re-asks on a crop around the first answer (zoom refinement), which
H reports gives 10-20% relative gains.

Configured with grounder_url / grounder_model / grounder_api_key_env; the locate tool is hidden when
no grounder is configured.
"""

from __future__ import annotations

import base64
import io
import json
import re
import time
import urllib.request

from PIL import Image

PROMPT = ("Localize an element on the GUI image according to the provided target and output a click position.\n"
          " * You must output a valid JSON following the format: {\"x\": int, \"y\": int}\n"
          " * x and y are integers from 0 to 1000, relative to the image width and height.\n"
          "Your target is: ")
SCHEMA = {"type": "object", "properties": {"x": {"type": "integer", "minimum": 0, "maximum": 1000},
                                           "y": {"type": "integer", "minimum": 0, "maximum": 1000}},
          "required": ["x", "y"], "additionalProperties": False}


def encode(img: Image.Image, max_dim: int) -> tuple[str, tuple[int, int]]:
    """Downscale to max_dim and return (data URL, size actually sent). Coordinates are relative to that image."""
    if max(img.size) > max_dim:
        s = max_dim / max(img.size)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), img.size


def parse_point(text: str) -> tuple[float, float]:
    """Accept {"x":..,"y":..}, a bare [x, y], or <point>x y</point>; values in 0-1000."""
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return float(obj["x"]), float(obj["y"])
        if isinstance(obj, list) and len(obj) >= 2:
            return float(obj[0]), float(obj[1])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    m = re.search(r'"?x"?\s*[:=]\s*(-?\d+(?:\.\d+)?)\D+?"?y"?\s*[:=]\s*(-?\d+(?:\.\d+)?)', text) or \
        re.search(r"(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)", text)
    if not m:
        raise ValueError(f"no point in grounder reply: {text[:200]!r}")
    return float(m.group(1)), float(m.group(2))


class Grounder:
    def __init__(self, url: str, model: str, api_key: str = "", image_max: int = 1280, timeout: float = 60):
        self.url, self.model, self.api_key = url.rstrip("/"), model, api_key
        self.image_max, self.timeout = image_max, timeout

    @property
    def configured(self) -> bool:
        return bool(self.url and self.model)

    def ask(self, img: Image.Image, target: str) -> tuple[float, float, dict]:
        """Point in pixels of `img` for `target`, plus call metadata."""
        data_url, sent = encode(img, self.image_max)
        body = {"model": self.model, "temperature": 0, "max_tokens": 64,
                "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": PROMPT + target}]}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "point", "schema": SCHEMA}}}
        req = urllib.request.Request(f"{self.url}/chat/completions", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            reply = json.loads(r.read())
        text = reply["choices"][0]["message"].get("content") or ""
        nx, ny = parse_point(text)
        nx, ny = min(max(nx, 0), 1000), min(max(ny, 0), 1000)
        meta = {"ms": round((time.monotonic() - t0) * 1000), "sent": list(sent), "raw": text[:120],
                "usage": reply.get("usage")}
        return nx / 1000 * img.width, ny / 1000 * img.height, meta

    def locate(self, img: Image.Image, target: str, refine: bool = True, crop_frac: float = 0.35) -> dict:
        """Point in pixels of `img`. With refine, re-ask on a crop around the first guess (same aspect)."""
        x, y, m1 = self.ask(img, target)
        passes = [{"x": round(x, 1), "y": round(y, 1), **m1}]
        if refine:
            cw, ch = max(64, img.width * crop_frac), max(64, img.height * crop_frac)
            x0 = min(max(0, x - cw / 2), img.width - cw)
            y0 = min(max(0, y - ch / 2), img.height - ch)
            crop = img.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch)))
            cx, cy, m2 = self.ask(crop, target)
            x, y = x0 + cx * (cw / crop.width), y0 + cy * (ch / crop.height)
            passes.append({"x": round(x, 1), "y": round(y, 1), "crop": [round(x0), round(y0), round(cw), round(ch)],
                           **m2})
        return {"x": x, "y": y, "passes": passes}
