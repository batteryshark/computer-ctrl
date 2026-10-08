"""Image frames and coordinate mapping.

Every image handed to the model is a Frame: it records where the image's
pixel (0, 0) sits on the screen and how many screen pixels one image pixel
covers. Coordinates the model reads off an image map back to logical screen
pixels with Frame.to_screen, whatever resizing or cropping happened.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field


@dataclass
class Frame:
    id: str
    kind: str                      # "desktop" | "window" | "region" | "zoom"
    origin_x: float                # screen x of image pixel (0, 0)
    origin_y: float
    scale_x: float                 # screen pixels per image pixel
    scale_y: float
    width: int                     # size of the image the model saw
    height: int
    path: str | None = None        # image as sent
    native_path: str | None = None  # full-resolution original, for zoom(fresh=false)
    window_id: int | None = None
    pid: int | None = None
    extra: dict = field(default_factory=dict)

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        return (round(self.origin_x + x * self.scale_x), round(self.origin_y + y * self.scale_y))

    def from_screen(self, sx: float, sy: float) -> tuple[float, float]:
        return ((sx - self.origin_x) / self.scale_x, (sy - self.origin_y) / self.scale_y)

    def region_to_screen(self, region: list[float]) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = region
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        sx0, sy0 = self.to_screen(x0, y0)
        sx1, sy1 = self.to_screen(x1, y1)
        return sx0, sy0, sx1, sy1

    def describe(self) -> dict:
        return {"frame": self.id, "kind": self.kind, "width": self.width, "height": self.height,
                "screen_origin": [round(self.origin_x), round(self.origin_y)],
                "scale": round(self.scale_x, 4)}


SCREEN = Frame(id="screen", kind="screen", origin_x=0, origin_y=0, scale_x=1, scale_y=1, width=0, height=0)


class FrameStore:
    """Frames issued in one agent session. Ids are short and monotonically numbered."""

    def __init__(self, keep: int = 64):
        self._frames: dict[str, Frame] = {}
        self._order: list[str] = []
        self._counter = itertools.count(1)
        self._keep = keep

    def new_id(self, prefix: str) -> str:
        return f"{prefix}{next(self._counter)}"

    def add(self, frame: Frame) -> Frame:
        self._frames[frame.id] = frame
        self._order.append(frame.id)
        while len(self._order) > self._keep:
            self._frames.pop(self._order.pop(0), None)
        return frame

    def latest(self) -> Frame | None:
        return self._frames[self._order[-1]] if self._order else None

    def get(self, frame_id: str | None) -> Frame:
        """Resolve a frame id; None means the most recent image, "screen" means raw screen pixels."""
        if frame_id in (None, ""):
            f = self.latest()
            if f is None:
                raise LookupError("no image yet: take a screenshot (or pass frame=\"screen\")")
            return f
        if frame_id == "screen":
            return SCREEN
        try:
            return self._frames[frame_id]
        except KeyError:
            raise LookupError(f"unknown or expired frame {frame_id!r}; take a new screenshot") from None


def fit(width: int, height: int, max_dim: int) -> tuple[int, int]:
    """Size that fits within max_dim on the long edge, never upscaling."""
    long_edge = max(width, height)
    if long_edge <= max_dim:
        return width, height
    s = max_dim / long_edge
    return max(1, round(width * s)), max(1, round(height * s))


def magnify(width: int, height: int, max_dim: int, max_factor: float = 4.0) -> tuple[int, int]:
    """Size that fills max_dim on the long edge, upscaling at most max_factor."""
    long_edge = max(width, height)
    s = min(max_dim / long_edge, max_factor)
    return max(1, round(width * s)), max(1, round(height * s))
