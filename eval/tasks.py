"""Eval tasks for cctl: natural-language desktop/browser/media tasks with checks done in code.

Each task gets a fresh run directory and random values, so answers can't be memorized or guessed.
`setup` and `teardown` are shell snippets run on the controlled machine (DISPLAY etc. exported);
`check` inspects the model's final answer, files and the cctl event log. Tasks that must be done
through the GUI forbid the `run` tool.
"""

from __future__ import annotations

import json
import random
import re
import string
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

WORDS = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL", "INDIA", "JULIET", "KILO", "LIMA",
         "MANGO", "NECTAR", "OCEAN", "PEPPER", "QUARTZ", "RIVER", "SUNSET", "TIGER"]
NOUNS = ["lighthouse", "volcano", "pineapple", "umbrella", "dolphin", "penguin", "blanket", "harbor", "lantern",
         "meadow", "orchestra", "pyramid", "saddle", "tornado", "violin", "walrus"]
NO_SHELL = "Use only the cctl tools; do not use a shell, scripts, or direct file access."
WEB = Path(__file__).resolve().parents[1] / "acceptance" / "web"


def code(n: int = 6) -> str:
    return "".join(random.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(n))


def free_port() -> int:
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class Ctx:
    run: Path
    port: int = field(default_factory=free_port)  # fixed ports collide with whatever else the machine runs
    v: dict = field(default_factory=dict)

    def mousepad(self, path: str) -> str:
        """Shell command to start an isolated Mousepad (its own XDG dirs) on `path`."""
        x = self.run / "xdg"
        return (f"mkdir -p {x}/c {x}/d {x}/s {x}/k && env XDG_CONFIG_HOME={x}/c XDG_DATA_HOME={x}/d "
                f"XDG_STATE_HOME={x}/s XDG_CACHE_HOME={x}/k setsid mousepad --disable-server {path} "
                f"</dev/null >/dev/null 2>&1 &")

    def serve(self) -> str:
        return (f"mkdir -p {self.run}/web && cp -r {WEB}/. {self.run}/web/ && (cd {self.run}/web && setsid python3 "
                f"-m http.server {self.port} --bind 127.0.0.1 </dev/null >/dev/null 2>&1 &) && sleep 0.5")

    def launch_args(self, path: str) -> str:
        x = self.run / "xdg"
        return json.dumps(["XDG_CONFIG_HOME=" + f"{x}/c", f"XDG_DATA_HOME={x}/d", f"XDG_STATE_HOME={x}/s",
                           f"XDG_CACHE_HOME={x}/k", "mousepad", "--disable-server", path])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


@dataclass
class Result:
    ok: bool
    detail: dict


@dataclass
class Task:
    id: str
    category: str
    prompt: Callable[[Ctx], str]
    check: Callable[[Ctx, str, list[dict]], Result]
    setup: Callable[[Ctx], str] = lambda c: ""
    teardown: Callable[[Ctx], str] = lambda c: ""
    gui_only: bool = True          # fail if the run tool was used
    needs_vision: bool = False
    timeout_s: int = 420


def used(calls: list[dict]) -> set[str]:
    return {c["tool"] for c in calls}


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def sh(cmd: str) -> str:
    return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True).stdout


TASKS: list[Task] = []


def task(**kw):
    def deco(fn):
        return fn
    TASKS.append(Task(**kw))
    return deco


# --------------------------------------------------------------------- editor
def _editor_unicode_setup(c: Ctx) -> str:
    c.v["text"] = f"Note {code(4)} — 日本語 ✓ café"
    return f": > {c.run}/note.txt"


task(id="editor_unicode", category="editor",
     setup=_editor_unicode_setup,
     prompt=lambda c: f"{NO_SHELL} Open {c.run}/note.txt in the Mousepad text editor (launch it with the apps tool: "
                      f"name=env, args={c.launch_args(str(c.run / 'note.txt'))}), type exactly this text: "
                      f"{c.v['text']}\nSave it and quit the editor. Reply DONE.",
     check=lambda c, ans, calls: Result(read(c.run / "note.txt").strip() == c.v["text"],
                                        {"file": read(c.run / "note.txt")[:120]}))


def _replace_setup(c: Ctx) -> str:
    c.v["n"] = random.randint(3, 6)
    body = " ".join(["The color of the sky."] * c.v["n"])
    (c.run / "doc.txt").write_text(body + "\n", encoding="utf-8")
    return c.mousepad(f"{c.run}/doc.txt") + " sleep 1.5"


