import inspect

import pytest
from PIL import Image

from cctl import contract, imaging
from cctl.cli import parse_args
from cctl.engine import Engine, match_element
from cctl.frames import Frame, FrameStore, fit, magnify
from cctl.textentry import choose_route, is_key_safe, paste_keys
from cctl.x11 import normalize_keys


# ---- frames ---------------------------------------------------------------
def test_downscaled_desktop_maps_back_to_screen():
    # 1920x1080 sent as 1568x882
    f = Frame(id="c1", kind="desktop", origin_x=0, origin_y=0, scale_x=1920 / 1568, scale_y=1080 / 882,
              width=1568, height=882)
    assert f.to_screen(0, 0) == (0, 0)
    assert f.to_screen(1568, 882) == (1920, 1080)
    assert f.to_screen(784, 441) == (960, 540)


def test_window_frame_offsets_by_origin():
    f = Frame(id="c2", kind="window", origin_x=640, origin_y=325, scale_x=1, scale_y=1, width=640, height=480)
    assert f.to_screen(294, 12) == (934, 337)
    assert f.from_screen(934, 337) == (294, 12)


def test_zoom_frame_round_trip():
    # 200x100 screen region at (100, 50) enlarged 4x to 800x400
    z = Frame(id="z3", kind="zoom", origin_x=100, origin_y=50, scale_x=0.25, scale_y=0.25, width=800, height=400)
    assert z.to_screen(400, 200) == (200, 100)
    assert z.region_to_screen([800, 400, 0, 0]) == (100, 50, 300, 150)


def test_store_latest_screen_and_expiry():
    s = FrameStore(keep=2)
    with pytest.raises(LookupError):
        s.get(None)
    a = s.add(Frame(id=s.new_id("c"), kind="desktop", origin_x=0, origin_y=0, scale_x=1, scale_y=1, width=1,
                    height=1))
    b = s.add(Frame(id=s.new_id("c"), kind="desktop", origin_x=0, origin_y=0, scale_x=1, scale_y=1, width=1,
                    height=1))
    assert s.get(None) is b
    assert s.get("screen").to_screen(5, 7) == (5, 7)
    s.add(Frame(id=s.new_id("z"), kind="zoom", origin_x=0, origin_y=0, scale_x=1, scale_y=1, width=1, height=1))
    with pytest.raises(LookupError):
        s.get(a.id)


def test_fit_and_magnify():
    assert fit(1920, 1080, 1568) == (1568, 882)
    assert fit(800, 600, 1568) == (800, 600)
    assert magnify(200, 25, 1024) == (800, 100)      # capped at 4x
    assert magnify(400, 300, 1024) == (1024, 768)


def test_blank_detection():
    assert imaging.is_blank(Image.new("RGB", (1920, 1080), "black"))
    assert not imaging.is_blank(Image.new("RGB", (1920, 1080), "white"))


# ---- text entry ---------------------------------------------------------------
@pytest.mark.parametrize("text,route", [
    ("hello world", "keys"), ("a\tb\nc", "keys"), ("~`!@#$%^&*()_+-=[]{}|\\:;\"'<>,.?/", "keys"),
    ("café", "paste"), ("日本語", "paste"), ("✓", "paste"), ("🙂", "paste"), ("x→y", "paste"),
])
def test_route(text, route):
    assert choose_route(text, platform="linux") == route
    assert is_key_safe(text) == (route == "keys")


def test_route_macos_element_uses_ax_insertion():
    assert choose_route("日本語 ✓ 🙂", has_element=True, platform="darwin") == "keys"
    assert choose_route("日本語", has_element=False, platform="darwin") == "paste"


def test_route_overrides():
    assert choose_route("café", "keys") == "keys"
    assert choose_route("abc", "paste") == "paste"
    with pytest.raises(ValueError):
        choose_route("abc", "set_value", has_element=False)


def test_terminal_paste_keys():
    assert paste_keys("Zutty") == "ctrl+shift+v"
    assert paste_keys("xfce4-terminal") == "ctrl+shift+v"
    assert paste_keys("Mousepad") == "ctrl+v"
    assert paste_keys(None) == "ctrl+v"


@pytest.mark.parametrize("given,want", [
    ("Ctrl+S", "ctrl+s"), ("enter", "Return"), ("esc", "Escape"), ("cmd+shift+t", "super+shift+t"),
    ("alt+f4", "alt+F4"), ("A", "A"), ("ctrl + Page_Down", "ctrl+Page_Down"), ("pagedown", "Next"),
])
def test_normalize_keys(given, want):
    assert normalize_keys(given) == want


# ---- CLI ---------------------------------------------------------------------
def test_parse_args():
    assert parse_args(["--x", "12", "--y", "3.5", "--frame", "c2"]) == {"x": 12, "y": 3.5, "frame": "c2"}
    assert parse_args(['{"text": "hi"}', "--submit"]) == {"text": "hi", "submit": True}
    assert parse_args(["--region", "[0,0,10,10]", "--fresh=false"]) == {"region": [0, 0, 10, 10], "fresh": False}
    assert parse_args(["--text", "hello world"]) == {"text": "hello world"}


# ---- contract <-> engine --------------------------------------------------------
def test_every_contract_tool_has_a_handler_with_matching_params():
    for tool in contract.tools():
        handler = getattr(Engine, f"tool_{tool['name']}", None)
        assert handler, f"no handler for {tool['name']}"
        sig = inspect.signature(handler)
        params = set(sig.parameters) - {"self"}
        accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
        props = set(tool["inputSchema"].get("properties", {})) - {"then"}  # consumed by Engine.dispatch
        missing = props - params
        assert not missing or accepts_kwargs, f"{tool['name']}: schema params {missing} not accepted"
        for req in tool["inputSchema"].get("required", []):
            assert req in props, f"{tool['name']}: required {req} not in properties"
        extra = {p for p, v in sig.parameters.items() if p != "self" and v.default is inspect.Parameter.empty
                 and v.kind not in (v.VAR_KEYWORD, v.VAR_POSITIONAL)}
        assert extra <= set(tool["inputSchema"].get("required", [])), f"{tool['name']}: {extra} required in code only"


