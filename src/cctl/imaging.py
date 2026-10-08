"""Image helpers: decode, resize, crop, black-frame detection."""

from __future__ import annotations

import base64
import io

from PIL import Image, ImageStat

from .frames import fit, magnify


def decode_b64(data: str) -> Image.Image:
    img = Image.open(io.BytesIO(base64.b64decode(data)))
    img.load()
    return img


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def downscale(img: Image.Image, max_dim: int) -> Image.Image:
    w, h = fit(*img.size, max_dim)
    return img if (w, h) == img.size else img.resize((w, h), Image.Resampling.LANCZOS)


def enlarge(img: Image.Image, max_dim: int, max_factor: float = 4.0) -> Image.Image:
    w, h = magnify(*img.size, max_dim, max_factor)
    return img if (w, h) == img.size else img.resize((w, h), Image.Resampling.LANCZOS)


def is_blank(img: Image.Image) -> bool:
    """True for an all-black (or nearly uniform dark) frame, as produced by a locked or powered-off display."""
    gray = img.convert("L")
    small = gray.resize((min(256, gray.width), min(256, gray.height)))
    stat = ImageStat.Stat(small)
    return stat.mean[0] < 3 and stat.stddev[0] < 2


def changed_fraction(a: Image.Image, b: Image.Image, threshold: int = 16) -> float:
    """Fraction of pixels whose grayscale value differs by more than threshold (on a 256-px thumbnail)."""
    size = (256, max(1, round(256 * a.height / a.width)))
    ga = a.convert("L").resize(size)
    gb = b.convert("L").resize(size)
    da, db = ga.tobytes(), gb.tobytes()
    diff = sum(1 for p, q in zip(da, db) if abs(p - q) > threshold)
    return diff / len(da)