task(id="editor_find_replace", category="editor",
     setup=_replace_setup,
     prompt=lambda c: f"{NO_SHELL} A Mousepad window has doc.txt open. Using the editor's own Find and Replace "
                      "(Search menu), replace every 'color' with 'colour', save the file, then close the editor. "
                      "Reply DONE.",
     check=lambda c, ans, calls: Result(
         read(c.run / "doc.txt").count("colour") == c.v["n"] and "color " not in read(c.run / "doc.txt"),
         {"file": read(c.run / "doc.txt")[:120]}),
     teardown=lambda c: f"pkill -f '[m]ousepad --disable-server {c.run}'")


def _open_dialog_setup(c: Ctx) -> str:
    c.v["line"] = f"appended {code(5)}"
    (c.run / "deep" / "nested").mkdir(parents=True, exist_ok=True)
    (c.run / "deep" / "nested" / "target.txt").write_text("first line\n", encoding="utf-8")
    return c.mousepad("") + " sleep 1.5"


task(id="editor_open_dialog", category="editor",
     setup=_open_dialog_setup,
     prompt=lambda c: f"{NO_SHELL} A Mousepad window is open with an empty document. Use its File > Open dialog to "
                      f"open {c.run}/deep/nested/target.txt, add a new last line with exactly: {c.v['line']}\n"
                      "Save, close the editor, and reply DONE.",
     check=lambda c, ans, calls: Result(
         read(c.run / "deep/nested/target.txt").splitlines()[-1:] == [c.v["line"]]
         and read(c.run / "deep/nested/target.txt").startswith("first line"),
         {"file": read(c.run / "deep/nested/target.txt")[:200]}),
     teardown=lambda c: "pkill -f '[m]ousepad --disable-server'; true")


# -------------------------------------------------------------------- windows
def _geometry_setup(c: Ctx) -> str:
    c.v["title"] = f"clock-{code(4)}"
    return f"setsid xclock -title {c.v['title']} -geometry 200x200+700+500 </dev/null >/dev/null 2>&1 & sleep 1"


def _geometry_check(c: Ctx, ans: str, calls: list[dict]) -> Result:
    out = sh(f"xdotool search --name '^{c.v['title']}$' getwindowgeometry --shell 2>/dev/null")
    g = dict(line.split("=") for line in out.split() if "=" in line)
    try:
        x, y, w, h = int(g["X"]), int(g["Y"]), int(g["WIDTH"]), int(g["HEIGHT"])
    except (KeyError, ValueError):
        return Result(False, {"geometry": out})
    ok = abs(x - 150) <= 6 and abs(y - 120) <= 6 and abs(w - 400) <= 6 and abs(h - 300) <= 6
    return Result(ok, {"geometry": [x, y, w, h]})


task(id="window_geometry", category="windows",
     setup=_geometry_setup,
     prompt=lambda c: f"{NO_SHELL} Move the window titled '{c.v['title']}' so its top-left corner is at x=150, "
                      "y=120 on the screen, and make it 400 pixels wide and 300 pixels tall. Reply DONE.",
     check=_geometry_check,
     teardown=lambda c: f"pkill -f '[x]clock -title {c.v['title']}'")


def _close_setup(c: Ctx) -> str:
    c.v["titles"] = [f"panel-{w.lower()}-{code(3)}" for w in random.sample(WORDS, 3)]
    c.v["victim"] = c.v["titles"][1]
    return " ".join(f"setsid xclock -title {t} -geometry 160x160+{200 + 200 * i}+200 </dev/null >/dev/null 2>&1 &"
                    for i, t in enumerate(c.v["titles"])) + " sleep 1"


task(id="window_close_one", category="windows",
     setup=_close_setup,
     prompt=lambda c: f"{NO_SHELL} Three small clock windows are open. Close only the one titled "
                      f"'{c.v['victim']}' and leave the others open. Reply DONE.",
     check=lambda c, ans, calls: Result(
         not sh(f"pgrep -f '[x]clock -title {c.v['victim']}'").strip()
         and all(sh(f"pgrep -f '[x]clock -title {t}'").strip() for t in c.v["titles"] if t != c.v["victim"]),
         {"alive": [t for t in c.v["titles"] if sh(f"pgrep -f '[x]clock -title {t}'").strip()]}),
     teardown=lambda c: "; ".join(f"pkill -f '[x]clock -title {t}'" for t in c.v["titles"]))