def test_match_element_survives_index_shift_and_label_change():
    info = {"role": "text", "label": None, "bounds": {"x": 641, "y": 353, "w": 638, "h": 449}}
    newer = [{"element_token": "s2:17", "role": "page tab", "label": None, "frame": None},
             {"element_token": "s2:18", "role": "text", "label": "typed", "frame": dict(info["bounds"])}]
    assert match_element(info, "17", newer)["element_token"] == "s2:18"


def test_match_element_by_index_and_label_when_bounds_move():
    info = {"role": "push button", "label": "OK", "bounds": {"x": 1, "y": 1, "w": 5, "h": 5}}
    newer = [{"element_token": "s3:4", "role": "push button", "label": "OK", "frame": {"x": 9, "y": 9, "w": 5, "h": 5}},
             {"element_token": "s3:5", "role": "push button", "label": "OK", "frame": {"x": 20, "y": 9, "w": 5, "h": 5}}]
    assert match_element(info, "4", newer)["element_token"] == "s3:4"
    assert match_element({**info, "label": "Gone"}, "4", newer) is None


# ---- media ---------------------------------------------------------------------
def test_contact_sheet_grid_and_change(tmp_path):
    from cctl.media import contact_sheet
    frames = [(i * 0.5, Image.new("RGB", (640, 360), (255, 255, 255) if i < 2 else (0, 0, 0))) for i in range(4)]
    sheet, timeline = contact_sheet(frames, max_dim=800)
    assert max(sheet.size) <= 800
    assert [t["tile"] for t in timeline] == [1, 2, 3, 4]
    assert timeline[1]["changed"] == 0 and timeline[2]["changed"] > 0.9


def test_analyze_wav_finds_sound(tmp_path):
    import math, struct, wave
    from cctl.media import analyze_wav
    path = tmp_path / "t.wav"
    rate = 16000
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        silence = b"\0\0" * rate
        tone = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(rate))
        w.writeframes(silence + tone + silence)
    a = analyze_wav(path)
    assert a["duration_s"] == 3.0 and not a["silent"]
    assert len(a["sound"]) == 1 and 0.9 <= a["sound"][0][0] <= 1.1 and 1.9 <= a["sound"][0][1] <= 2.2


def test_capture_args():
    from pathlib import Path
    from cctl.media import pulse_args, x11grab_args
    a = x11grab_args(":0", (10, 20, 641, 481), 8, Path("/tmp/c.mp4"), 3, None)
    assert a[a.index("-video_size") + 1] == "640x480" and a[a.index("-i") + 1] == ":0+10,20"
    assert pulse_args("auto_null.monitor", Path("/tmp/a.wav"), 2)[:4] == ["-f", "pulse", "-i", "auto_null.monitor"]
    b = x11grab_args(":0", (0, 0, 640, 480), 8, Path("/tmp/c.mkv"), 3, "auto_null.monitor")
    # with audio: input-side limits on both inputs, wall-clock timestamps kept into Matroska
    assert b.count("-t") == 2 and b.index("-t") < b.index("-i") and "-copyts" in b and b[-3:-1] == ["-f", "matroska"]


# ---- grounding ----------------------------------------------------------------
@pytest.mark.parametrize("reply,want", [
    ('{"x": 500, "y": 250}', (500, 250)), ("[120, 880]", (120, 880)), ("<point>40 960</point>", (40, 960)),
    ('Sure! {"x":7,"y":993}', (7, 993)),
])
def test_parse_point(reply, want):
    from cctl.grounding import parse_point
    assert parse_point(reply) == want


def test_grounder_maps_normalized_point_and_refines(monkeypatch):
    """A fake OpenAI-compatible server that always answers the centre of whatever image it gets."""
    import http.server, json as j, threading
    from cctl.grounding import Grounder

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = j.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["temperature"] == 0 and body["messages"][0]["content"][0]["type"] == "image_url"
            out = j.dumps({"choices": [{"message": {"content": '{"x": 500, "y": 500}'}}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    g = Grounder(f"http://127.0.0.1:{srv.server_port}/v1", "fake")
    r = g.locate(Image.new("RGB", (1920, 1080), "white"), "the centre", refine=True)
    srv.shutdown()
    assert round(r["x"]) == 960 and round(r["y"]) == 540 and len(r["passes"]) == 2


def test_cua_session_ended_detection():
    from cctl.cua_client import CuaClient
    linux = {"isError": True, "content": [{"type": "text", "text": "session has ended; tool call 'x' was rejected"}]}
    windows = {"isError": True, "structuredContent": {"refusal": {"code": "session_ended", "message": "..."}},
               "content": [{"type": "text", "text": "session 'cctl-1' has ended; call start_session ..."}]}
    ok = {"content": [{"type": "text", "text": "fine"}]}
    assert CuaClient._session_ended(linux) and CuaClient._session_ended(windows) and not CuaClient._session_ended(ok)


def test_parse_args_respects_string_params():
    from cctl import contract
    assert parse_args(["--keys", "4"], contract.schema("key")) == {"keys": "4"}
    assert parse_args(["--text", "true"], contract.schema("type_text")) == {"text": "true"}
    assert parse_args(["--window", "123", "--keys", "ctrl+s"], contract.schema("key")) == {"window": 123, "keys": "ctrl+s"}
