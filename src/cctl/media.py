"""Media capture for models that can't take video or audio directly: screen clips summarized as an
annotated contact sheet, system/mic audio summarized as levels (plus an optional transcript), and OCR.

Raw MP4/WAV files are always saved, and their paths returned, for harnesses and models that can
use them. Capture goes through ffmpeg (x11grab + PulseAudio on Linux; other platforms in Phase 4).
"""

from __future__ import annotations

import array
import asyncio
import math
import shutil
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import imaging

MAX_CLIP_S = 300
MAX_AUDIO_S = 600


@dataclass
class Recording:
    id: str
    kind: str                 # "clip" | "audio"
    path: Path
    proc: asyncio.subprocess.Process
    started: float
    meta: dict = field(default_factory=dict)


def even(n: float) -> int:
    n = int(n)
    return n - (n % 2)


async def run_ffmpeg(args: list[str], env: dict, timeout: float) -> None:
    proc = await asyncio.create_subprocess_exec("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, env=env,
                                                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("ffmpeg timed out") from None
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + err.decode(errors="replace").strip()[-400:])


async def start_ffmpeg(args: list[str], env: dict) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, env=env,
                                                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.PIPE)


async def stop_ffmpeg(proc: asyncio.subprocess.Process, timeout: float = 15) -> None:
    """Ask ffmpeg to finish cleanly ('q' on stdin) so the MP4/WAV trailer is written."""
    if proc.returncode is None:
        try:
            proc.stdin.write(b"q")
            await proc.stdin.drain()
            proc.stdin.close()
        except (BrokenPipeError, ConnectionResetError):
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


# ---------------------------------------------------------------- screen clips
def x11grab_args(display: str, rect: tuple[int, int, int, int], fps: int, out: Path, seconds: float | None,
                 audio_source: str | None = None, max_width: int = 1280) -> list[str]:
    x, y, w, h = rect
    args = ["-f", "x11grab", "-framerate", str(fps), "-video_size", f"{even(w)}x{even(h)}",
            "-i", f"{display}+{x},{y}"]
    if audio_source:
        args += ["-f", "pulse", "-i", audio_source]
    if seconds:
        args += ["-t", f"{seconds:.2f}"]
    args += ["-vf", f"scale='min({max_width},iw)':-2", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
             "-pix_fmt", "yuv420p"]
    if audio_source:
        args += ["-c:a", "aac", "-b:a", "96k"]
    return args + ["-movflags", "+faststart", str(out)]