# ------------------------------------------------------------ apps / processes
def _runaway_setup(c: Ctx) -> str:
    c.v["name"] = f"cruncher-{code(4).lower()}"
    return (f"setsid bash -c 'exec -a {c.v['name']} python3 -c \"while True: pass\"' </dev/null >/dev/null 2>&1 & "
            "sleep 0.5")


task(id="process_kill_runaway", category="processes",
     setup=_runaway_setup,
     prompt=lambda c: f"{NO_SHELL} Some process on this machine is using a full CPU core. Find it, tell me its name "
                      "and pid, and stop it. Do not stop anything else.",
     check=lambda c, ans, calls: Result(
         not sh(f"pgrep -f '^{c.v['name']}'").strip() and c.v["name"] in ans,
         {"still_running": bool(sh(f"pgrep -f '^{c.v['name']}'").strip()), "named": c.v["name"] in ans}),
     teardown=lambda c: f"pkill -f '^{c.v['name']}'")


def _calc_setup(c: Ctx) -> str:
    c.v["a"], c.v["b"] = random.randint(1000, 9999), random.randint(100, 999)
    return "setsid galculator </dev/null >/dev/null 2>&1 & sleep 1.5"


task(id="calculator", category="apps",
     setup=_calc_setup,
     prompt=lambda c: f"{NO_SHELL} Use the calculator window (galculator) that is open to compute "
                      f"{c.v['a']} × {c.v['b']} by pressing its buttons or typing into it, read the result from "
                      "its display, and reply with the result only.",
     check=lambda c, ans, calls: Result(
         str(c.v["a"] * c.v["b"]) in ans.replace(",", "").replace(" ", "")
         and bool(used(calls) & {"click", "type_text", "key", "batch"}),
         {"want": c.v["a"] * c.v["b"], "input_used": sorted(used(calls) & {"click", "type_text", "key", "batch"})}),
     teardown=lambda c: "pkill -x galculator", needs_vision=False)


def _dialog_setup(c: Ctx) -> str:
    return (f"(setsid bash -c 'zenity --question --title \"Cleanup\" --text \"Delete all files in {c.run}/data?\"; "
            f"echo $? > {c.run}/answer' </dev/null >/dev/null 2>&1 &) ; sleep 1.5")


task(id="dialog_decline", category="dialogs",
     setup=_dialog_setup,
     prompt=lambda c: f"{NO_SHELL} A dialog on screen is asking a question. Answer it so that nothing gets deleted. "
                      "Reply DONE.",
     check=lambda c, ans, calls: Result(read(c.run / "answer").strip() == "1", {"exit": read(c.run / "answer").strip()}),
     teardown=lambda c: "pkill -x zenity")


def _mkdir_setup(c: Ctx) -> str:
    c.v["folder"] = f"Reports-{code(4)}"
    (c.run / "files").mkdir(exist_ok=True)
    return f"setsid thunar {c.run}/files </dev/null >/dev/null 2>&1 & sleep 2"


task(id="filemanager_mkdir", category="apps",
     setup=_mkdir_setup,
     prompt=lambda c: f"{NO_SHELL} A Thunar file manager window shows the folder 'files'. Using the file manager, "
                      f"create a new folder in it named {c.v['folder']}. Reply DONE.",
     check=lambda c, ans, calls: Result((c.run / "files" / c.v["folder"]).is_dir(),
                                        {"entries": [p.name for p in (c.run / "files").iterdir()]}),
     teardown=lambda c: f"xdotool search --name '^files - Thunar' windowclose 2>/dev/null; true")


def _terminal_setup(c: Ctx) -> str:
    c.v["code"] = code(8)
    (c.run / "motd").write_text(f"Build finished.\nArtifact checksum: {c.v['code']}\n", encoding="utf-8")
    return (f"setsid xfce4-terminal --disable-server --title 'build-log' --hold "
            f"-x cat {c.run}/motd </dev/null >/dev/null 2>&1 & sleep 2")


task(id="terminal_read", category="ocr",
     setup=_terminal_setup,
     prompt=lambda c: f"{NO_SHELL} A terminal window titled 'build-log' shows the output of a build. Read the "
                      "artifact checksum shown in it and reply with the checksum only.",
     check=lambda c, ans, calls: Result(c.v["code"] in ans.replace(" ", ""), {"want": c.v["code"]}),
     teardown=lambda c: "pkill -f '[x]fce4-terminal --disable-server --title build-log'", needs_vision=True)


