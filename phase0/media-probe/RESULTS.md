# Media probe results (measured)

Each probe hides a fresh random code in one kind of MCP result. A pass means the model reported the exact code. "Native" means the media itself reached the model; "workaround" means the agent recovered it some other way, e.g. by running a shell tool on a file path.

| Harness / model | image | image + structuredContent | audio | video blob | resource_link | file path | structured-only | Run |
|---|---|---|---|---|---|---|---|---|
| Codex CLI 0.161.0 (VM) / gpt-6.1-sol, medium | native | native | no | workaround: ffmpeg frame from the blob's `file://` URI | no (Codex called `resources/read`, which the probe server does not implement) | yes, via `view_image` | yes | `runs/codex-20261008-010023` |

Codex 0.161 kept the image even when `structuredContent` was present. The image-drop described in codex#10334 did not reproduce.

## Not yet measured

- **Claude Code 2.1.261 (VM):** OAuth session expired; needs `claude` login on the VM. The Mac's bundled CLI is not logged in for headless use.
- **opencode 1.18.35 (VM):** no OpenAI credentials (only Meta, xAI, Z.AI), and the run hung silently. The Mac's opencode 2.0.23 has only xAI, which is out of credits.
- **pi:** the VM has 0.85.0, which predates built-in MCP (1.0). The Mac's pi 1.0.4 has only xAI.

## Follow-ups

- Implement `resources/read` in the probe so the resource_link case measures harness behavior, not a server gap.
- A video-capable model (Gemini) is still needed to tell whether native video ever arrives.

Re-run: `ssh user@linux-vm 'export PATH=$HOME/.nvm/versions/node/v24.20.0/bin:$HOME/.local/bin:$PATH; cd ~/computer-ctrl/phase0/media-probe && ./run.sh codex -m gpt-6.1-sol -c model_reasoning_effort=\"medium\" --dangerously-bypass-approvals-and-sandbox'`