async def probe_duration(path: Path, env: dict) -> float:
    proc = await asyncio.create_subprocess_exec("ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                "-of", "csv=p=0", str(path), env=env, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.DEVNULL)
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except ValueError:
        return 0.0


async def sample_frames(path: Path, duration: float, n: int, env: dict, workdir: Path) -> list[tuple[float, Image.Image]]:
    n = max(1, min(n, 36))
    frames = []
    for i in range(n):
        t = duration * (i + 0.5) / n if n > 1 else duration / 2
        out = workdir / f"{path.stem}-f{i:02d}.png"
        await run_ffmpeg(["-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", str(out)], env, timeout=30)
        if out.exists():
            frames.append((t, Image.open(out).convert("RGB")))
    return frames


def label_font(size: int):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def contact_sheet(frames: list[tuple[float, Image.Image]], max_dim: int) -> tuple[Image.Image, list[dict]]:
    """Grid of sampled frames. Each tile has a caption strip underneath (never covering content) with its number,
    time, and the share of pixels that changed since the previous tile."""
    n = len(frames)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    fw, fh = frames[0][1].size
    gap = 4
    font_px = max(13, min(22, max_dim // 70))
    strip = font_px + 8
    scale = min(1.0, (max_dim - gap * (cols - 1)) / (cols * fw),
                (max_dim - gap * (rows - 1) - strip * rows) / (rows * fh))
    tw, th = max(1, int(fw * scale)), max(1, int(fh * scale))
    sheet = Image.new("RGB", (cols * tw + gap * (cols - 1), rows * (th + strip) + gap * (rows - 1)), (32, 32, 32))
    font = label_font(font_px)
    draw = ImageDraw.Draw(sheet)
    timeline = []
    prev = None
    for i, (t, img) in enumerate(frames):
        change = imaging.changed_fraction(prev, img, width=640) if prev is not None else 0.0
        prev = img
        timeline.append({"tile": i + 1, "t": round(t, 2), "changed": round(change, 4)})
        x, y = (i % cols) * (tw + gap), (i // cols) * (th + strip + gap)
        sheet.paste(img.resize((tw, th), Image.Resampling.LANCZOS), (x, y))
        label = f"#{i + 1}  t={t:.1f}s" + (f"  changed {change * 100:.1f}%" if i else "")
        draw.text((x + 4, y + th + 3), label, fill=(255, 220, 0), font=font)
    return sheet, timeline


# ---------------------------------------------------------------------- audio
async def pulse_source(kind: str, env: dict) -> str:
    """'system' -> monitor of the default sink; 'mic' -> default source; anything else is a device name."""
    if kind not in ("system", "mic"):
        return kind
    if not shutil.which("pactl"):
        raise RuntimeError("pactl not found (PulseAudio/PipeWire-pulse needed for audio capture)")
    arg = "get-default-sink" if kind == "system" else "get-default-source"
    proc = await asyncio.create_subprocess_exec("pactl", arg, env=env, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.DEVNULL)
    out, _ = await proc.communicate()
    name = out.decode().strip()
    if not name:
        raise RuntimeError(f"no default {'sink' if kind == 'system' else 'source'}")
    if kind == "system":
        return name + ".monitor"
    if name.endswith(".monitor"):
        raise RuntimeError("no microphone: the default source is a monitor of an output")
    return name


def pulse_args(source: str, out: Path, seconds: float | None) -> list[str]:
    args = ["-f", "pulse", "-i", source]
    if seconds:
        args += ["-t", f"{seconds:.2f}"]
    return args + ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out)]


def analyze_wav(path: Path, window_ms: int = 100, threshold_dbfs: float = -45.0) -> dict:
    """Overall levels and the time ranges where sound is present (pure Python; 16 kHz mono s16)."""
    with wave.open(str(path)) as w:
        rate, n = w.getframerate(), w.getnframes()
        samples = array.array("h", w.readframes(n))
    if not samples:
        return {"duration_s": 0.0, "silent": True, "peak_dbfs": None, "rms_dbfs": None, "sound": []}

    def dbfs(v: float) -> float:
        return round(20 * math.log10(v / 32768), 1) if v > 0 else -120.0

    step = max(1, rate * window_ms // 1000)
    total_sq, peak, active = 0, 0, []
    for start in range(0, len(samples), step):
        chunk = samples[start:start + step]
        sq = sum(s * s for s in chunk)
        total_sq += sq
        peak = max(peak, max(abs(s) for s in chunk))
        if dbfs(math.sqrt(sq / len(chunk))) > threshold_dbfs:
            active.append(start / rate)
    segments: list[list[float]] = []
    win = window_ms / 1000
    for t in active:
        if segments and t - segments[-1][1] <= win * 3:
            segments[-1][1] = t + win
        else:
            segments.append([t, t + win])
    return {"duration_s": round(len(samples) / rate, 2), "silent": not segments,
            "peak_dbfs": dbfs(peak), "rms_dbfs": dbfs(math.sqrt(total_sq / len(samples))),
            "sound": [[round(a, 1), round(b, 1)] for a, b in segments][:50]}


def waveform(path: Path, width: int = 1024, height: int = 160) -> Image.Image:
    with wave.open(str(path)) as w:
        rate, n = w.getframerate(), w.getnframes()
        samples = array.array("h", w.readframes(n))
    img = Image.new("RGB", (width, height), (20, 20, 20))
    d = ImageDraw.Draw(img)
    mid = height // 2
    if samples:
        per = max(1, len(samples) // width)
        for x in range(width):
            chunk = samples[x * per:(x + 1) * per]
            if not chunk:
                break
            amp = max(abs(min(chunk)), abs(max(chunk))) / 32768
            d.line((x, mid - amp * mid, x, mid + amp * mid), fill=(80, 200, 255))
        secs = len(samples) / rate
        font = label_font(12)
        for s in range(0, int(secs) + 1, max(1, int(secs // 10) or 1)):
            x = int(s / secs * (width - 1)) if secs else 0
            d.line((x, height - 8, x, height), fill=(200, 200, 200))
            d.text((x + 2, height - 22), f"{s}s", fill=(200, 200, 200), font=font)
    return img


class Transcriber:
    """Speech-to-text: an OpenAI-compatible endpoint if configured, else local faster-whisper if installed."""

    def __init__(self, url: str = "", model: str = "small", api_key: str = ""):
        self.url, self.model, self.api_key = url.rstrip("/"), model, api_key
        self._local: dict = {}

    @property
    def available(self) -> str | None:
        if self.url:
            return "endpoint"
        try:
            import faster_whisper  # noqa: F401
            return "local"
        except ImportError:
            return None

    async def transcribe(self, path: Path, model: str | None = None) -> dict:
        if self.url:
            return await asyncio.to_thread(self._remote, path, model or self.model)
        return await asyncio.to_thread(self._local_transcribe, path, model or self.model)

    def _remote(self, path: Path, model: str) -> dict:
        import json
        import urllib.request
        import uuid
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: audio/wav\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"{self.url}/audio/transcriptions", data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                              **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        with urllib.request.urlopen(req, timeout=120) as r:
            return {"text": json.loads(r.read()).get("text", ""), "backend": f"endpoint:{model}"}

    def _local_transcribe(self, path: Path, model: str) -> dict:
        from faster_whisper import WhisperModel
        if model not in self._local:
            self._local[model] = WhisperModel(model, device="cpu", compute_type="int8")
        t0 = time.monotonic()
        # Pass samples, not a path: faster-whisper's file decoding goes through PyAV, whose API drifts
        # (av 16 dropped an argument faster-whisper 1.2 still passes). Our WAVs are already 16 kHz mono s16.
        import numpy as np
        with wave.open(str(path)) as w:
            if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise RuntimeError("expected 16 kHz mono 16-bit WAV")
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        segments, info = self._local[model].transcribe(pcm, vad_filter=True, beam_size=5, word_timestamps=True)
        segs, unsure = [], []
        for seg in segments:
            segs.append({"start": round(seg.start, 1), "end": round(seg.end, 1), "text": seg.text.strip()})
            unsure += [{"word": w.word.strip(), "t": round(w.start, 1), "p": round(w.probability, 2)}
                       for w in (seg.words or []) if w.probability < 0.6]
        out = {"text": " ".join(s["text"] for s in segs), "segments": segs, "language": info.language}
        if unsure:
            out["uncertain_words"] = unsure
            out["note"] = "uncertain_words were hard to hear; re-record, try a larger stt_model, or attach inline audio"
        return {**out,
                "backend": f"faster-whisper:{model}", "seconds": round(time.monotonic() - t0, 2)}


# ------------------------------------------------------------------------ OCR
def _accepts_params(cls) -> bool:
    import inspect
    try:
        return "params" in inspect.signature(cls).parameters
    except (TypeError, ValueError):
        return False


class Ocr:
    def __init__(self):
        self._engine = None

    def _get(self):
        if self._engine is None:
            import logging
            from rapidocr import RapidOCR
            for name in list(logging.root.manager.loggerDict):
                if "rapidocr" in name.lower():
                    logging.getLogger(name).setLevel(logging.WARNING)
            self._engine = RapidOCR(params={"Global.log_level": "warning"}) if _accepts_params(RapidOCR) else RapidOCR()
            for name in list(logging.root.manager.loggerDict):
                if "rapidocr" in name.lower():
                    logging.getLogger(name).setLevel(logging.WARNING)
        return self._engine

    def read(self, img: Image.Image, min_confidence: float = 0.5, words: bool = False) -> list[dict]:
        """Lines of text with boxes in the image's pixel coordinates, top-to-bottom then left-to-right.
        words=True adds per-word boxes (OCR merges adjacent menu items or tabs into one line)."""
        import numpy as np
        result = self._get()(np.asarray(img.convert("RGB")), return_word_box=words or None)
        lines = []
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return lines
        word_results = getattr(result, "word_results", None) if words else None

        def bbox(quad):
            xs, ys = [p[0] for p in quad], [p[1] for p in quad]
            return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]

        for i, (box, text, score) in enumerate(zip(boxes, result.txts, result.scores)):
            if score < min_confidence or not text.strip():
                continue
            line = {"text": text, "box": bbox(box), "conf": round(float(score), 2)}
            if word_results and i < len(word_results):
                line["words"] = [{"text": w[0], "box": bbox(w[2])} for w in word_results[i] if w and w[0].strip()]
            lines.append(line)
        lines.sort(key=lambda l: (round(l["box"][1] / 8), l["box"][0]))
        return lines
