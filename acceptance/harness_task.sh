#!/usr/bin/env bash
# Phase 1 exit check from a real harness: the model edits and saves a file through the GUI
# using cctl's MCP tools; the result is verified in code, and the event log must show the
# GUI path was used (not a shell shortcut).
# Usage (on the target machine): [TASK=editor|browser|audio|clip] acceptance/harness_task.sh codex|claude|opencode [args...]
set -euo pipefail
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
HARNESS="$1"; shift
TASK="${TASK:-editor}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CCTL="${CCTL_BIN:-$HOME/.local/bin/cctl}"
RUN="/tmp/cctl-harness-$HARNESS-$(date +%H%M%S)"
mkdir -p "$RUN"/{c,d,s,k}
NOTE="$RUN/note.txt"
: > "$NOTE"
EXPECT="Hello from $HARNESS — 日本語 ✓"
EVENTS="$HOME/.local/state/cctl/events.jsonl"
START=$(date +%s)

WORDS_POOL=(ALPHA BRAVO CHARLIE DELTA ECHO FOXTROT GOLF HOTEL INDIA JULIET KILO LIMA MANGO NECTAR OCEAN PEPPER QUARTZ RIVER SUNSET TIGER)
if [ "$TASK" = audio ]; then
  NOUNS=(lighthouse volcano pineapple umbrella dolphin penguin blanket harbor lantern meadow orchestra pyramid saddle tornado violin walrus)
  SECRET="${NOUNS[$((RANDOM % 16))]}"
  espeak-ng -s 125 -w "$RUN/say.wav" "Attention. The secret word is $SECRET. I repeat, $SECRET."
  (setsid bash -c "for i in \$(seq 1 40); do paplay '$RUN/say.wav'; sleep 2; done" < /dev/null >/dev/null 2>&1 &)
  PROMPT="Something on this computer is speaking out loud every few seconds. Use the cctl tools to listen to the computer's audio output and tell me the secret word it says. Do not use a shell. Reply with the secret word."
elif [ "$TASK" = clip ]; then
  SEQ=$(printf '%s\n' "${WORDS_POOL[@]}" | shuf -n 5 | paste -sd, -)
  # Serve a per-run copy whose words live in words.js, so they appear in no URL or command line.
  mkdir -p "$RUN/web" && cp "$HERE/web/ticker.html" "$RUN/web/"
  printf 'window.WORDS="%s";\n' "$(printf %s "$SEQ" | base64 -w0)" > "$RUN/web/words.js"
  (cd "$RUN/web" && setsid python3 -m http.server 8765 --bind 127.0.0.1 < /dev/null >/dev/null 2>&1 &)
  sleep 0.5
  PROMPT="Use the cctl tools and do not use a shell. A browser window titled 'cctl ticker' is open on this desktop. It flashes a repeating cycle of 5 words, one at a time. Watch it (for example with record_clip on that window, at least 6 seconds) and reply with the 5 words in the order they appear, as a comma-separated list starting from any word."
  DISPLAY=:0 XAUTHORITY="$HOME/.Xauthority" chromium --user-data-dir="$RUN/chrome" --no-first-run \
    --no-default-browser-check --new-window --window-size=1000,400 --window-position=100,100 \
    "http://127.0.0.1:8765/ticker.html" < /dev/null >/dev/null 2>&1 &
  CHROME_PID=$!
  sleep 4
elif [ "$TASK" = browser ]; then
  (cd "$HERE/web" && setsid python3 -m http.server 8765 --bind 127.0.0.1 >/dev/null 2>&1 &)
  sleep 0.5
  CODE="Kiwi-日本-$((RANDOM % 900 + 100))"
  PROMPT="Use the cctl browser tools (browser_open, browser_snapshot, browser_act). Do not use a shell or curl.
Open http://127.0.0.1:8765/form.html, enter the code word $CODE in the Code word field, tick 'I agree', press Submit,
then read the confirmation shown on the page and close the browser. Reply with the confirmation code (it looks like CONF-123456)."
else
PROMPT="Use the cctl computer-use tools to do this through the desktop GUI. Do not use a shell or edit files directly.
1. Launch a text editor window on the file $NOTE with the apps tool: action=launch, name=env, args=[\"XDG_CONFIG_HOME=$RUN/c\",\"XDG_DATA_HOME=$RUN/d\",\"XDG_STATE_HOME=$RUN/s\",\"XDG_CACHE_HOME=$RUN/k\",\"mousepad\",\"--disable-server\",\"$NOTE\"].
2. Type exactly this text into the editor: $EXPECT
3. Save with ctrl+s, confirm from a screenshot or observe that it saved (no '*' in the title), then quit the editor with the apps tool.
Reply DONE when finished."
fi

case "$HARNESS" in
  codex)
    (cd "$RUN" && codex exec --skip-git-repo-check --ephemeral \
      -c "mcp_servers.cctl.command=\"$CCTL\"" -c 'mcp_servers.cctl.args=["mcp"]' \
      -c 'mcp_servers.cctl.tool_timeout_sec=120' "$@" "$PROMPT" < /dev/null) > "$RUN/transcript.txt" 2>&1 || true ;;
  claude)
    printf '{"mcpServers":{"cctl":{"command":"%s","args":["mcp"]}}}' "$CCTL" > "$RUN/mcp.json"
    (cd "$RUN" && printf '%s' "$PROMPT" | claude -p --mcp-config "$RUN/mcp.json" --strict-mcp-config \
      --allowedTools "mcp__cctl" "$@") > "$RUN/transcript.txt" 2>&1 || true ;;
  opencode)
    printf '{"$schema":"https://opencode.ai/config.json","mcp":{"cctl":{"type":"local","command":["%s","mcp"],"timeout":120000}}}' \
      "$CCTL" > "$RUN/opencode.json"
    (cd "$RUN" && opencode run --auto "$@" "$PROMPT" < /dev/null) > "$RUN/transcript.txt" 2>&1 || true ;;
  *) echo "unknown harness $HARNESS" >&2; exit 2 ;;
