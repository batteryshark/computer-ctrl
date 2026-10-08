# Harness Integration: How Coding-Agent Harnesses Consume External Tools and Media (state as of 2026-10-07)

Method note: Where possible, these notes check harness behavior against current source code on GitHub main/dev branches, fetched 2026-10-07, as well as docs. Source-code findings say what the code does today. They do not say which release first shipped it. Items marked UNVERIFIED rest on third-party pages or on reasoning, not primary sources.

---

## 1. Per-harness MCP support, and whether MCP Image/Audio/Resource content actually reaches the model

### Takeaway
Every major harness now supports MCP over stdio and Streamable HTTP. All the verified ones pass MCP `ImageContent` to the model as a real image. They differ in the details that matter for a screenshot tool:
- Codex turns the entire result into text, dropping images, whenever `structuredContent` is present.
- Crush forwards only the first image.
- opencode silently drops `AudioContent` and `resource_link`.
- pi replaces audio with a placeholder.
- Only Gemini CLI and Codex forward MCP audio to the model. Crush does too, but only when the result has no image.

The portable result shape is: one text block (path, dimensions, ids) plus one image block, no `structuredContent`, and an image of about 2000 px or less on the long edge.

### Cited Findings

**Claude Code**
- Transports are stdio, HTTP (recommended for remote), SSE (deprecated) and WebSocket (`type: "ws"`, JSON config only). Scopes are local (`~/.claude.json`), project (`.mcp.json`, needs approval) and user. Remote auth works through `--header "Authorization: Bearer …"`, OAuth (`claude mcp login`) or `headersHelper` — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- Images: "When an MCP tool returns a PNG, JPEG, GIF, or WebP image, Claude sees the image inline in the conversation." The inline copy may be scaled or compressed. Claude Code also saves the original bytes to the session's `tool-results` directory under `~/.claude/projects/` and gives Claude the path, so it can crop or reuse the full-resolution file. This needs v2.1.283+ — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- Output limits:
  - A warning appears above 10,000 tokens.
  - The default maximum is 25,000 tokens, set with `MAX_MCP_OUTPUT_TOKENS`.
  - Text results over 50,000 characters are saved to a file.
  - The per-tool `_meta["anthropic/maxResultSizeChars"]` (ceiling 500,000 chars) "has no effect on tools that return image content; for those, raising `MAX_MCP_OUTPUT_TOKENS` is the only option."
  - Error text over about 11,000 chars is middle-truncated.
  - Source: [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- Tool search is on by default, so MCP tool definitions are deferred and only names plus server instructions load at start. `alwaysLoad: true` per server, or `_meta["anthropic/alwaysLoad"]: true` per tool, exempts tools from deferral. Tool descriptions and server instructions are truncated at 2,048 chars by default — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- Other features — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp):
  - Elicitation is supported in form and URL modes. On protocol 2026-07-28 connections, Claude Code declares `elicitation: {form: {}, url: {}}`.
  - Resources can be @-mentioned, and list/read tools are auto-provided.
  - MCP Apps UI resources (`ui://`, `text/html;profile=mcp-app`) are excluded from the @ list and the resource tool.
  - `_meta["anthropic/requiresUserInteraction"]: true` forces a permission prompt on every call.
- Bug: when a result had both `content` (with images) and `structuredContent`, Claude Code discarded `content`, so the model saw only the stringified JSON. Reported on v2.1.123, it "never worked". The issue was closed as fixed on May 2, 2026; the fixing release isn't named — [claude-code #54737 mirror](https://claudeissues.com/issue/54737-bug-mcp-tool-results-image-content-blocks-dropped-when-structuredcontent-is-also)
- Bug: for MCP error results (`isError`), the model reportedly receives only the first content block. A March 2026 follow-up says the original #1804 was auto-closed without a fix — [claude-code #39976 mirror](https://claudeissues.com/issue/39976-mcp-error-responses-still-drop-all-content-blocks-after-the-first-re-1804)

**OpenAI Codex CLI**
- Config lives in `~/.codex/config.toml`, or `.codex/config.toml` for trusted projects, under `[mcp_servers.<name>]` — [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli):
  - stdio keys: `command`, `args`, `env`, `env_vars`, `cwd`, and `experimental_environment = "remote"` for a remote executor.
  - HTTP keys: `url`, `auth` (default oauth), `bearer_token_env_var`, `http_headers`, `env_http_headers`, `http_headers_helper`.
  - Other keys: `startup_timeout_sec` (default 10), `tool_timeout_sec` (default 60), `enabled_tools`/`disabled_tools`, and per-tool `tools.<tool>.output_token_limit` and `approval_mode`.
- Source (`codex-rs/protocol/src/models.rs`, `convert_mcp_content_to_items`) — [codex models.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs):
  - MCP `image` blocks become `FunctionCallOutputContentItem::InputImage` with a `data:` URL, so the model gets a real image in the function-call output.
  - `_meta["codex/imageDetail"]` on the image block can set `auto`/`low`/`high`/`original`. The default is `high`.
  - MCP `audio` blocks become `InputAudio { audio_url: data:… }`.
  - Unknown types (`resource`, `resource_link`) are JSON-stringified into text.