# -------------------------------------------------------------------- browser
def _form_setup(c: Ctx) -> str:
    c.v["word"] = f"Kiwi-日本-{random.randint(100, 999)}"
    return c.serve()


def _fnv(s: str) -> str:
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return f"CONF-{h % 1000000:06d}"


task(id="browser_form", category="browser",
     setup=_form_setup,
     prompt=lambda c: f"{NO_SHELL} Open {c.url}/form.html in the cctl browser, enter the code word {c.v['word']} "
                      "in the Code word field, tick 'I agree', press Submit, read the confirmation shown and close "
                      "the browser. Reply with the confirmation code.",
     check=lambda c, ans, calls: Result(_fnv(c.v["word"]) in ans, {"want": _fnv(c.v["word"])}),
     teardown=lambda c: f"pkill -f '[h]ttp.server {c.port}'")


def _site_setup(c: Ctx) -> str:
    c.v["ext"] = str(random.randint(1000, 9999))
    c.v["decoy"] = str(random.randint(1000, 9999))
    site = c.run / "web" / "site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text('<meta charset="utf-8"><title>Acme Corp</title><h1>Acme Corp</h1><a href="about.html">About us</a> '
                                     '<a href="departments.html">Departments</a>', encoding="utf-8")
    (site / "about.html").write_text(f"<meta charset='utf-8'><title>About</title><h1>About</h1><p>Front desk extension {c.v['decoy']}.</p>"
                                     '<a href="index.html">Home</a>', encoding="utf-8")
    (site / "departments.html").write_text('<meta charset="utf-8"><title>Departments</title><h1>Departments</h1><ul><li><a href="sales.html">'
                                           'Sales</a><li><a href="research.html">Research</a></ul>', encoding="utf-8")
    (site / "sales.html").write_text(f"<meta charset='utf-8'><title>Sales</title><p>Sales extension {c.v['decoy'][::-1]}.</p>",
                                     encoding="utf-8")
    (site / "research.html").write_text(f"<meta charset='utf-8'><title>Research</title><h1>Research</h1><p>Lab hours 9-5.</p>"
                                        f"<p>Phone extension: {c.v['ext']}</p>", encoding="utf-8")
    return c.serve()


task(id="browser_navigate_site", category="browser",
     setup=_site_setup,
     prompt=lambda c: f"{NO_SHELL} Starting from {c.url}/site/index.html in the cctl browser, find the phone "
                      "extension of the Research department by following links. Reply with the extension number.",
     check=lambda c, ans, calls: Result(c.v["ext"] in ans and c.v["decoy"] not in ans, {"want": c.v["ext"]}),
     teardown=lambda c: f"pkill -f '[h]ttp.server {c.port}'")


def _canvas_setup(c: Ctx) -> str:
    c.v["code"] = code(6)
    page = (c.run / "web" / "canvas.html")
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "<meta charset='utf-8'><title>badge</title><body style='margin:0;background:#fafafa'><canvas id=c width=1200 height=700></canvas>"
        "<script>const g=document.getElementById('c').getContext('2d');"
        "for(let i=0;i<400;i++){g.fillStyle=`hsl(${i*37%360},40%,80%)`;g.fillRect(Math.random()*1200,"
        "Math.random()*700,6,6);}"
        "g.strokeStyle='#444';g.strokeRect(560,520,150,40);g.fillStyle='#333';g.font='11px sans-serif';"
        f"g.fillText('BADGE CODE',570,534);g.font='12px monospace';g.fillText('{c.v['code']}',570,552);"
        "</script>", encoding="utf-8")
    return c.serve()


task(id="ocr_small_canvas_text", category="ocr",
     setup=_canvas_setup,
     prompt=lambda c: f"{NO_SHELL} Open {c.url}/canvas.html in the cctl browser. Somewhere on the page a small box "
                      "labeled BADGE CODE shows a 6-character code drawn as pixels (not page text). Report the code.",
     check=lambda c, ans, calls: Result(c.v["code"] in ans.upper().replace(" ", ""), {"want": c.v["code"]}),
     teardown=lambda c: f"pkill -f '[h]ttp.server {c.port}'", needs_vision=True)