esac

if [ "$TASK" = audio ]; then
  pkill -f "[f]or i in .*paplay '$RUN" || true; pkill -f "[p]aplay $RUN/say.wav" || true
  python3 - "$SECRET" "$EVENTS" "$START" "$RUN" <<'EOF'
import json, sys
secret, events, start, run = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
transcript = open(f"{run}/transcript.txt", encoding="utf-8", errors="replace").read()
answer = transcript.split("Reply with the secret word.")[-1].lower()
calls = [json.loads(l) for l in open(events, encoding="utf-8") if json.loads(l)["ts"] >= start]
used = sorted({c["tool"] for c in calls})
ok = secret in answer and "audio_capture" in used and "run" not in used
print(f"secret       : {secret}   in answer: {secret in answer}")
print(f"cctl calls   : {len(calls)} ({', '.join(used)})")
print(f"errors       : {[(c['tool'], c.get('error')) for c in calls if not c['ok']]}")
print(("PASS" if ok else "FAIL") + f"  run dir {run}")
sys.exit(0 if ok else 1)
EOF
  exit $?
fi
if [ "$TASK" = clip ]; then
  kill "$CHROME_PID" 2>/dev/null || true; pkill -f "[h]ttp.server 8765" || true
  python3 - "$SEQ" "$EVENTS" "$START" "$RUN" <<'EOF'
import json, re, sys
seq, events, start, run = sys.argv[1].split(","), sys.argv[2], float(sys.argv[3]), sys.argv[4]
transcript = open(f"{run}/transcript.txt", encoding="utf-8", errors="replace").read()
answer = transcript.split("starting from any word.")[-1].upper()
found = [w for w in re.findall(r"[A-Z]+", answer) if w in seq]
# accept any rotation of the cycle, using the last 5 distinct words the model reported
got = []
for w in found:
    if w in got:
        got.remove(w)
    got.append(w)
got = got[-5:]
rot = [seq[(seq.index(got[0]) + k) % 5] for k in range(5)] if got else []
ok_order = len(got) == 5 and got == rot
calls = [json.loads(l) for l in open(events, encoding="utf-8") if json.loads(l)["ts"] >= start]
used = sorted({c["tool"] for c in calls})
ok = ok_order and "run" not in used
print(f"cycle        : {seq}")
print(f"answer       : {got}  order ok: {ok_order}")
print(f"cctl calls   : {len(calls)} ({', '.join(used)})")
print(f"errors       : {[(c['tool'], c.get('error')) for c in calls if not c['ok']]}")
print(("PASS" if ok else "FAIL") + f"  run dir {run}")
sys.exit(0 if ok else 1)
EOF
  exit $?
fi
if [ "$TASK" = browser ]; then
  pkill -f "[h]ttp.server 8765" || true
  python3 - "$CODE" "$EVENTS" "$START" "$RUN" <<'EOF'
import json, sys
code, events, start, run = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
h = 2166136261
for c in code:
    h ^= ord(c); h = (h * 16777619) & 0xFFFFFFFF
want = f"CONF-{h % 1000000:06d}"
transcript = open(f"{run}/transcript.txt", encoding="utf-8", errors="replace").read()
answer = transcript.split("Reply with the confirmation code")[-1]
calls = [json.loads(l) for l in open(events, encoding="utf-8") if json.loads(l)["ts"] >= start]
used = sorted({c["tool"] for c in calls})
ok = want in answer and "browser_act" in used and "run" not in used
print(f"expected     : {want} (code word {code!r})")
print(f"in answer    : {want in answer}")
print(f"cctl calls   : {len(calls)} ({', '.join(used)})")
print(f"errors       : {[(c['tool'], c.get('error')) for c in calls if not c['ok']]}")
print(("PASS" if ok else "FAIL") + f"  run dir {run}")
sys.exit(0 if ok else 1)
EOF
  exit $?
fi

python3 - "$NOTE" "$EXPECT" "$EVENTS" "$START" "$RUN" <<'EOF'
import json, sys, time
note, expect, events, start, run = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
content = open(note, encoding="utf-8").read()
calls = []
for line in open(events, encoding="utf-8"):
    e = json.loads(line)
    if e["ts"] >= start:
        calls.append(e)
tools = [c["tool"] for c in calls]
gui_typed = any(c["tool"] == "type_text" and c["ok"] for c in calls)
saved_by_key = any(c["tool"] in ("key", "batch") and c["ok"] for c in calls)
ok_content = content.strip() == expect
print(f"file content : {content!r}")
print(f"cctl calls   : {len(calls)} ({', '.join(sorted(set(tools)))})")
print(f"errors       : {[(c['tool'], c.get('error')) for c in calls if not c['ok']]}")
verdict = ok_content and gui_typed and saved_by_key
print(("PASS" if verdict else "FAIL") + f"  run dir {run}")
sys.exit(0 if verdict else 1)
EOF