- Source, same function: when `structured_content` is non-null, `as_function_call_output_payload` returns the serialized `structuredContent` as text. All `content[]` items, images included, are then dropped. This matches open issue #10334, filed against codex-cli 0.93.0 on 2026-02-01 with no maintainer response — [codex models.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs); [openai/codex #10334](https://github.com/openai/codex/issues/10334)
- Image resizing: `MAX_DIMENSION: u32 = 2048`, and "ResizeToFit" downsizes larger images; `ImageDetail::Original` skips it — [codex utils/image](https://github.com/openai/codex/blob/main/codex-rs/utils/image/src/lib.rs)
- History: issue #4819 reported that the model could not see MCP images, with the workaround "save the image file, then use the view_image tool". It is closed and links PR #5600 — [openai/codex #4819](https://github.com/openai/codex/issues/4819). PR #9815, merged 2026-01-27, fixed the TUI dropping MCP image output when text preceded the image — [openai/codex #9815](https://github.com/openai/codex/issues/9815)
- Token-estimate bug: base64 image data URLs were counted as text tokens, which made "context remaining" crash and could trigger auto-compaction. Closed and linked to PR #12419; merge status not shown — [openai/codex #11845](https://github.com/openai/codex/issues/11845)
- The documented MCP page doesn't mention resources, prompts, elicitation or image/audio content. It does mention server `instructions` — [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

**opencode (anomalyco/opencode, formerly sst/opencode)**
- Config: an `"mcp"` key in `opencode.json`, with `type: "local"` (`command` array, `environment`, `cwd`) or `type: "remote"` (`url`, `headers`, `oauth`). `timeout` defaults to 5000 ms. The docs warn that "MCP servers add to your context" — [opencode MCP docs](https://opencode.ai/docs/mcp-servers/)
- Source (`session/tools.ts`) — [opencode tools.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/session/tools.ts):
  - MCP `text` becomes text, and `image` becomes a file attachment (`data:` URL).
  - An embedded `resource` with text becomes text. With a `blob`, it is attached only when its MIME is gif, jpeg, png or webp and it is 10 MB or less; otherwise you get a "[Binary MCP resource omitted…]" placeholder.
  - The code has no branch for `audio` or `resource_link`, so these blocks are silently dropped.
- Source (`session/message-v2.ts`, `supportsMediaInToolResult`): media stays inside the tool result for these providers:
  - `@ai-sdk/anthropic` and `@ai-sdk/openai`
  - Bedrock Anthropic/Nova/Llama4 models, images only
  - xAI, images only
  - Vertex-Anthropic
  - Google, only `gemini-3` ids

  For all other providers (for example openai-compatible), media is moved into a synthetic user message — [opencode message-v2.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/session/message-v2.ts); [opencode #52977](https://github.com/anomalyco/opencode/issues/52977)
- Source (`provider/transform.ts`): `unsupportedParts()` replaces any image/audio/video/pdf part with "ERROR: Cannot read … (this model does not support X input)" when the model's capability list (from models.dev) lacks that modality — [opencode transform.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/provider/transform.ts)
- Open bugs:
  - #52977 (opened 2026-10-03, v1.18.34): images re-sent to openai-compatible providers carry no filename or tool-call id, so the model misattributes images in parallel calls — [opencode #52977](https://github.com/anomalyco/opencode/issues/52977)
  - #51652 (v1.18.32): stale or wrong image bytes are delivered from an MCP `read_image` tool — [opencode #51652](https://github.com/anomalyco/opencode/issues/51652)
  - A third-party provider plugin reports that MCP images reach the model only after the next user message, because tool-result media sits in a trailing user message — [cursor-opencode-provider #45](https://github.com/oakimov/cursor-opencode-provider/issues/45)

**pi (badlogic/pi-mono, now earendil-works/pi)**
- pi 1.0 shipped on 2026-10-01 with built-in MCP support, after Earendil (Armin Ronacher and Colin Daymond Hanna) acquired pi in April 2026. The release also added Codemode (a harness-side sandbox for tool calls) and deferred tool loading — [The Register, 2026-10-02](https://www.theregister.com/ai-and-ml/2026/10/02/pi-coding-agent-pulls-a-180-and-adds-mcp-support/5300678)
- Config: stdio and Streamable HTTP; legacy SSE is rejected. Servers live in `~/.pi/agent/mcp.json` and `.pi/mcp.json` (project file only after project trust). CLI: `pi mcp add <name> -- <cmd>` and `pi mcp add <name> --url … --bearer-token-env-var …`. Tools are named `mcp__<server>__<tool>`. Default per-request timeout is 60 s, reset by progress notifications — [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)
- Exposure modes — [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md):
  - `codemode` (the default) means tools are "neither declared to the model nor listed". They can only be called from JS scripts in the `codemode` tool.
  - `deferred` means tools load via `tool_search`.
  - `direct` means tools are declared like built-ins.
  - `hidden` means registered but unreachable.
  - Per-tool overrides go through `toolExposure`.
- Source (`dist/extensions/mcp/tools.js`, pi-coding-agent 1.0.4) — [pi tools.js](https://cdn.jsdelivr.net/npm/@earendil-works/pi-coding-agent@1.0.4/dist/extensions/mcp/tools.js):
  - Results map to model-facing text and images, and the image blocks survive truncation.
  - Text over 20 KB is middle-truncated, with the full output saved to a temp file.
  - Non-image binary resources are saved to temp files and the path is given.
  - Resource links become text naming `read_mcp_resource`.
  - `structuredContent` is used only when `content` is empty.
- Source (`@earendil-works/pi-mcp` `protocol/content.js`): audio blocks become the text `[audio <mime> omitted]` — [pi-mcp content.js](https://cdn.jsdelivr.net/npm/@earendil-works/pi-mcp@1.0.4/dist/protocol/content.js)
- In codemode, scripts receive the full `CallToolResult`, and `image(result.content[0])` forwards an image block. MCP Apps resources are omitted because "Pi does not render them" — [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)

**Gemini CLI (and its successor, Antigravity CLI)**
- Transports: stdio (`command`), SSE (`url`) and Streamable HTTP (`httpUrl`), configured under `mcpServers` in settings.json. Keys include `headers`, `timeout` (default 600,000 ms), `trust`, `includeTools`/`excludeTools`, `oauth` and `authProviderType`. CLI: `gemini mcp add --transport http …` — [Gemini CLI MCP docs](https://geminicli.com/docs/tools/mcp-server/)
- Source (`packages/core/src/tools/mcp-tool.ts`, `transformMcpContentToParts`) — [gemini-cli mcp-tool.ts](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/tools/mcp-tool.ts):
  - `image` and `audio` both become a text label plus an `inlineData` part with the original mimeType.
  - An embedded `resource` with a `blob` of any MIME becomes `inlineData`.
  - `resource_link` becomes text ("Resource Link: … at <uri>").
- This makes Gemini CLI the only verified harness where an MCP EmbeddedResource with, say, `video/mp4` reaches the model as media — [gemini-cli mcp-tool.ts](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/tools/mcp-tool.ts)
- Docs: text goes into a single `functionResponse` part, and image data goes "as a separate `inlineData` part" — [Gemini CLI MCP docs](https://geminicli.com/docs/tools/mcp-server/). The original gap was issue #2136 — [gemini-cli #2136](https://github.com/google-gemini/gemini-cli/issues/2136)
- On 2026-06-18, Gemini CLI stopped serving requests for Google AI Pro/Ultra and free individual tiers and was replaced by Antigravity CLI (`agy`). Enterprise (Code Assist Standard/Enterprise, Google Cloud) and paid API-key users keep access. Skills, hooks, subagents and extensions (now "Antigravity plugins") carried over, and `agy plugin import gemini` migrates them — [Google Developers Blog](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/); [Gemini CLI MCP docs banner](https://geminicli.com/docs/tools/mcp-server/)
- Antigravity CLI is written in Go and is reportedly not open source. Whether it handles MCP media the same way is UNVERIFIED — [Google Developers Blog](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/); [Flutter docs on Antigravity CLI](https://docs.flutter.dev/ai/antigravity-cli.md)

**Other harnesses (brief)**
- **Cursor:** the docs say MCP servers can return images, which Cursor attaches to the chat and a vision model analyzes — [Cursor MCP docs](https://cursor.com/docs/mcp.md). Forum reports describe several problems:
  - The Cursor CLI couldn't see MCP images on v1.6.23 (fix unconfirmed) — [Cursor forum](https://forum.cursor.com/t/cursor-cli-cant-parse-mcp-image-responses/135764)
  - FastMCP must use its `Image` type, not text-wrapping — [Cursor forum](https://forum.cursor.com/t/images-in-mcp-how-to-do-it/83021)
  - Images sometimes fail to display — [Cursor forum](https://forum.cursor.com/t/image-not-displaying-in-chat-when-returned-from-mcp-server/103623)
- **Cline:** the v3.13.0 changelog says "Add ability for models that support it to receive image responses from MCP servers" — [Cline CHANGELOG](https://github.com/cline/cline/blob/main/CHANGELOG.md)
- **Crush (charmbracelet):**
  - Source (`internal/agent/tools/mcp/tools.go`): only the first `ImageContent` is kept. Audio is kept only if no image is present, and it is sent as a "media" response.
  - Other content types are `fmt.Sprintf("%v")`-stringified into text.
  - Source: [crush mcp/tools.go](https://github.com/charmbracelet/crush/blob/main/internal/agent/tools/mcp/tools.go)
  - Models without image support get the error text "This model (…) does not support image data." — [crush mcp-tools.go](https://github.com/charmbracelet/crush/blob/main/internal/agent/tools/mcp-tools.go)
- **Zed:** the context-server docs list Tools and Prompts as implemented, and invite contributions for Discovery, Sampling and Elicitation. Image results aren't mentioned — [Zed context servers docs](https://zed.dev/docs/assistant/context-servers.html)
- **GitHub Copilot CLI:** user MCP config lives in `~/.copilot/mcp-config.json`, and repo `.mcp.json` / `.github/mcp.json` take precedence. Personal skills live in `~/.copilot/skills/`, and plugins install to `~/.copilot/installed-plugins/` — [Copilot CLI config dir reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference); [Copilot about plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins)
- **Goose:** MCP servers are its "extensions" — [Goose architecture](https://goose-docs.ai/docs/goose-architecture/). It is listed as an Agent Skills client — [agentskills.io](https://agentskills.io)

### Inferences

Compatibility matrix for MCP tool results (S = verified in source, D = docs, ? = unverified):

| Harness | MCP stdio / HTTP | Image → model | Audio → model | EmbeddedResource blob | resource_link | Gotchas |
|---|---|---|---|---|---|---|
| Claude Code | yes / yes (+ws) (D) | yes, inline, scaled; original also saved to disk with path (D) | no (Claude can't take audio, see §7) | ? | resources via @ / tool (D) | 25k-token cap applies to image tools; structuredContent bug fixed May 2026; error results keep first block only |
| Codex CLI | yes / yes (D) | yes, `input_image`, detail via `_meta["codex/imageDetail"]`, max 2048 px (S) | mapped to `input_audio` (S); model support uncertain (§7) | stringified to text (S) | stringified to text (S) | `structuredContent` present ⇒ images dropped (S, #10334 open) |
| opencode | yes / yes (D) | yes, as attachment; synthetic user msg for non-native providers (S) | dropped silently (S) | images ≤10 MB only (S) | dropped (S) | image misattribution and stale-bytes bugs (Oct 2026) |
| pi 1.0 | yes / yes, no SSE (D) | yes; default 2000×2000 resize (S/D) | placeholder text (S) | non-image saved to temp file, path given (S) | text pointer to `read_mcp_resource` (S) | default `codemode` exposure hides tools from direct calls; set `exposure: "direct"` |
| Gemini CLI | yes / yes (+SSE) (D) | yes, `inlineData` (S) | yes, `inlineData` (S) | any MIME → `inlineData`, so video works (S) | text (S) | replaced by Antigravity CLI for individual users since 2026-06-18 |
| Crush | yes (S) | first image only (S) | only if no image (S) | stringified (S) | stringified (S) | one image per result |
| Cline | yes | yes since 3.13 (changelog) | ? | ? | ? | — |
| Cursor | yes | yes (D); CLI buggy in 1.6 | ? | ? | ? | — |
| Zed, Goose, Copilot CLI, Amp | MCP yes | ? | ? | ? | ? | not verified |

Design rules that follow from the matrix:
1. Return exactly one image per tool call (Crush).
2. Put a short text block first, with the saved file path, pixel dims, scale factor and a screenshot id. This works around opencode's lack of filenames on forwarded images (#52977) and gives CLI-mode parity.
3. Never set `structuredContent` or `outputSchema` on image-returning tools (Codex drops images; Claude Code did too before May 2026). Put machine-readable data as JSON text in the text block instead.
4. Keep images at about 2000 px or less on the long edge (Codex 2048, pi 2000×2000) and well under Claude Code's 25k-token MCP cap.
5. Make audio and video opt-in and always pair them with text (a transcript or frame descriptions), because most harnesses drop or placeholder them.

Pi's codemode default is notable. A computer-use MCP server installed in pi without `exposure: "direct"` (or a `toolExposure` override) is reachable only via scripts. That hurts the tight screenshot→click loop.

### Gaps
- No primary-source verification for Goose, Zed, Copilot CLI, Amp, Roo Code or Windsurf on MCP image passthrough. The issue and source searches didn't surface their result-conversion code.
- Could not confirm which Codex release fixed MCP images reaching the model. PR #5600 is "closed" and merge state wasn't visible, but current main clearly maps images to `input_image`.
- Claude Code's handling of MCP `audio` and `resource`/`resource_link` blocks in tool results isn't documented. Behavior is unknown; images are documented.
- Antigravity CLI's MCP media handling is unknown (closed source).

---

## 2. Built-in ways to view an image, audio or video file from disk (the "CLI writes a file, agent views it" pattern)

### Takeaway
Every target harness can view a PNG/JPEG from disk with a built-in tool:
- Claude Code: Read
- Codex: `view_image`
- opencode: read
- pi: read
- Gemini CLI: `read_file`

This makes "CLI writes a PNG and prints its path" universally viable. Only Gemini CLI's `read_file` also loads audio and video, up to 20 MB, as native media.

### Cited Findings
- Mario Zechner's browser-tools pattern: the screenshot script "saves a PNG of the current viewport to a temporary directory and prints the file path", and the agent then reads that file with its vision capabilities — [Zechner, "What if you don't need MCP?" (2025-11-02)](https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/)
- Codex `view_image` takes a path and an optional `detail`; "original" is allowed only when the model can request original detail. It errors with "view_image is not allowed because you do not support image inputs" for non-vision models — [codex view_image.rs](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/view_image.rs). Codex also has local *audio* user-input plumbing: wav/mp3/m4a/webm/ogg, `MAX_PROMPT_AUDIO_INPUT_BYTES = 50 MiB` ("matches the Responses API audio input limit"). This is for user attachments, not a model-callable tool — [codex local_media.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/local_media.rs)
- The workaround documented in Codex #4819 before MCP images worked: "MCP server save the image file, and then use the view_image tool" — [openai/codex #4819](https://github.com/openai/codex/issues/4819)
- opencode's `read` tool attaches JPEG/PNG/GIF/WebP images and PDFs as `data:` URL attachments ("Image read successfully") — [opencode read.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/tool/read.ts). An older bug: the read tool failed on images with vision models while paste worked — [opencode #11306](https://github.com/anomalyco/opencode/issues/11306)
- pi's `read` tool reads "text files and supported images" — [pi CLI docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md). Images from `read` results are resized per `inputLimits.images.resize` (default 2000×2000, 4.5 MiB encoded, JPEG quality 80) before entering history — [pi models docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md)
- Gemini CLI `read_file` — [gemini-cli fileUtils.ts](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/utils/fileUtils.ts):
  - It detects `'text' | 'image' | 'pdf' | 'audio' | 'video' | 'binary' | 'svg'`.
  - Audio (supported formats only), image, pdf and video are returned as base64 `inlineData`.
  - `MAX_FILE_SIZE_MB = 20`.
- Claude Code: the docs above confirm image handling for MCP results. Claude Code's Read tool viewing images (and PDFs) is long-standing behavior, and the MCP doc notes Claude "can then crop, convert, or reuse the full-resolution file with tools such as Bash" — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)

### Inferences
- A CLI-first toolkit, where a `screenshot` command writes a PNG and prints its absolute path plus metadata, works in all five primary harnesses with zero integration code. The cost is one extra tool call per observation (bash → read) versus inline MCP.
- For audio and video, only Gemini CLI can "read" the file natively. Elsewhere the CLI must produce derived artifacts: a contact-sheet PNG, keyframe PNGs, a transcript text file.
- Recommended CLI output convention: print a one-line JSON object such as `{"path":"/tmp/cc/shot-0042.png","w":1280,"h":800,"scale":0.5,"id":"0042"}` and nothing else on stdout. Skills then instruct "read the file at `path`".

### Gaps
- Not verified from a primary doc page fetched in this session: the exact image formats and size limits of Claude Code's Read tool, and whether it reads audio. Claude models don't accept audio (§7), so audio is presumed unsupported.
- Whether Antigravity CLI's file-read tool retains Gemini CLI's audio/video support is unknown.

---

## 3. Agent Skills (SKILL.md) support, discovery paths, and bundling binaries

### Takeaway
Agent Skills (agentskills.io) are now near-universal. Claude Code, Codex, opencode, pi, Gemini CLI, Cursor, Copilot/VS Code, Goose, Amp, Roo Code, Junie, Kiro, Factory, OpenHands and Mistral Vibe all list support. The cross-harness path `.agents/skills/` (project) and `~/.agents/skills/` (user) is read by Codex, opencode, pi and Gemini CLI. Claude Code documents only `.claude/skills` and `~/.claude/skills`, and opencode also reads those.

### Cited Findings
- The agentskills.io client list includes Junie, Gemini CLI, OpenCode, OpenHands, Mux, Cursor, Amp, Letta, Goose, GitHub Copilot, VS Code, Claude Code, Claude, "ChatGPT & Codex", Factory, pi, Roo Code, Mistral Vibe, Kiro, Tabnine, Hermes Agent, OpenClaw and others — [agentskills.io](https://agentskills.io)
- Spec: a skill is a folder with `SKILL.md` (frontmatter `name`, `description` at minimum) plus optional `scripts/`, `references/` and `assets/`. Loading is progressive: name and description at startup, full body on activation, files on demand — [agentskills.io](https://agentskills.io). Spec fields: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` (experimental) and `disable-model-invocation`. Names are at most 64 chars in lowercase-hyphen form; descriptions are at most 1024 chars — [pi skills docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)
- **Claude Code** — [Claude Code skills docs](https://code.claude.com/docs/en/skills):
  - Locations: `~/.claude/skills/<name>/SKILL.md`, `.claude/skills/` (start dir up to repo root), nested `<subdir>/.claude/skills`, `--add-dir`, plugin `skills/`, and enterprise managed dir. The page doesn't mention `.agents/skills`.
  - `${CLAUDE_SKILL_DIR}` resolves to the skill directory. It works in `allowed-tools`, for example `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/render.sh *)`, so bundled scripts run without permission prompts.
  - Extensions to the spec: `context: fork`, `paths`, `hooks`, `model`, `effort`, and `` !`cmd` `` injection.
- **Codex** — [Codex skills docs](https://learn.chatgpt.com/docs/build-skills):
  - Locations: `$CWD/.agents/skills`, `$CWD/../.agents/skills`, `$REPO_ROOT/.agents/skills`, `$HOME/.agents/skills`, `/etc/codex/skills`, plus bundled system skills.
  - Install with `$skill-installer <name>`.
  - The optional `agents/openai.yaml` sets UI metadata, `policy.allow_implicit_invocation`, and `dependencies.tools` (for example MCP servers).
  - "Skills are the authoring format, plugins are the distribution format."
- **opencode** — [opencode skills docs](https://opencode.ai/docs/skills/):
  - Locations: `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` (project, walking up to the git worktree), and `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/` (global).
  - Loaded via the native `skill` tool, with `permission.skill` allow/deny/ask.
  - `name` must match the directory name.
- **pi** — [pi skills docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md); [pi security docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/security.md); [pi settings docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md):
  - Implements the Agent Skills spec and reads `~/.agents/skills/` and `.agents/skills/` (ancestors up to the repo root).
  - The project dir is `.pi/skills`, which needs project trust.
  - The `skills` settings array adds paths, and `/skill:name` forces loading.
  - The user-level pi-specific dir is presumably `~/.pi/agent/skills`, by analogy with `~/.pi/agent/extensions/` — UNVERIFIED verbatim.
- **Gemini CLI** — [Gemini CLI skills docs](https://geminicli.com/docs/cli/skills/):
  - Locations: built-in, extension `skills/`, `~/.gemini/skills/` or `~/.agents/skills/`, and `.gemini/skills/` or `.agents/skills/` (`.agents` wins within a tier).
  - Activated via the `activate_skill` tool with user confirmation; the skill dir becomes an allowed path.
  - Install with `gemini skills install <git-url|dir> --scope user|workspace`.
- **Antigravity CLI** reportedly respects `.agents/skills/` — UNVERIFIED, third-party — [Flutter docs on Antigravity CLI](https://docs.flutter.dev/ai/antigravity-cli.md)
- **Copilot CLI**: personal skills live in `~/.copilot/skills/`, and plugins contain `skills/<name>/SKILL.md` — [Copilot CLI config dir reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference)
- Bundling executables:
  - Claude Code: shown in the `scripts/` examples above, and plugins can ship `bin/` on PATH (§5) — [Claude Code skills docs](https://code.claude.com/docs/en/skills)
  - Codex: skills may include `scripts/` "executable code", but compiled binaries aren't addressed — [Codex skills docs](https://learn.chatgpt.com/docs/build-skills)
  - Gemini: bundled scripts are allowed; execution isn't explicitly addressed — [Gemini CLI skills docs](https://geminicli.com/docs/cli/skills/)

### Inferences
- Install the toolkit's skill once at `~/.agents/skills/computer-use/`, which covers Codex, opencode, pi, Gemini CLI and probably Antigravity. Symlink it into `~/.claude/skills/computer-use/` for Claude Code; Claude Code supports symlinked skill folders per its docs. Put platform binaries (or a tiny launcher that finds or downloads the right binary) in `scripts/`.
- Keep frontmatter to the six spec fields for portability. Claude Code extras like `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/cuctl *)` are harmless elsewhere, because unrecognized fields are ignored by opencode and pi warns rather than failing.
- Make the skill body tiny, a few hundred tokens: Zechner's README was 225 tokens versus 13.7k–18k tokens for the Playwright and Chrome DevTools MCPs (§4). Push details to `references/`.

### Gaps
- Exact Cursor skill discovery paths, and whether Cursor and Copilot CLI read `.agents/skills`, weren't verified. One third-party page rated Cursor's support "Partial (project-only)" — [agensi.io](https://www.agensi.io/learn/every-ai-agent-that-supports-skill-md-2026) (low reliability).
- Whether a future Claude Code version reads `.agents/skills` couldn't be confirmed. The current docs omit it.

---

## 4. pi specifically: MCP stance, extension/tool API, images, existing computer-use extensions

### Takeaway
Pi went from "no MCP, use CLI tools plus READMEs" (Nov 2025) to built-in MCP in pi 1.0 (Oct 1 2026). Even so, its default exposes MCP tools only through codemode scripts, and its native extension API (TypeScript `pi.registerTool`, image-capable results, npm/git packages) remains the most idiomatic integration. Several community pi computer-use packages already exist.

### Cited Findings
- Zechner's argument — [Zechner, "What if you don't need MCP?"](https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/):
  - Playwright MCP is "21 tools using 13.7k tokens (6.8% of Claude's context)" and Chrome DevTools MCP is 26 tools and 18.0k tokens (9.0%). His browser-tools README is "a whopping 225 tokens", loaded only when needed.
  - "MCP servers also aren't composable."
  - The screenshot tool saves a PNG to a temp dir and prints the path.
  - He doesn't reject MCP outright: "in many situations, you don't need or even want an MCP server."
- Zechner's pi design post lists "No MCP support" as deliberate. It says tools can return attachments like images "attached in the native format of the respective provider" — [Zechner, pi coding agent post (2025-11-30)](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/)
- Armin Ronacher (now at Earendil, pi's owner) argued earlier that MCP isn't truly composable and costs more context than code. He proposed MCPs that expose a single code-execution entry point — [Ronacher, "Tools: Code Is All You Need"](https://lucumr.pocoo.org/2025/7/3/tools/); [Ronacher, "Your MCP Doesn't Need 30 Tools: It Needs Code"](https://lucumr.pocoo.org/2025/8/18/code-mcps/). Pi 1.0's Codemode default is consistent with that view — [The Register](https://www.theregister.com/ai-and-ml/2026/10/02/pi-coding-agent-pulls-a-180-and-adds-mcp-support/5300678)
- The reversal: "Pi coding agent pulls a 180 and adds MCP support", pi 1.0, 2026-10-01. Earendil said "things change" — [The Register](https://www.theregister.com/ai-and-ml/2026/10/02/pi-coding-agent-pulls-a-180-and-adds-mcp-support/5300678)
- Before 1.0, MCP came via the third-party `pi-mcp-adapter` extension — [mcp-debugger #714](https://github.com/debugmcp/mcp-debugger/issues/714). An installed extension that registers `/mcp` (for example pi-mcp-adapter) replaces the built-in MCP — [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)
- Extension API — [pi extensions docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md):
  - `pi.registerTool()` takes a TypeBox schema and an `execute()`. The result needs model-facing `content` plus `details`.
  - Optional `outputSchema` + `structuredContent` is passed to codemode scripts, while the model still gets `content`.
  - `pi.registerMcpServer(name, config)` registers a server for the session. Extensions live in, for example, `~/.pi/agent/extensions/*.ts`.
- Packages — [pi packages docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/packages.md):
  - A package bundles `extensions/`, `skills/`, `prompts/` and `themes/`.
  - Install with `pi install npm:@x/y@1.0.0 | git:github.com/x/y@v1 | ./local`, or try with `pi -e`.
  - The `pi-package` npm keyword lists it in the pi.dev gallery.
- Images — [pi models docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md); [pi settings docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md); [pi codemode docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/codemode.md):
  - `inputLimits.images.resize` (default 2000×2000, 4.5 MiB, JPEG q80) applies to attachments, `read` results and tool-result images. "Images are encoded once; changing models does not rewrite historical images."
  - Settings `images.autoResize` (default true) and `images.blockImages`.
  - Codemode `image()` accepts PNG/JPEG/GIF/WebP, and each image is also saved to a temp file with its path given.
- Existing pi computer-use packages — [pi.dev @injaneity/pi-computer-use](https://pi.dev/packages/@injaneity/pi-computer-use); [pi.dev @amaster.ai/pi-computer-use](https://pi.dev/packages/@amaster.ai/pi-computer-use?page=2); [PriNova/pi-os](https://github.com/PriNova/pi-os):
  - `@injaneity/pi-computer-use` v0.5.0 covers macOS, Windows and Linux. Its tools find windows, read UI, search for text and controls, and click/type/scroll/wait. The macOS helper needs macOS 14+ with Accessibility and Screen Recording permission.
  - `@amaster.ai/pi-computer-use` wraps `cua-driver-rs` with `computer_use_*` tools and an optional vision-model screenshot analyzer.
  - A swairshah macOS package does screencapture plus vision-model grounding plus a Swift input helper.
  - PriNova/pi-os is a Windows hotkey overlay with a `desktop_act` tool.

### Inferences
- For pi, ship a pi package containing (a) a TypeScript extension that registers native tools by shelling out to the shared CLI binary and returning image content, and (b) the shared SKILL.md. This avoids codemode indirection and works on pi versions before 1.0.
- If MCP is used with pi 1.0, document `"exposure": "direct"` for the computer-use server, or direct exposure for just `screenshot`/`click`/`type`.
- Pi's codemode is useful for batched multi-step UI scripts: scripts get full `CallToolResult`s and can choose which image to forward with `image()`.

### Gaps
- Exact pi 1.0 behavior for images returned from *direct* MCP tool calls: the code maps them to images, but this wasn't live-tested.
- No primary statement from Zechner explaining the reversal was found; The Register quotes Earendil.

---

## 5. Plugin/extension systems that can ship the toolkit as a first-class package

### Takeaway
Each major harness has a package format that can bundle MCP config, skills and (in most) executables:
- Claude Code plugins: `bin/` on PATH, `.mcp.json`, skills, `.mcpb` bundles, marketplaces.
- Codex plugins: a shared ChatGPT/Codex plugin directory bundling skills and MCP.
- opencode: JS/TS custom tools and plugins.
- pi packages via npm/git.
- Gemini CLI extensions, now Antigravity plugins: `gemini-extension.json` with `mcpServers` and `skills/`.
- Copilot CLI plugins.

### Cited Findings
- **Claude Code plugin** — [Claude Code plugins reference](https://code.claude.com/docs/en/plugins-reference):
  - The manifest is `.claude-plugin/plugin.json`, which is optional.
  - Default layout: `skills/`, `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`, `.lsp.json`, `monitors/monitors.json`, `bin/`.
  - "Files [in `bin/`] are on the Bash tool's `PATH` while the plugin is enabled, so Claude runs them as bare commands." claude.ai and Cowork don't install plugins that have `bin/`.
  - `mcpServers` accepts `.mcpb`/`.dxt` bundles, including by URL.
  - Variables: `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` (persists across updates, at `~/.claude/plugins/data/<id>/`).
  - `userConfig` supports `sensitive` secrets stored in the OS credential store, and `claude plugin validate` checks plugins.
- **Codex plugins**: plugins can bundle MCP servers in their manifest. User config `[plugins."<plugin>".mcp_servers.<server>]` controls enablement and policy, and plugin OAuth is declared in `.mcp.json` — [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). There is a "universal plugin directory shared by ChatGPT and Codex", and plugins bundle multiple skills, MCP connections and assets — [Codex skills docs](https://learn.chatgpt.com/docs/build-skills)
- **opencode custom tools**: TS/JS files in `.opencode/tools/` or `~/.config/opencode/tools/` using `tool()` from `@opencode-ai/plugin`. They can invoke scripts in any language (Python example via `Bun.$`). Examples return strings, and the docs don't mention returning images — [opencode custom tools docs](https://opencode.ai/docs/custom-tools/)
- **pi packages**: see §4 — [pi packages docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/packages.md)
- **Gemini CLI extensions** — [Gemini CLI extension reference](https://geminicli.com/docs/extensions/reference/):
  - `gemini-extension.json` has `name`, `version`, `mcpServers` (all options except `trust`), `contextFileName`, `excludeTools` and `settings` (`envVar`, `sensitive` → keychain).
  - Directory-based components: `commands/*.toml`, `hooks/hooks.json`, `skills/<name>/SKILL.md`, `agents/`, `policies/`.
  - Variables: `${extensionPath}` and `${workspacePath}`.
  - Install with `gemini extensions install <github-url|path>` or `gemini extensions link <path>`.
- Antigravity converts Gemini extensions into "Antigravity plugins" via `agy plugin import gemini` — [Google Developers Blog](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
- **Copilot CLI plugins**: installable from a repo, a marketplace or a local path via `copilot plugin`. A plugin contains a manifest, agents, `skills/…/SKILL.md`, `hooks.json` and `.mcp.json` — [Copilot about plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins); [Copilot CLI config dir reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference)

### Inferences
- Recommended packaging: one native binary (`cuctl`) with subcommands, plus `cuctl mcp` (an MCP stdio server mode) and `cuctl serve --http` (remote mode). Thin per-harness wrappers:
  - Claude Code plugin: `bin/cuctl` and `.mcp.json` pointing to `${CLAUDE_PLUGIN_ROOT}/bin/cuctl mcp`, plus `skills/computer-use`.
  - Gemini/Antigravity extension: `mcpServers` with `${extensionPath}`, plus `skills/`.
  - Codex plugin, or `config.toml` snippet plus `~/.agents/skills`.
  - pi package: extension plus skill.
  - opencode: `opencode.json` `mcp` entry plus skill, since opencode custom tools aren't documented to return images.
- Since all wrappers point at the same binary, behavior stays identical. The MCP layer and the CLI layer are two front-ends to one core.

### Gaps
- Codex plugin manifest format, file layout and whether it can ship binaries weren't retrieved.
- Whether opencode plugin or custom-tool results can carry image attachments is undocumented.
- Amp, Goose, Cursor and Zed plugin/extension formats weren't researched in depth.

---

## 6. MCP spec state in 2026 and which harnesses implement the relevant features

### Takeaway
The current spec is **2026-07-28**; the previous one was 2025-11-25. It makes MCP stateless: no initialize handshake, no `Mcp-Session-Id`, and a new `server/discover`. It moves Tasks to an official extension, replaces server-initiated requests (sampling, elicitation, roots) with Multi Round-Trip Requests, deprecates Roots, Sampling and Logging, and adds MCP Apps as a companion extension. Content types are unchanged: text, image, audio, resource, resource_link. There is **no video content type** and no accepted file-transfer mechanism.

### Cited Findings
- Major changes in 2026-07-28 — [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog):
  - Protocol-level sessions and `Mcp-Session-Id` removed (SEP-2567).
  - Initialize handshake removed: each request carries protocol version and capabilities in `_meta` (SEP-2575).
  - New mandatory `server/discover`.
  - `subscriptions/listen` replaces the GET endpoint and resource subscribe.
  - `ping` and `logging/setLevel` removed.
  - Tasks moved to an extension, `io.modelcontextprotocol/tasks`, with polling via `tasks/get` and a new `tasks/update` (SEP-2663).
  - MRTR (`InputRequiredResult`, `resultType: "input_required"`) replaces server-initiated `sampling/createMessage`, `elicitation/create` and `roots/list` (SEP-2322).
  - SSE resumability removed (SEP-2575).
- Minor changes — [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog):
  - `extensions` capability field.
  - Deterministic `tools/list` order recommended, for prompt caching.
  - `Mcp-Method`/`Mcp-Name` headers.
  - `ttlMs`/`cacheScope` on list results (SEP-2549).
  - Any JSON Schema 2020-12 keyword allowed in input/output schemas, and `structuredContent` may be any JSON value (SEP-2106).
- Deprecated: Roots, Sampling and Logging (SEP-2577), with the suggested migration of "integrate directly with LLM provider APIs instead of Sampling". Also deprecated: HTTP+SSE transport and Dynamic Client Registration (in favor of Client ID Metadata Documents) — [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- MCP Apps (SEP-1865) delivers interactive HTML UIs rendered in sandboxed iframes by hosts. The final spec was announced 2026-07-28; the release candidate was 2026-05-21 — [MCP blog 2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/); [SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp)
- Host support:
  - Claude Code declares form+URL elicitation on 2026-07-28 connections and excludes MCP Apps UI resources from model-facing resource lists — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
  - Pi omits MCP Apps resources — [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)
  - Zed implements Tools and Prompts only — [Zed docs](https://zed.dev/docs/assistant/context-servers.html)
  - Codex chooses CIMD or DCR automatically for OAuth — [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- Video and files:
  - No video content-type SEP was found.
  - The closest is SEP-2631, "File Objects and Transfer" (URI plus metadata, with bytes moved over authorized HTTPS). A commenter cited video editing as a use case — [SEP-2631 PR](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2631)
  - A June 2026 write-up says file-upload SEPs (SEP-1306, SEP-2356) were not in the 2026-07-28 RC — [dev.to on MCP file transfer](https://dev.to/kenimo49/7-services-0-upload-solutions-why-mcp-file-transfer-fails-2f2o)

### Inferences
- Don't depend on Sampling: it's deprecated, and harness support was always thin. Don't depend on Tasks either: it's an extension now, and no harness was found implementing it.
- For long operations like recording a 10 s clip, use synchronous tools with progress notifications. Pi resets its timeout on progress; Codex's default tool timeout is 60 s and Gemini's is 600 s. Keep clip tools under about 60 s, or expose start/stop tool pairs with explicit handles (the SEP-2567 style).
- Being stateless, the 2026-07-28 Streamable HTTP transport suits a remote computer-use server behind a plain load balancer. Session state (current display, last screenshot id) should be passed as explicit handles in tool arguments.
- To ship video over MCP portably, the only options are an EmbeddedResource `blob` with `mimeType: video/mp4` (works only in Gemini CLI) or a `resource_link`/file path (needs a harness tool that can view video, again only Gemini).

### Gaps
- Which harnesses have already moved to protocol 2026-07-28 (other than Claude Code, which mentions it) wasn't established.
- SEP-2631's current status (draft, accepted or rejected) couldn't be confirmed.

---

## 7. Audio/video-capable models in these harnesses, whether a harness can forward tool audio/video, and fallbacks

### Takeaway
- **Video:** only Gemini models through Gemini CLI can receive it from a tool today, via `read_file` (≤20 MB) or an MCP EmbeddedResource blob.
- **Audio:** Gemini CLI (inlineData) works. Codex maps MCP audio to `input_audio`, but mainstream GPT-5-family models reportedly don't accept audio input, which is a conflicting signal (see below). Claude cannot take audio. opencode drops audio and pi replaces it with a placeholder.
- **Fallback for everyone else:** transcripts (Whisper/Parakeet-class ASR) and video contact sheets or keyframe images.

### Cited Findings
- Gemini 3 Pro inputs: "Text, Code, Images, Audio, Video, PDF". Gemini 3 function responses "can now include multimodal objects like images and PDFs in addition to text" — audio and video in function responses aren't stated — [Vertex Gemini 3 Pro](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-pro); [Vertex Gemini 3 Flash](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash). Gemini 3 Flash per-prompt limits: max 1 audio file and max 10 videos — [Vertex Gemini 3 Flash](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash)
- Some Gemini models return "Multimodal function responses are not supported for this model" (400) when images are placed inside the function response — [Google AI forum](https://discuss.ai.google.dev/t/unable-to-process-multimodal-function-calls-response/106660). Gemini CLI sidesteps this by sending media as separate `inlineData` parts — [Gemini CLI MCP docs](https://geminicli.com/docs/tools/mcp-server/)
- Gemini CLI forwards MCP `audio` and any-MIME resource blobs as `inlineData`, and `read_file` returns audio and video as `inlineData` up to 20 MB — [gemini-cli mcp-tool.ts](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/tools/mcp-tool.ts); [gemini-cli fileUtils.ts](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/utils/fileUtils.ts)
- OpenAI evidence conflicts:
  - OpenAI's audio guide puts the Responses API in a text+image lane and routes audio chat to Chat Completions or Realtime. `gpt-realtime-2` and `gpt-audio-1.5` handle audio in and out — [OpenAI audio guide](https://developers.openai.com/api/docs/guides/audio.md)
  - A developer reported `input_audio` rejected by the Responses API — [OpenAI community](https://community.openai.com/t/audio-input-not-working-when-migrating-from-completions-to-responses/1364108)
  - But Codex main contains `ContentItem::InputAudio`, maps MCP audio to `FunctionCallOutputContentItem::InputAudio`, and comments that its 50 MiB limit "matches the Responses API audio input limit" — [codex local_media.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/local_media.rs); [codex models.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs)
  - So audio input via Responses may have shipped for some newer models by Oct 2026. UNVERIFIED which.
- Claude: a July 2, 2026 feature request says Claude can't take in sound and audio must be transcribed first — [claude-code feature request mirror](https://claudeissues.com/issue/73566-feature-allow-claude-to-hear-and-process-audio). This is user-filed, not an Anthropic doc; treat as likely but not authoritative.
- Qwen3-Omni (Thinker-Talker MoE) handles text, images, audio and video — [HF Transformers docs](https://huggingface.co/docs/transformers/main/model_doc/qwen3_omni_moe). On Alibaba Model Studio, Qwen3-Omni-Flash audio and video input is capped at 150 s — [Alibaba Model Studio](https://help.aliyun.com/en/model-studio/qwen-omni). One host lists text plus one other modality per request — [Novita](https://novita.ai/models/model-detail/qwen-qwen3-omni-30b-a3b-instruct)
- opencode understands audio and video modalities via model capabilities (`mimeToModality`). But its MCP adapter drops audio blocks and only attaches image blobs, so tool-originated audio and video never reach Qwen3-Omni or Gemini through opencode — [opencode transform.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/provider/transform.ts); [opencode tools.ts](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/session/tools.ts)
- pi's model input types are `"text" | "image"` in its catalog schema, and MCP audio becomes a placeholder — [pi models docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md); [pi-mcp content.js](https://cdn.jsdelivr.net/npm/@earendil-works/pi-mcp@1.0.4/dist/protocol/content.js)
- Crush forwards MCP audio as a "media" response only when no image is present, and gates it on the model's image support flag — [crush mcp/tools.go](https://github.com/charmbracelet/crush/blob/main/internal/agent/tools/mcp/tools.go); [crush mcp-tools.go](https://github.com/charmbracelet/crush/blob/main/internal/agent/tools/mcp-tools.go)

### Inferences
- Capability-negotiate at the toolkit level: a `--media` or `CUCTL_MEDIA=image|image+audio|image+audio+video` setting (or per-call args) that the skill tells the agent to set based on the harness and model.
  - Default: image only, plus text transcripts and contact sheets.
  - On Gemini CLI: allow native audio and video, either `read_file` on a `.mp4`/`.wav` under 20 MB or MCP resource blobs.
- Video fallback hierarchy:
  1. A contact sheet: a single PNG grid of N timestamped frames, about 3×3 at 1280 px total.
  2. Scene-change keyframes, each a separate image only on request.
  3. A text summary of frame diffs (changed regions, OCR of new text).
  
  Audio fallback: ASR transcript with timestamps, plus a short "sound events" text line, then a raw clip only for harnesses known to forward audio.
- Because the CLI writes files, a single capture can serve all paths. Write `clip.mp4`, `clip_contact.png`, `clip.wav` and `clip.txt`, and return paths plus the contact-sheet image inline.

### Gaps
- No authoritative OpenAI model card was fetched confirming which current GPT models, if any, accept `input_audio` in Responses function-call outputs.
- No test was found of whether Gemini models actually interpret video `inlineData` sent as a separate part after a function response, in Gemini CLI's message layout. The code sends it; model behavior wasn't verified.
- The availability of Qwen3-Omni in the specific harnesses' provider catalogs (models.dev and OpenRouter) wasn't confirmed.

---

## 8. Context/token management for screenshot-heavy loops

### Takeaway
Harnesses offer partial help:
- Claude Code: tool search defers tool definitions, MCP images are capped by `MAX_MCP_OUTPUT_TOKENS`, and the full-resolution original is saved to disk.
- pi: resize defaults and codemode filtering.
- Codex: per-tool `output_token_limit` and a 2048 px resize.

None of them prunes old screenshots automatically, and compaction with many images has been slow or miscounted. The toolkit itself should be text-first, downscale, crop on demand, and reference images by file path and id.

### Cited Findings
- Tool-definition overhead: Playwright MCP is 13.7k tokens and Chrome DevTools MCP is 18.0k, versus a 225-token README — [Zechner](https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/). Claude Code's tool search defers definitions by default, with an `auto:N` threshold mode — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp). Pi's `codemode`/`deferred` exposure keeps tools out of the declared set — [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)
- Claude Code: MCP image results are scaled or compressed inline, the original is saved, and the path is given to the model. `MAX_MCP_OUTPUT_TOKENS` (default 25k) still governs image-bearing results — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- Claude Code compaction with images: a Feb 2026 feature request reported screenshots as 86% of context by size and compaction taking 12+ minutes. It asked for image-aware compaction or PreCompact hooks that strip images; closed 2026-02-12 with resolution unclear — [claude-code #24298 mirror](https://claudeissues.com/issue/24298-feature-image-aware-compaction-strip-summarize-images-before-context-compression)
- Codex: base64 MCP images inflated the token estimate and triggered auto-compaction (closed, linked PR) — [openai/codex #11845](https://github.com/openai/codex/issues/11845). Codex resizes to 2048 max and supports `detail: low` through `_meta["codex/imageDetail"]` — [codex models.rs](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs); [codex utils/image](https://github.com/openai/codex/blob/main/codex-rs/utils/image/src/lib.rs). Per-tool `output_token_limit` exists — [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- pi: images are resized once on entry (2000×2000 / 4.5 MiB / q80 defaults) and never rewritten. `images.blockImages` blocks all images. In codemode, scripts can call tools, filter, and forward only selected images, and only script output reaches the model — [pi models docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md); [pi settings docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md); [pi codemode docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/codemode.md)
- Cursor users hit "conversation too long" when a Puppeteer MCP dumped base64 screenshots as text. The workaround was saving to disk and returning a path — [Cursor forum](https://forum.cursor.com/t/images-in-mcp-how-to-do-it/83021) (version-specific, older)
- Third-party estimate: about 1,000 tokens per screenshot, with image token cost driven by pixel dimensions, not content — [morphllm](https://www.morphllm.com/claude-code-token-limit); [pxpipe](https://gittrend.io/repo/teamchong/pxpipe) (secondary, low reliability)

### Inferences
Recommended observation strategy for the toolkit:
1. **Text-first observe:** `observe` returns the accessibility tree or OCR as compact text (element ids, roles, labels, bounding boxes), with no image unless requested.
2. **Downscaled screenshot by default:** long edge about 1280–1568 px, JPEG or WebP, with a scale factor reported in the text block so coordinates map back.
3. **Zoom/crop tool:** returns a full-resolution crop of a region, and on Codex sets `codex/imageDetail: "high"` or `"original"`.
4. **Image references:** every image is saved to disk with an id; the agent can re-view by path instead of the toolkit re-sending.
5. **Diff mode:** return "no visual change" text or a changed-region crop instead of a full screenshot after actions.
6. **A `max_images` or "last N" hint in the skill instructions**, since harnesses don't prune. In pi, an extension `context` handler could strip old tool-result images: pi exposes `context` transforms of conversation messages. In Claude Code, a PreCompact or PostToolUse hook in the plugin could help, though hook support for stripping images isn't verified.

- The CLI path (bash prints a path, then the agent reads the file) naturally avoids base64 in text and lets the agent skip viewing when text suffices. The cost is an extra round trip.

### Gaps
- Whether any harness's auto-compaction now strips or summarizes old images, as of Oct 2026, couldn't be confirmed from primary docs.
- No primary token-per-image formulas for each provider were gathered in this pass.

---

## 9. Remote operation: an agent on machine A controlling machine B

### Takeaway
Two patterns work across harnesses:
- **Streamable HTTP MCP on machine B with bearer-token auth**, reachable over a private network such as Tailscale. This is supported by Claude Code, Codex, opencode, pi and Gemini CLI, and the 2026-07-28 stateless transport makes it simpler.
- **SSH as the stdio transport**: `command: "ssh"`, `args: ["-T", "host", "/abs/path/cuctl", "mcp"]`.

For the CLI and skill path, the same binary can run as a client that talks to a remote daemon.

### Cited Findings
- Remote HTTP config per harness:
  - Claude Code: `claude mcp add --transport http <name> <url> --header "Authorization: Bearer …"`, OAuth, `headersHelper` — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
  - Codex: `url` with `bearer_token_env_var`, `http_headers`/`env_http_headers`/`http_headers_helper`, or OAuth — [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
  - opencode: `type: "remote"`, `url`, `headers`, `oauth` — [opencode MCP docs](https://opencode.ai/docs/mcp-servers/)
  - pi: `url` with `headers` (`${VAR}` or `!command`), `oauth`, and `pi mcp add --url … --bearer-token-env-var` — [pi MCP docs](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)
  - Gemini CLI: `httpUrl` with `headers` and `oauth` — [Gemini CLI MCP docs](https://geminicli.com/docs/tools/mcp-server/)
- Codex stdio servers accept `experimental_environment = "remote"` to use a remote executor, and `env_vars` sources can be `"local"` or `"remote"` — [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- The 2026-07-28 spec removes sessions and SSE resumability, so "Operators can now run a plain round-robin load balancer". A broken stream loses the in-flight request, which the client must re-issue — [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog); [MCP blog](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- SSH-as-stdio pattern: an MCP config whose `command` is `ssh`, with args holding the target, port, remote binary path and config — [Selin MCP listing](https://lobehub.com/ko/mcp/sysrex-selin). An alternative design runs the MCP server locally and uses SSH only to execute commands, reusing `~/.ssh/config`, keys and ProxyJump — [remote-ssh-mcp](https://glama.ai/mcp/servers/bbt567/remote-ssh-mcp)
- Claude Code plugin validation warns about `http://` or `ws://` URLs to non-loopback hosts and about header values that look like literal credentials — [Claude Code plugins reference](https://code.claude.com/docs/en/plugins-reference)

### Inferences
- Remote design:
  - Machine B runs `cuctl serve --http --listen 100.x.y.z:7777` (a Tailscale IP) with a bearer token.
  - Machine A's harness config uses a URL and header via an env var, never a literal.
  - Images return inline over MCP. In CLI mode, run `cuctl --remote https://b:7777 screenshot`, which downloads the PNG to a local temp path and prints that path, so A's file-view tools work.
- The SSH stdio variant needs `-T` (no pty), `BatchMode=yes`, an absolute remote binary path, and stdout reserved for JSON-RPC. These are practical requirements, but they come from general knowledge and the search summary, not a primary doc.
- Since screenshots and clips are large, HTTP transport with gzip, or SSH compression, helps. Don't rely on SSE resumability, which was removed.

### Gaps
- No primary Tailscale doc was gathered on exposing an MCP server (for example via tsnet or `tailscale serve`).
- The MCP docs page on remote-server security best practices wasn't fetched.
- Antigravity CLI's remote MCP config format wasn't verified.
