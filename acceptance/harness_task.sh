#!/usr/bin/env bash
# Phase 1 exit check from a real harness: the model edits and saves a file through the GUI
# using cctl's MCP tools; the result is verified in code, and the event log must show the
# GUI path was used (not a shell shortcut).
# Usage (on the target machine): [TASK=editor|browser] acceptance/harness_task.sh codex|claude|opencode [args...]
set -euo pipefail
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

if [ "$TASK" = browser ]; then
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
      -c 'mcp_servers.cctl.tool_timeout_sec=120' "$@" "$PROMPT") > "$RUN/transcript.txt" 2>&1 || true ;;
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
