#!/usr/bin/env bash
# Run the media probe in one harness and grade it.
# Usage: run.sh claude|opencode|pi|codex [extra harness args...]
# Writes runs/<harness>-<timestamp>/{transcript.txt,codes.json,grade.json}.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$1"; shift
UV="${UV:-$(command -v uv)}"
SERVER="$HERE/server.py"
RUN="$HERE/runs/$HARNESS-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN"
CODES="$RUN/codes.json"

TOOLS=(probe_image probe_image_structured probe_audio probe_video_blob probe_resource_link probe_image_path probe_structured_only)
PROMPT="You have an MCP server named media-probe. Call each of its tools exactly once, in this order: ${TOOLS[*]}.
Each result hides a 5-character code inside media (an image, audio, a video, a linked resource, a file path) or structured output.
For probe_image_path, open the file with your own file or image viewing tool. For probe_resource_link, read the resource only if you have a tool for it.
Report only codes you actually perceived. If the media did not reach you, write NONE. Never guess.
Finish with exactly one line in this form, with no code fences:
RESULT {\"probe_image\":\"...\",\"probe_image_structured\":\"...\",\"probe_audio\":\"...\",\"probe_video_blob\":\"...\",\"probe_resource_link\":\"...\",\"probe_image_path\":\"...\",\"probe_structured_only\":\"...\"}"

case "$HARNESS" in
  claude)
    CLAUDE="${CLAUDE_BIN:-$(command -v claude)}"
    cat > "$RUN/mcp.json" <<EOF
{"mcpServers":{"media-probe":{"command":"$UV","args":["run","--quiet","--script","$SERVER"],"env":{"PROBE_CODES_FILE":"$CODES"}}}}
EOF
    ALLOWED="Read,$(printf 'mcp__media-probe__%s,' "${TOOLS[@]}")"
    # --allowedTools is variadic, so the prompt goes in on stdin.
    (cd "$RUN" && printf '%s' "$PROMPT" | env -u CLAUDECODE "$CLAUDE" -p --mcp-config "$RUN/mcp.json" \
      --strict-mcp-config --allowedTools "${ALLOWED%,}" "$@") > "$RUN/transcript.txt" 2>&1 || true
    ;;
  opencode)
    cat > "$RUN/opencode.json" <<EOF
{"\$schema":"https://opencode.ai/config.json","mcp":{"media-probe":{"type":"local","command":["$UV","run","--quiet","--script","$SERVER"],"environment":{"PROBE_CODES_FILE":"$CODES"},"timeout":60000}}}
EOF
    STANDALONE=""; opencode run --help 2>&1 | grep -q -- "--standalone" && STANDALONE="--standalone"
    (cd "$RUN" && opencode run $STANDALONE --auto "$@" "$PROMPT") > "$RUN/transcript.txt" 2>&1 || true
    ;;
  pi)
    mkdir -p "$RUN/.pi"
    cat > "$RUN/.pi/mcp.json" <<EOF
{"mcpServers":{"media-probe":{"command":"$UV","args":["run","--quiet","--script","$SERVER"],"env":{"PROBE_CODES_FILE":"$CODES"},"exposure":"direct"}}}
EOF
    (cd "$RUN" && pi -p --approve --no-session "$@" "$PROMPT") > "$RUN/transcript.txt" 2>&1 || true
    ;;
  codex)
    (cd "$RUN" && "${CODEX_BIN:-codex}" exec --skip-git-repo-check --ephemeral \
      -c "mcp_servers.media-probe.command=\"$UV\"" \
      -c "mcp_servers.media-probe.args=[\"run\",\"--quiet\",\"--script\",\"$SERVER\"]" \
      -c "mcp_servers.media-probe.env={PROBE_CODES_FILE=\"$CODES\"}" \
      "$@" "$PROMPT") > "$RUN/transcript.txt" 2>&1 || true
    ;;
  *) echo "unknown harness: $HARNESS" >&2; exit 2 ;;
esac

python3 - "$RUN" <<'EOF'
import json, re, sys
from pathlib import Path
run = Path(sys.argv[1])
codes = json.loads((run / "codes.json").read_text()) if (run / "codes.json").exists() else {}
text = (run / "transcript.txt").read_text(errors="replace")
m = re.findall(r"RESULT\s*(\{.*?\})", text, re.S)
reported = json.loads(m[-1]) if m else {}
grade = {k: {"expected": v, "reported": reported.get(k), "reached_model": str(reported.get(k, "")).strip().upper() == v}
         for k, v in codes.items()}
(run / "grade.json").write_text(json.dumps(grade, indent=2))
print(run.name)
for k, g in grade.items():
    print(f"  {k:24s} {'PASS' if g['reached_model'] else 'FAIL'}  reported={g['reported']!r}")
if not codes:
    print("  server never started (no codes.json); see transcript.txt")
elif not m:
    print("  no RESULT line; see transcript.txt")
EOF