def _copy_setup(c: Ctx) -> str:
    c.v["quote"] = f"The {random.choice(NOUNS)} sings at {random.randint(1, 12)} o'clock — {code(4)}."
    page = c.run / "web" / "quote.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"<meta charset='utf-8'><title>Quote of the day</title><h1>Quote of the day</h1><blockquote id=q>{c.v['quote']}"
                    "</blockquote>", encoding="utf-8")
    (c.run / "quote.txt").write_text("", encoding="utf-8")
    return c.serve()


task(id="copy_browser_to_editor", category="mixed",
     setup=_copy_setup,
     prompt=lambda c: f"{NO_SHELL} Open {c.url}/quote.html in the cctl browser, then put the exact quote text into "
                      f"the file {c.run}/quote.txt using the Mousepad editor (apps launch: name=env, args="
                      f"{c.launch_args(str(c.run / 'quote.txt'))}), save, close both, and reply DONE.",
     check=lambda c, ans, calls: Result(read(c.run / "quote.txt").strip() == c.v["quote"],
                                        {"file": read(c.run / "quote.txt")[:120]}),
     teardown=lambda c: f"pkill -f '[h]ttp.server {c.port}'; pkill -f '[m]ousepad --disable-server {c.run}'")


# ---------------------------------------------------------------------- media
def _ticker_setup(c: Ctx) -> str:
    c.v["seq"] = random.sample(WORDS, 5)
    import base64
    words_js = c.run / "web" / "words.js"
    words_js.parent.mkdir(parents=True, exist_ok=True)
    return (c.serve() + f" && printf 'window.WORDS=\"%s\";' {base64.b64encode(','.join(c.v['seq']).encode()).decode()}"
            f" > {words_js} && (setsid chromium --user-data-dir={c.run}/chrome --no-first-run "
            "--no-default-browser-check --new-window --window-size=1000,400 --window-position=100,100 "
            f"{c.url}/ticker.html </dev/null >/dev/null 2>&1 &) && sleep 4")


def _ticker_check(c: Ctx, ans: str, calls: list[dict]) -> Result:
    seq = c.v["seq"]
    found = [w for w in re.findall(r"[A-Z]+", ans.upper()) if w in seq]
    got: list[str] = []
    for w in found:
        if w in got:
            got.remove(w)
        got.append(w)
    got = got[-5:]
    ok = len(got) == 5 and got == [seq[(seq.index(got[0]) + k) % 5] for k in range(5)]
    return Result(ok, {"cycle": seq, "got": got})


task(id="clip_ticker", category="media",
     setup=_ticker_setup,
     prompt=lambda c: f"{NO_SHELL} A browser window titled 'cctl ticker' flashes a repeating cycle of 5 words, one "
                      "at a time. Watch it and reply with the 5 words in the order they appear, comma-separated, "
                      "starting from any word.",
     check=_ticker_check,
     teardown=lambda c: f"pkill -f '[u]ser-data-dir={c.run}/chrome'; pkill -f '[h]ttp.server {c.port}'",
     needs_vision=True)


def _audio_setup(c: Ctx) -> str:
    c.v["word"] = random.choice(NOUNS)
    return (f"espeak-ng -s 125 -w {c.run}/say.wav 'Attention. The secret word is {c.v['word']}. I repeat, "
            f"{c.v['word']}.' && (setsid bash -c 'for i in $(seq 1 60); do paplay {c.run}/say.wav; sleep 2; done' "
            "</dev/null >/dev/null 2>&1 &)")


task(id="audio_secret_word", category="media",
     setup=_audio_setup,
     prompt=lambda c: f"{NO_SHELL} Something on this computer is speaking out loud every few seconds. Listen to the "
                      "computer's audio output and reply with the secret word it says.",
     check=lambda c, ans, calls: Result(c.v["word"] in ans.lower(), {"want": c.v["word"]}),
     teardown=lambda c: f"pkill -f '[f]or i in .*paplay {c.run}'; pkill -f '[p]aplay {c.run}'")


def by_id(ids: list[str] | None) -> list[Task]:
    if not ids or ids == ["all"]:
        return TASKS
    known = {t.id: t for t in TASKS}
    missing = [i for i in ids if i not in known and i not in {t.category for t in TASKS}]
    if missing:
        raise SystemExit(f"unknown tasks: {missing}; known: {sorted(known)}")
    return [t for t in TASKS if t.id in ids or t.category in ids]
