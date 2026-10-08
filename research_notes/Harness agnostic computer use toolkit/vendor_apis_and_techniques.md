# Frontier-vendor computer-use APIs and SOTA accuracy/efficiency techniques (as of 2026-10-07)

Method note: Sources were fetched live on 2026-10-07. Several model names (Claude Fable 5 / Mythos 5 / Opus 5.5, GPT-6 Astra / GPT-6.1 Sol / GPT-5.6, Gemini 3.6 / 3.8 Flash, Qwen3.8) postdate the researcher's background knowledge. Each one appears in at least one primary vendor doc and is corroborated by independent trackers. Page summaries came through a fetch tool, so exact strings should be re-checked against the live pages before they are hard-coded. Items marked **[background, unverified 2026]** come from pre-2026 knowledge and were not re-confirmed on a live page. Items marked **[local observation]** were read directly from tool schemas or skill files installed in this Claude desktop session on 2026-10-07.

---

## Q1. Anthropic: tool versions, action schema, screenshot sizing, coordinates, companion tools, and Claude Code / desktop / Chrome surfaces

### Takeaway
Anthropic replaced the single `computer` tool with a GA **client toolset**, `computer_toolset_20260801`. It has 17 member tools (one tool per action, no `action` field), zoom on by default, native multi-action batching, and no `display_*` params. Screenshots must be pre-resized by the client, because oversized images are rejected rather than downscaled. The model works in absolute pixel coordinates of the screenshot you return, and zoom never changes that frame. The legacy `computer_20251124` / `computer_20250124` beta tools still exist for older models and non-Anthropic clouds.

### Cited Findings
**Versions and model support**
- `computer_toolset_20260801` is GA on the Claude API and Google Cloud and needs no beta header. Declaration: `{"type": "computer_toolset_20260801", "configs": {"zoom": {"enabled": false}}, "cache_control": {"type": "ephemeral"}}`. `configs` sets per-member `enabled` (default true for all 17) and `defer_loading`, and `allowed_callers` accepts only `["direct"]`. The toolset rejects `name`, `display_width_px`, `display_height_px`, `display_number`, and `enable_zoom`, and it cannot be declared alongside `computer_20251124` or any tool named `computer`. — [Anthropic computer use tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- Toolset-supported models: claude-fable-5-1, claude-mythos-5-1, claude-fable-5, claude-mythos-5, claude-opus-5-5, claude-opus-5, claude-sonnet-5-5, claude-sonnet-5, claude-opus-4-8, claude-haiku-5-5. On the Claude API and Google Cloud, Claude 5.5+ models accept **only** the toolset and return an error for `computer_20251124`. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- Earlier versions (beta headers required):
  - `computer_20251124` (`anthropic-beta: computer-use-2025-11-24`): Fable 5.1, Mythos 5.1, Fable 5, Mythos 5, Opus 5, Sonnet 5, Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 4.6, Opus 4.5, plus Opus 5.5 and Sonnet 5.5 on Bedrock.
  - `computer_20250124` (`computer-use-2025-01-24`): Sonnet 4.5 (deprecated), Haiku 4.5, Opus 4.1 / Sonnet 4 / Opus 4 (retired except on some clouds).
  - Bedrock, Claude Platform on AWS, and Microsoft Foundry offer only the beta versions.
  - Legacy tool entry: `{"type":"computer_20251124","name":"computer","display_width_px":1024,"display_height_px":768,"display_number":1}`. Zoom on that version requires `enable_zoom` (default `false`). — [Anthropic computer use docs, "Earlier tool versions" and "Migrate" sections](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- `computer_20241022` no longer appears in the current docs' version table. **[background, unverified 2026]** It shipped with Claude 3.5 Sonnet (new) and exposed `key, type, mouse_move, left_click, left_click_drag, right_click, middle_click, double_click, screenshot, cursor_position`. `computer_20250124` added `scroll` (`scroll_direction`, `scroll_amount`), `triple_click`, `left_mouse_down/up`, `hold_key`, `wait`, and modifier `text` on clicks. `computer_20251124` added `zoom` (`region: [x1,y1,x2,y2]`, gated by `enable_zoom`).

**Action schema (toolset members)**
- Every `tool_use` carries `"toolset_name": "computer"`. Its `name` is the member, and `input` holds only that member's params. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)

| Member | Input |
|---|---|
| `screenshot` | `{}` |
| `zoom` | `region: [x0, y0, x1, y1]` (full-display pixel coords) |
| `left_click`, `right_click`, `middle_click`, `double_click`, `triple_click` | `coordinate` (optional), `text` (optional modifiers: `shift`, `ctrl`, `alt`, `super`, or `+`-joined) |
| `left_click_drag` | `start_coordinate`, `coordinate`, `text` (optional) |
| `mouse_move` | `coordinate` |
| `left_mouse_down`, `left_mouse_up` | `{}` |
| `cursor_position` | `{}`, answered as text, e.g. `X=512, Y=384` |
| `scroll` | `scroll_direction` (up/down/left/right), `scroll_amount`, `coordinate` (optional), `text` (optional) |
| `type` | `text` |
| `key` | `text` (xdotool-style, e.g. `"Return"`, `"ctrl+s"`), `repeat` (1–100, default 1) |
| `hold_key` | `text`, `duration` (s, max 300) |
| `wait` | `duration` (s, max 300) |

  Source for the table: [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- Coordinates are "always in the pixel space of the full-display screenshots you return, with the origin at the top left. Zoom images don't change this." — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- **Batching.** Claude can emit several `tool_use` blocks per turn. Run them in order and stop at the first failure. Return `is_error: true` for the failed block and the exact text `Not executed: an earlier computer action in this turn failed.` for the blocks after it. Leaving any block unanswered gives `invalid_request_error`. Results may contain only `text` and `image` content. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- Migration checklist from `computer_20251124`: drop the beta header, dispatch on `name` + `toolset_name` instead of `input.action`, handle every block in the turn, echo `toolset_name` on results, honor `key.repeat`, and resize screenshots yourself. Zoom is on by default in the toolset, so disable it if you don't implement it. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)

**Screenshot sizing, scaling and token cost**
- Opus 4.7 and later (including every toolset model): up to **2576 px long edge** and **4784 visual tokens** (`⌈w/28⌉ × ⌈h/28⌉`, ≈3.75 MP). Earlier models: **1568 px** long edge, ≈1.15 MP, max 1568 visual tokens. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool); [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Images returned to the computer-use or browser-use **toolsets** are **rejected** (validation error) if they exceed the limits. They are not downscaled. Other images are downscaled with aspect ratio preserved. — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision). The May 2026 best-practices blog (written for `computer_20251124`) instead says oversized images are "silently downscaled" — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude). The difference is consistent with the legacy tool downscaling and the toolset rejecting.
- Downscale table from the vision docs: 1920×1080 → 1456×819 (1560 tokens) on the standard tier and kept at 2691 tokens on the high-res tier. 3840×2160 → 2576×1449 (4784 tokens) on high-res. 1000×1000 = 1296 tokens. — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- If a request holds **>20 images**, every image is limited to **2000 px** per side, and that count includes screenshots nested in `tool_result`. Keep ≤20 images or resize. Hard limits: 8000×8000 px, 10 MB base64 per image on the direct API, 100 images per request (200k-context models) or 600 (others), 32 MB request. — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- The reference scaling code computes `scale = min(1, 1568/long_edge, sqrt(1_150_000/(w*h)))` and maps clicks back with `x/scale`. That snippet uses the legacy tier constants. On Retina (DPR 2), either downscale by 2× or halve coordinates. Suggested resolutions: **1024×768 or 1280×720** for general desktop, **1280×800 or 1366×768** for web apps, and avoid anything above 1920×1080. Each screenshot costs about 1,000–1,800 input tokens. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- Toolset definition overhead is about **4,500 input tokens** (≈4,520–4,590 depending on model), covering member definitions and the tool-use system prompt. Disabling `zoom` saves about 410 tokens. The legacy tools cost 466–499 system-prompt tokens plus about 735 tokens per tool definition. — [Anthropic computer use docs, Pricing](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)

**Prompting guidance (official)**
- Docs tips: give simple, explicit tasks; screenshot after each step to verify; prefer keyboard shortcuts for dropdowns and scrollbars; put instruction text *before* the screenshot image to improve click accuracy; ask Claude to zoom on small text; include example screenshots and tool calls for repeatable tasks. Use `left_mouse_down/up` plus modifiers for spreadsheet cell selection, and Page Down where scroll doesn't take effect. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool). The general vision docs recommend the opposite order (image before text) for non-computer-use prompts — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision).
- "Best practices for computer and browser use with Claude" (May 13, 2026):
  - Start at 1280×720 (about 80% of the 4.6 pixel budget) and use 1080p for Opus 4.7. Avoid native 1080p+ on 4.6 models and avoid inputs below 960×540.
  - A 16 px checkbox on a 3840×2160 display becomes about 5 px at 1280×720.
  - **Tiling, coordinate-grid overlays, and resize-algorithm choice (LANCZOS, sips, etc.) were tested and did not help.**
  - Enable zoom for dense UIs with small targets.
  - Effort: Opus 4.7 `high` gets near-top success with about half the output tokens of `max`, and Opus 4.7 `low` matches Sonnet 4.6 `max` at about 1/10 the tokens.
  - Context: a rolling buffer of keep_n=3 recent screenshots, pruned in batches every 25 turns to protect the prompt cache. Cache breakpoints: 1 on the prefix and up to 3 on recent tool results. Compaction at about 150k tokens.
  - Sonnet 4.6 clicks more precisely and is more robust to heavy downscaling than Opus 4.6. Opus 4.7 closes most of that gap.
  - Experimental `computer_batch` / `browser_batch`: use for independent actions such as form fields, and avoid for exploration or error recovery.
  — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)

**Companion tools**
- The quick start declares `{"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}` and `{"type": "bash_20250124", "name": "bash"}`. Only the computer tool needs a beta header (legacy path). — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)

**Browser toolset (sibling API tool)**
- `browser_toolset_20260801` has 31 members, 27 enabled by default. `javascript_exec`, `file_upload`, `read_console`, and `read_network` are off by default. Members:
  - Navigation and capture: `navigate` (url, or `back` / `forward` / `reload`), `screenshot`, `zoom` (`region`)
  - Pointer: `left/right/middle/double/triple_click`, `hover`, `left_click_drag`, `left_mouse_down/up`, `mouse_move`, `scroll` (`scroll_amount` 1–10, default 3), `scroll_to`
  - Keyboard and timing: `type`, `key` (`repeat`), `hold_key`, `wait` (0–30 s)
  - Page reading: `read_page` (`filter`: interactive/all, `depth`, `ref`), `find` (`query`), `get_page_text`
  - Forms and tabs: `form_input`, `new_tab`, `list_tabs`, `switch_tab`, `close_tab`
  - Pointer members take `target: {"type":"ref","ref":"ref_2"}` or `{"type":"coordinate","x":640,"y":380}`.
  - "Prefer refs where the page has a usable accessibility tree. Read the tree before taking a screenshot when possible, since a scoped tree read often costs fewer input tokens."
  - A stale ref returns an error that tells the model to re-read the page. Clients should attach a fresh screenshot or page read to the last result in a batch. A `browser_state` block reports tabs.
  — [Anthropic browser use tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/browser-use-tool)

**Claude Code CLI built-in `computer-use` MCP server**
- Built-in MCP server named `computer-use`, off by default, enabled per project via `/mcp`.
  - Requirements: macOS research preview, Pro/Max plans (not Team/Enterprise), Claude Code ≥ v2.1.85, interactive sessions only (not `-p`), and claude.ai auth (not Bedrock/Vertex/Foundry).
  - Needs macOS Accessibility and Screen Recording permissions.
  — [Claude Code docs: computer use](https://code.claude.com/docs/en/computer-use); version requirement also in [search summary of same docs](https://code.claude.com/docs/en/computer-use.md)
- Tool-selection policy: an MCP for the service first, then Bash, then Claude in Chrome for browser work, and computer use only when nothing else reaches the target (native apps, simulators, tools without an API). — [Claude Code docs](https://code.claude.com/docs/en/computer-use)
- Behaviors:
  - Per-session app approval, with prompts that show requested apps, extra permissions (clipboard), and how many apps will be hidden.
  - Other apps are hidden while Claude works and restored at turn end. The terminal stays visible but is excluded from screenshots.
  - A machine-wide lock allows one session at a time.
  - Esc aborts from anywhere, and the keypress is consumed so injected content can't use it to dismiss dialogs.
  - "Claude Code downscales every screenshot before sending it": a 16-inch MBP at 3456×2234 becomes about 1372×887. The target size cannot be changed, and the docs advise enlarging app text instead.
  — [Claude Code docs](https://code.claude.com/docs/en/computer-use)
- Tool names: `mcp__computer-use__*` in the desktop app (e.g. `request_access`, `screenshot`, `list_granted_applications`, `open_application`, `left_click`, `type`, `right_click`), and `mcp__remote-devices__computer_*` for cloud sessions linked to a computer (e.g. `computer_resolve_access` then `computer_request_access`, `computer_screenshot`). Access is requested once per set of apps before any action. — **[local observation]** Anthropic `computer-use` Agent Skill, SKILL.md in the Claude desktop skills plugin directory (read 2026-10-07)

**Claude in Chrome and the Claude desktop browser pane (MCP tool schemas)**
- `computer` tool:
  - Actions: `left_click, right_click, double_click, triple_click, type, screenshot, wait, scroll, key, left_click_drag, zoom, scroll_to, hover`.
  - Params: `coordinate`, `start_coordinate`, `ref` (alternative to coordinates), `region` [x0,y0,x1,y1] for zoom, `modifiers` ("ctrl+shift", "cmd", ...), `scroll_direction`, `scroll_amount` (1–10, default 3), `duration` (max 10 s), `repeat` (1–100), `text`, and `action_summary` (a required-by-description human-readable effect string on mutating actions).
  - `scale` (0.1–1) for screenshot/zoom: "0.5 returns an image at half the width and height (~quarter of the tokens). Coordinates are ALWAYS in the full-resolution coordinate frame… never in the scaled image's own pixels."
  - Companion tools: `read_page` (accessibility tree with `ref_N`, `filter: interactive|all`, `depth`, `max_chars` default 50000), `find` (natural-language query, returns up to 20 refs), `form_input`, `get_page_text`, `javascript_tool`, `navigate`, `browser_batch` (sequential, stops on first error, "coordinates you write in THIS batch refer to the screenshot taken BEFORE this call"), console/network readers, and `gif_creator`.
  — **[local observation]** `mcp__claude-in-chrome__*` and `mcp__Claude_Browser__*` tool schemas loaded in this session, 2026-10-07

### Inferences
- The newest Anthropic design has four properties a harness-agnostic toolkit can copy: one tool per action, a shared absolute-pixel frame tied to the last full screenshot, zoom as a first-class read-only action that returns a higher-detail crop without changing coordinates, and ordered batching with a halt-on-first-failure contract. The Claude in Chrome `scale` parameter adds a fifth: a cheaper image in the same coordinate frame.
- Visual-token arithmetic (28 px patches, from the documented formula):
  - 1024×768 ≈ 1,036 tokens; 1280×720 ≈ 1,196; 1280×800 ≈ 1,334; 1366×768 ≈ 1,372; 1440×900 ≈ 1,716; 1920×1080 ≈ 2,691 (high-res tier only); 2576×1449 = 4,784.
  - Claude Code's 1372×887 works out to exactly 49×32 = 1,568 visual tokens, the standard-tier cap. Claude Code's own pipeline therefore appears to size screenshots to the legacy 1568-token budget even for high-res-capable models (inference from arithmetic).
- An MCP server is a custom tool, so it does **not** get Anthropic's server-side screenshot prompt-injection classifiers. The best-practices blog says those run only on the official tool (see Q7).

### Gaps
- The exact JSON schema of the Claude Code / desktop `computer-use` MCP tools (full action list, whether they include `zoom`, multi-monitor params) is not published. Only names seen in the skill file are confirmed.
- No published benchmark numbers on how much `zoom` improves Claude's accuracy. The blog presents results as charts.

---

## Q2. OpenAI: computer tool schema, models, Codex, ChatGPT agent/Atlas

### Takeaway
OpenAI's current Responses API tool is a bare `{"type":"computer"}`. The model returns `computer_call` items whose **`actions` array** batches ordered actions: `click`, `double_click`, `drag`, `move`, `scroll`, `keypress`, `type`, `wait`, `screenshot`. Coordinates are absolute `x`/`y` pixels in the screenshot, which should be sent with `detail: "original"`. The 2026 OpenAI docs now *recommend code execution (PyAutoGUI/Playwright via a function tool) over the computer tool* for GPT-6 Astra. GPT-5.4 (Mar 2026) was the first mainline model with native computer use. The Codex desktop app gained background macOS computer use in Apr 2026.

### Cited Findings
- Current tool definition: `tools: [{ type: "computer" }]`, with no display size or environment fields. Example response:
  `{"type":"computer_call","call_id":"call_002","actions":[{"type":"click","button":"left","x":405,"y":157},{"type":"type","text":"penguin"}],"status":"completed"}`. Actions run in order, and the first call may contain only `screenshot`. Output:
  `{type:"computer_call_output", call_id, output:{type:"computer_screenshot", image_url:"data:image/png;base64,...", detail:"original"}}`, chained with `previous_response_id`. — [OpenAI computer use guide](https://developers.openai.com/api/docs/guides/tools-computer-use)
- Example models are `gpt-6.1-sol` for the computer tool and `gpt-6-astra` for code execution: "For GPT-6 Astra, we recommend code execution. The `computer` tool remains supported as an alternative." Code-execution examples are a function tool `exec_py` (PyAutoGUI) or `exec_js` (Playwright, `reasoning.effort: "low"`, `strict: true`, loop capped at 20 responses, 1440×900 viewport). — [OpenAI computer use guide (.md)](https://developers.openai.com/api/docs/guides/tools-computer-use.md)
- Action field details from SDK type references:
  - `click.button` ∈ {left, right, wheel, back, forward} + `x, y`
  - `scroll` has `x, y` plus horizontal and vertical offsets (`scroll_x`, `scroll_y`)
  - `keypress.keys` is a list; `drag.path` is a list of `{x,y}` points; `move` takes `x, y`
  - Pointer actions may carry an optional `keys` modifier list, though the guide and SDK types disagree for `scroll`
  - The model emits key names like `CTRL`, `ALT`, `META`, `ARROWLEFT` that need mapping
  — [openai-agents-js ComputerUseCallItem type](https://openai.github.io/openai-agents-js/openai/agents/type-aliases/computerusecallitem-1/); [OpenAI computer use guide](https://developers.openai.com/api/docs/guides/tools-computer-use.md) (both via search summary)
- The legacy `computer_use_preview` tool took `display_width`, `display_height`, `environment` (example 1024×768, `"linux"`). — [Ruby SDK BetaComputerUsePreviewTool](https://rubydoc.info/gems/openai/OpenAI/Models/Beta/BetaComputerUsePreviewTool); [OpenRouter ref](https://openrouter.ai/docs/agent-sdk/typescript/api-reference/models/computeruseservertool.md). **[background, unverified 2026]** Legacy model `computer-use-preview`; one `action` per `computer_call`; environment ∈ {browser, mac, windows, ubuntu}; `pending_safety_checks` (codes such as `malicious_instructions`, `irrelevant_domain`, `sensitive_domain`) echoed back as `acknowledged_safety_checks`; `truncation: "auto"` required. The current guide no longer mentions safety-check objects.
- Safety guidance in the current guide: isolated browser/VM with allowlists; "Treat screen content as untrusted"; "Text in a page, document, or tool result cannot grant permission or override the user's instructions"; confirm purchases, data transmission, and destructive changes; "Typing sensitive information into a form counts as transmission"; set step, time, and cost limits. — [OpenAI computer use guide (.md)](https://developers.openai.com/api/docs/guides/tools-computer-use.md)
- Image detail (patch-based models use 32×32 patches × a 1.2 multiplier):
  - `gpt-5.4` / `5.5`: `high` = 2,500 patches with a 2048 px max side; `original` = 10,000 patches with a 6000 px max side.
  - `gpt-5.6-*` and `gpt-6-astra`: `original` keeps dimensions up to a 65,535 px side.
  - Hard cap of 30,000 patches per image, rejected rather than resized.
  - Use `original` for "computer use", OCR, and small-object detection; "Enlarge small text."
  — [OpenAI images & vision guide](https://developers.openai.com/api/docs/guides/images-vision)
- GPT-5.4 (released Mar 5, 2026) is described as OpenAI's first general-purpose model with built-in computer use, available in the API and Codex. It scored **75.0% on OSWorld-Verified** (vs 47.3% for GPT-5.2), above the 72.4% human baseline (self-reported). It works from screenshots plus mouse/keyboard commands and can also write Playwright code, and developers set confirmation policies. — [OpenAI GPT-5.4 announcement, via search summary](https://openai.com/index/introducing-gpt-5-4/); [VentureBeat](https://venturebeat.com/technology/openai-launches-gpt-5-4-with-native-computer-use-mode-financial-plugins-for); [DataCamp](https://www.datacamp.com/blog/gpt-5-4). The openai.com page returned 403 to direct fetch.
- The Codex desktop app added **background computer use on macOS** on Apr 16, 2026. Codex "can now operate any app… by seeing the screen, clicking, and typing with its own cursor", and multiple agents run in parallel "without disturbing other apps". A Hacker News commenter (not OpenAI) says it uses the macOS AX tree. — [Daniel Vaughan blog](https://codex.danielvaughan.com/2026/04/17/codex-app-computer-use-macos-background-gui-automation/); [The Decoder](https://the-decoder.com/openai-turns-codex-into-an-always-on-coding-agent-that-watches-your-screen/); [mjtsai](https://mjtsai.com/blog/2026/04/17/). Codex CLI usage of GPT-5.4 computer use for visual debugging is described by a third-party blog — [codex.danielvaughan.com](https://codex.danielvaughan.com/2026/03/31/gpt54-computer-use-tool-search-codex-cli/)
- OSWorld-Verified tracker figures: GPT-5.5 78.7%, GPT-5.4 75%, GPT-5.4 mini 72.1%, GPT-5.3 Codex 64.7%. No GPT-6.x row appears there. On OSWorld 2.0, GPT-6 Astra scored 72.6% partial (offline subset) and GPT-6.1 Sol 70.5% partial, both vendor/tracker-reported. — [BenchLM OSWorld-Verified](https://benchlm.ai/benchmarks/osworld-verified); [Presenc OSWorld 2026](https://presenc.ai/research/osworld-computer-use-leaderboard-2026)

### Inferences
- OpenAI and Anthropic converge on absolute screenshot pixels and ordered batches. They differ in shape: OpenAI puts one call with an `actions[]` array, Anthropic emits several `tool_use` blocks. A toolkit can expose one `batch` / `actions[]` entry point that maps to either.
- OpenAI steering frontier models toward *code execution* (PyAutoGUI/Playwright) means a CLI-plus-skills design that lets the agent script the GUI matches where OpenAI is heading, alongside structured click tools.

### Gaps
- Could not fetch the current OpenAI migration guide verbatim, so the exact current `scroll`, `keypress`, and `drag` field names are confirmed only via SDK types.
- ChatGPT agent and the Atlas browser agent mode were not researched live. **[background, unverified 2026]** ChatGPT agent (Jul 2025) merged Operator and deep research. Atlas (Oct 2025) is a Chromium browser with an agent mode. Neither exposes a public tool schema.
- Whether Codex CLI (as opposed to the Codex desktop app) ships a native computer-use tool in Oct 2026 is unconfirmed.

---

## Q3. Google: Gemini computer use

### Takeaway
Gemini computer use moved from the standalone `gemini-2.5-computer-use-preview-10-2025` model into the mainline Flash models as a built-in tool, starting with Gemini 3.5 Flash on Jun 24, 2026. Current docs name `gemini-3.8-flash` as recommended. Environments are `browser`, `desktop`, and `mobile`. Coordinates use a **normalized 0–999 (1000×1000) grid** mapped by the client. The schema is broader than Anthropic's: hotkeys, key up/down, navigate, an `intent` field on every action, and per-action `safety_decision`.

### Cited Findings
- Models: `gemini-3.8-flash` (recommended), `gemini-3.7-flash`, `gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-3-flash-preview`. — [Gemini API computer use docs](https://ai.google.dev/gemini-api/docs/computer-use)
- Environments `"browser"`, `"mobile"`, `"desktop"` (`ENVIRONMENT_BROWSER`, `ENVIRONMENT_MOBILE`, `ENVIRONMENT_DESKTOP`). — [Gemini API computer use docs](https://ai.google.dev/gemini-api/docs/computer-use)
- Actions:
  - Browser and desktop: `click`, `double_click`, `triple_click`, `middle_click`, `right_click`, `mouse_down`, `mouse_up`, `move`, `type`, `drag_and_drop`, `wait`, `press_key`, `key_down`, `key_up`, `hotkey`, `take_screenshot`, `scroll`, `go_back`, `navigate`, `go_forward`.
  - Mobile: `open_app`, `click`, `list_apps`, `wait`, `go_back`, `type`, `drag_and_drop`, `long_press`, `press_key`, `take_screenshot`.
  - Params: `x`, `y` int 0–999; `type` has `text` and `press_enter` (default false); `drag_and_drop` has `start_x`, `start_y`, `end_x`, `end_y`; `wait.seconds` (default 1); `long_press.seconds` (default 2); `scroll` has `direction` and `magnitude_in_pixels` (default 300); `hotkey.keys` (list); `press_key` / `key_down` / `key_up` take `key`; `navigate.url`; `open_app.app_name`; **every action includes `intent`**.
  - Conversion: `x / 1000 * screen_width`. The example screen is 1440×900.
  — [Gemini API computer use docs](https://ai.google.dev/gemini-api/docs/computer-use)
- Customization: `excluded_predefined_functions` (e.g. `["click"]`) and custom functions such as `yield_to_user(reason)`. After each action batch, return a PNG screenshot in `function_result` plus the current URL, with one `function_result` per parallel call. — [Gemini API computer use docs](https://ai.google.dev/gemini-api/docs/computer-use)
- **[background, unverified 2026]** The Gemini 2.5 Computer Use preview (Oct 2025) was browser-focused, with actions `open_web_browser`, `click_at`, `type_text_at`, `scroll_document`, `scroll_at`, `key_combination`, `hover_at`, `drag_and_drop`, `navigate`, `go_back`, `go_forward`, `search`, `wait_5_seconds`, on the same 0–999 grid. These names are absent from the current docs page.
- Gemini 3.5 Flash computer use (Jun 24, 2026) is a "built-in tool" rather than a separate model, works across browser, mobile, and desktop, ships with a Browserbase demo and a GitHub reference impl (`google-gemini/computer-use-preview`), and is in public preview. — [Google blog](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-computer-use-gemini-3-5-flash/)
- OSWorld-Verified, self-reported: Gemini 3.5 Flash 78.4 (vs Gemini 3 Flash 65.1). Gemini 3.6 Flash (Jul 21, 2026) 83.0%. 3.5 Flash-Lite also gained the tool (74% on a tracker). — [search summary of Google/Decoder coverage](https://the-decoder.com/google-bakes-computer-control-directly-into-gemini-3-5-flash-letting-the-model-see-and-operate-your-screen/); [Google blog 3.6 Flash](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-6-flash-3-5-flash-lite-3-5-flash-cyber/); [BenchLM](https://benchlm.ai/benchmarks/osworld-verified)
- Image budget: Gemini 3 `media_resolution` costs low=280, medium=560, high=1120 (default), `ultra_high`=2240 tokens per image. `ultra_high` is "required for specific use cases such as computer use." — [Gemini media resolution docs](https://ai.google.dev/gemini-api/docs/media-resolution)

### Inferences
- Gemini's normalized grid makes coordinates resolution-independent but less precise: one grid unit is about 1.4 px horizontally on a 1440 px screen and about 3.8 px on a 3840 px screen. A toolkit should support both an absolute-pixel and a normalized-grid convention, configured per model, through a single coordinate-transform layer.
- A per-action `intent` string, like Claude in Chrome's `action_summary`, is a cheap pattern for audit logs and for safety classifiers that check intent against the action.

### Gaps
- No Gemini zoom or crop action is documented. The model is not stated to support region zoom.
- The docs page gives no recommended screen size beyond the 1440×900 example.

---

## Q4. Other published CUA schemas (Qwen3-VL, UI-TARS, Fara, etc.) and the common-denominator action set

### Takeaway
Open models copy Anthropic's xdotool-style vocabulary: Qwen's `computer_use` tool is nearly identical to Anthropic's 2025 action list, plus `terminate` and `answer`. UI-TARS uses a compact function-call text format. The common denominator is: screenshot, click variants, move/hover, drag, scroll, type, key/hotkey, wait, and a terminal action. Zoom appears only in the Anthropic family.

### Cited Findings
- **Qwen3-VL `computer_use`** (cookbook `agent_function_call.py`):
  - Description: "Use a mouse and keyboard to interact with a computer, and take screenshots." "The screen's resolution is {display_width_px}x{display_height_px}."
  - `action` enum: `key, type, mouse_move, left_click, left_click_drag, right_click, middle_click, double_click, triple_click, scroll, hscroll, wait, terminate, answer`.
  - Params: `keys` (array), `text`, `coordinate`, `pixels` (scroll amount), `time`, `status` ∈ {success, failure}.
  - **`mobile_use`**: `key, click, long_press, swipe, type, system_button, open, wait, terminate`, with `coordinate2` for swipe and `button` ∈ {Back, Home, Menu, Enter}.
  - The code describes coordinates as absolute pixels.
  — [Qwen3-VL cookbook source](https://raw.githubusercontent.com/QwenLM/Qwen3-VL/main/cookbooks/utils/agent_function_call.py). A DeepWiki summary instead says Qwen3-VL outputs 0–999 normalized coordinates — [DeepWiki Qwen3-VL](https://deepwiki.com/QwenLM/Qwen3-VL/5.3-mobile-agent-and-function-calling) (auto-generated; conflicts with the code).
- **UI-TARS (Doubao prompts)**:
  - Output format: `Thought: …` then `Action: …`.
  - Actions: `click(point='<point>x1 y1</point>')`, `left_double(...)`, `right_single(...)`, `drag(start_point=..., end_point=...)`, `hotkey(key='ctrl c')` (space-separated lowercase), `type(content='xxx')` (end with `\n` to submit), `scroll(point=..., direction='down|up|right|left')`, `wait()` ("Sleep for 5s and take a screenshot"), `finished(content='xxx')`.
  - Mobile adds `long_press`, `open_app`, `press_home`, `press_back`.
  — [UI-TARS prompt.py](https://raw.githubusercontent.com/bytedance/UI-TARS/main/codes/ui_tars/prompt.py)
- **Microsoft Fara-7B** (web CUA) works from screenshots only: no accessibility tree, HTML, or Set-of-Marks. It predicts click/scroll/type coordinates directly. Results: WebVoyager 73.5% (vs computer-use-preview 70.9%, UI-TARS-1.5-7B 66.4%). WebTailBench 38.4% vs a GPT-4o SoM agent at 30.0%. About 16 steps per task vs about 41 for UI-TARS-1.5-7B. — [Microsoft Research blog](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/); [Azure AI Foundry Labs](https://labs.ai.azure.com/?p=951) (search summary; a DEV review lists a stronger GPT-4o-SoM row, so the SoM comparison depends on configuration)
- **Alibaba GUI-Plus** (Model Studio) uses a `mobile_use` function and a `terminate` action to finish. — [Alibaba Model Studio GUI automation](https://help.aliyun.com/en/model-studio/gui-automation) (via search summary)
- Open and specialized models now rank high on OSWorld-Verified: Qwen3.8 Max 86.1%, Qwen3.8-27B 84.3%, H Company Holo3-35B-A3B 82.6%, Xiaomi MiMo-V2.6-Pro 82%, Tencent UI-Mate-27B 77%. — [BenchLM OSWorld-Verified](https://benchlm.ai/benchmarks/osworld-verified)

### Inferences
- **Common-denominator action set** across Anthropic, OpenAI, Gemini, Qwen, and UI-TARS:
  - Pointer: `screenshot`, `click(x,y, button, modifiers)` covering left/right/middle/double/triple, `move/hover`, `drag(start,end)` (OpenAI accepts a multi-point `path`), `mouse_down/up`.
  - Input: `scroll(x,y, direction, amount)` (OpenAI uses `scroll_x/scroll_y` deltas; Gemini uses pixels), `type(text)` (Gemini adds `press_enter`), `key/hotkey(keys, repeat)`, `hold_key`, `wait(seconds)`.
  - Control: an explicit `done` / `terminate` / `answer` (open models) and a `yield_to_user` / `call_user` escape hatch (Gemini custom function).
  - Browser-only: `navigate/back/forward`.
  - Anthropic-only: `zoom(region)`. Anthropic plus Chrome: `cursor_position` and `scroll_to(ref)`.
- Coordinate conventions differ: absolute screenshot pixels (Anthropic, OpenAI, Qwen code), a 0–999 normalized grid (Gemini, and possibly Qwen3-VL natively), and `<point>` text (UI-TARS). A harness-agnostic server should accept `{x,y}` in a declared frame (`"screenshot_px"` or `"norm1000"`) and always report the frame with each screenshot.

### Gaps
- Amazon Nova Act and Mistral computer-use schemas were not researched (no time budget). Nova Act is **[background, unverified 2026]** an SDK with natural-language `act()` steps over Playwright, not a public low-level action schema.
- Exact Fara-7B action names (github.com/microsoft/fara) were not verified.

---

## Q5. Image-resolution reality: per-vendor limits, token cost per screenshot, small-target failure, and zoom/crop strategies that work

### Takeaway
Every vendor downsamples or caps images, and small targets on high-DPI screens are the main grounding failure mode. ScreenSpot-Pro was built around that problem. Two remedies have strong evidence: (a) send screenshots at the model's native budget (no hidden extra downscale), and (b) **iterative zoom/crop**. Zoom gives up to +18 points on ScreenSpot-Pro without any training, and Anthropic ships zoom as a native action. Grid overlays and tiling did *not* help Claude in Anthropic's tests. Frontier models have since closed much of the grounding gap: Opus 4.8 scores about 88% on ScreenSpot-Pro.

### Cited Findings
**Per-vendor limits**
- Anthropic: 1568 px / 1568 visual tokens on the standard tier; 2576 px / 4784 tokens on the high-res tier (Opus 4.7+). Formula `⌈w/28⌉×⌈h/28⌉`. Oversized toolset images are rejected. The per-side limit is 2000 px when a request holds more than 20 images. — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- OpenAI: 32 px patches × 1.2. `high` = 2,500 patches (≤3,000 tokens). `original` = 10,000 patches with a 6000 px side on gpt-5.4/5.5, and native dimensions on gpt-5.6 and gpt-6-astra. 30,000-patch hard cap. — [OpenAI images & vision](https://developers.openai.com/api/docs/guides/images-vision)
- Gemini 3: flat 280 / 560 / 1120 / 2240 tokens by `media_resolution`, with `ultra_high` required for computer use. — [Gemini media resolution](https://ai.google.dev/gemini-api/docs/media-resolution)
- Claude Code downscales Retina 3456×2234 captures to about 1372×887, with no user override, and says to enlarge in-app text if it is too small. — [Claude Code docs](https://code.claude.com/docs/en/computer-use)

**Evidence that small things get lost**
- A 16 px checkbox on a 4K display shrinks to about 5 px at 1280×720. Anthropic recommends against inputs below 960×540. — [Claude blog best practices](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)
- OSWorld (2024): for screenshot-only agents, higher resolution correlated with better performance. With SoM, downsampling to 0.4× (768×432) helped, but 0.2× hurt noticeably. — [OSWorld paper](https://arxiv.org/html/2404.07972)
- ZoomClick failure analysis: ScreenSpot-Pro has "densely packed fine-grained elements". Errors compound from the first prediction. Crops that are too tight make UI-specialized models lose context and pick distractors (UI-Venus-7B fell from 35.1% to 29.7% on hard-mislead between depths 1 and 4). Relative instructions ("first", "oldest") cause look-alike errors. — [ZoomClick arXiv 2512.05941](https://arxiv.org/html/2512.05941v1)

**Zoom strategies with numbers**
- **ZoomClick** (training-free, Dec 2025):
  - Pre-zoom: predict on the full image and on 4 patches in a 2×2 grid; if the nearest patch prediction is within 50 px of the global one, start from it.
  - Then iteratively shrink the viewport by ρ=0.5 around the prediction, depth T=3, with a minimum crop of 768 px.
  - ScreenSpot-Pro: Qwen3-VL-32B 54.0 → **72.1** (+18.1); UI-Venus-7B 50.3 → 65.7; UI-Venus-72B 61.4 → **73.1** (claimed SOTA at the time; GTA1-32B was 63.6).
  - Distance-based pre-zoom beat VLM-judged pre-zoom (71.3 vs 61.9).
  - Comparison on Qwen2.5-VL-7B: GUI-Cursor 56.5, ReGUIDE 44.4, ZoomClick 44.0, GUI-Spotlight 38.7, RegionFocus 32.1.
  — [ZoomClick paper](https://arxiv.org/html/2512.05941v1); code at [Princeton-AI2-Lab/ZoomClick](https://arxiv.org/pdf/2512.05941)
- Follow-ups: a Zoom-Consistency confidence signal (Apr 2026) and UI-Zoomer, which treats when and how much to zoom as an uncertainty problem. — [alphaxiv 2604.15376](https://www.alphaxiv.org/abs/2604.15376.md); [emergentmind 2604.14113](https://www.emergentmind.com/papers/2604.14113) (titles from the search summary only)
- Anthropic: "Enable zoom for dense UIs with small targets". The toolset turns zoom on by default. A zoom returns a region crop while coordinates stay in the full-screenshot frame. — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude); [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- Agent S3's judge pipeline adds "a marker and a zoomed crop" for pointer actions when describing each step, i.e. it zooms for verification, not only for grounding. — [Agent S3 paper v2](https://arxiv.org/html/2510.02250v2)
- **Negative results**: tiling, coordinate-grid overlays, and resampling-algorithm choice gave no benefit for Claude. — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)

**ScreenSpot-Pro state (aggregators)**
- Opus 4.8 87.9%, GPT-5.4 85.4%, Gemini 3.1 Pro 84.4% (BenchLM, Jul 29, 2026). AnotherWrapper (Sep 10, 2026) lists Opus 4.8 87.9%, GPT-5.2 86.3%, Qwen3.8 Max 84.5%. Mythos Preview scored 93% *with tools*, 79.3% without. In Mar 2026 the leader was Gemini 3 Pro at 72.7%. BenchLM warns that cropping, visual search, and Python tools inflate pipeline scores. — [BenchLM ScreenSpot-Pro](https://benchlm.ai/benchmarks/screenspot-pro); [AnotherWrapper](https://anotherwrapper.com/tools/llm-pricing/evals/screenspot-pro); [BenchmarkList](https://benchmarklist.com/benchmarks/screenspot_pro/)

### Inferences
- Token cost per screenshot, from the documented formulas:
  - 1280×800: Claude ≈ 1,334 tokens; OpenAI `original` ≈ 1,200; Gemini `ultra_high` = 2,240.
  - 1920×1080: Claude high-res ≈ 2,691 (standard tier forced to 1456×819 ≈ 1,560); OpenAI ≈ 2,448.
  - A zoom crop sized at or under the budget costs the same as a full screenshot, so zoom is cheap insurance only when used selectively.
- Design pattern supported by the evidence:
  - Default full-screen screenshots fit to the model's budget (about 1.15 MP for older or unknown models; up to 3.75 MP / 2576 px for Claude 4.7+; `original` for OpenAI; `ultra_high` for Gemini).
  - Provide `zoom(region)` that returns a native-resolution crop upscaled to the budget, with coordinates staying in the full-frame space.
  - Optionally provide a cheaper `scale` for change detection.
  - A ZoomClick-style "refine" helper (crop → re-predict → map back, depth ≤3, minimum crop about 768 px) could be offered as a tool for weaker models, but should be optional for frontier models scoring above 85% on ScreenSpot-Pro.
- Because grid overlays did not help Claude, overlays should be optional, not default.

### Gaps
- No vendor publishes the accuracy uplift of its own zoom action on OSWorld or ScreenSpot-Pro.
- ScreenSpot-Pro target-size statistics (e.g. the share of screen area per target) were not retrieved.

---

## Q6. Technique evidence: SoM, a11y+vision hybrids, OCR, planner+grounder, UI-stability waits, batching, history pruning, cursor overlay, best-of-N/judges, and OSWorld-Verified SOTA

### Takeaway
OSWorld-Verified (369 tasks, 100-step limit) is effectively saturated relative to humans:
- The official board's top entry is **Intelligence-Indeed Agent at 90.19%**, followed by Claude Fable 5 at 85.96%. The human baseline is **72.36%**.
- Single frontier models run with a plain screenshot+action loop now score 83–86%.
- OSWorld 2.0 (long-horizon, 108 tasks) is the new frontier, with best binary completion around 44–49%.

Techniques with the most evidence in 2026:
- Structured page/a11y refs where available (Anthropic's browser toolset says to prefer them).
- Zoom for small targets.
- Ordered action batching.
- Screenshot history pruning (keep about 3) with cache-aware batching.
- Delegation to a coding agent, and multi-rollout best-of-N with a narrative judge (Agent S3: +7–10 points).
- Separate grounding models and SoM overlays matter mostly for weaker or open models; frontier models ground natively at 85–88% on ScreenSpot-Pro.

### Cited Findings
**OSWorld-Verified standings (Oct 2026)**
- Official board as compiled Oct 1, 2026 (all 100-step): 1) Intelligence-Indeed Agent 90.19% (2026-07-25); 2) Claude Fable 5 85.96%; 3) Pointer Agent w/ Opus 4.7 83.64%; 4) Claude Opus 5 83.39%; 5) Coasty CUA v1 82.81%. Human 72.36%. Architectures of the top entries are not described. — [Presenc compilation](https://presenc.ai/research/osworld-computer-use-leaderboard-2026) (third-party; the official site os-world.github.io → osworld-v1.xlang.ai loads its table via JS and could not be read)
- Model-level tracker (updated Oct 7, 2026): Qwen3.8 Max 86.1; Claude Fable 5 85; Claude Mythos 5 85; Qwen3.8-27B 84.3; Claude Opus 4.8 83.4; Gemini 3.6 Flash 83; Holo3-35B-A3B 82.6; MiMo-V2.6-Pro 82; Claude Sonnet 5 81.2; GPT-5.5 78.7; Gemini 3.5 Flash 78.4; Claude Opus 4.7 78; GPT-5.4 75; Claude Opus 4.6 72.7; Sonnet 4.6 72.1; Opus 4.5 66.3; Sonnet 4.5 61.4; GPT-5.2 47.3. — [BenchLM OSWorld-Verified](https://benchlm.ai/benchmarks/osworld-verified). Pointer independently reported 83.6% (Opus 4.7) and 81.5% (Sonnet 4.6) — [Pointer blog](https://www.pointer.ai/blog/sota) (via search summary). Codesota still shows Agent S3 at 63.5% as the leader, which is stale — [Codesota](https://www.codesota.com/benchmark/osworld).
- Original OSWorld human baseline: 72.36% for "individuals unfamiliar with the software". — [OSWorld paper](https://arxiv.org/html/2404.07972)
- **OSWorld 2.0**:
  - Scope: 108 long-horizon workflows on 31 self-hosted sites, a median of about 1.6 human-hours per task, about 318 tool calls per task (vs about 30 in v1), and an average of 27.25 checkpoints.
  - Paper results: Claude Opus 4.8 (max thinking, **batched tool calls**) 20.6% binary / 54.8% partial at about 244K output tokens; Opus 4.7 18.2%; GPT-5.5 about 14% at about 39K output tokens ("most token-efficient but plateaus"). Every model scores 0% on tasks longer than 163 minutes.
  — [OSWorld 2.0 site](https://osworld-v2.xlang.ai/)
  - Later v2.1: Claude Opus 5.5 81.8% partial / 48.7% binary (vendor); Claude Opus 5 (max) 77.67% / 44.33% (official board). — [Presenc](https://presenc.ai/research/osworld-computer-use-leaderboard-2026)

**Accessibility tree, SoM, and hybrids**
- OSWorld 2024 baselines: GPT-4 with the a11y tree alone scored 12.24%, against 5.26% for GPT-4V with a screenshot alone. Screenshot plus a11y gave 12.17%, and SoM gave 11.77% with GPT-4V, but SoM fell to 4.59% with GPT-4o.
  - The authors: "A11y tree and SoM's effectiveness varies by models." With GPT-4V, SoM declined versus screenshot plus a11y, likely because high-res OS screens carry many elements and the overlays add noise.
  - More *text* (a11y) history helped SoM, but more *screenshot* history did not help screenshot-only agents.
  — [OSWorld paper](https://arxiv.org/html/2404.07972)
- In Anthropic's browser toolset docs, refs from `read_page` / `find` "survive layout shifts", and the docs prefer them where an a11y tree exists. A scoped tree read "often costs fewer input tokens" than a screenshot. Coordinates are reserved for canvas, video, remote desktops, and cross-origin iframes. — [Anthropic browser use tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/browser-use-tool)
- Claude's browser tools fall back to JavaScript execution, keyboard navigation, or DOM manipulation when clicks fail, e.g. for system dropdowns that don't render in the viewport screenshot. — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)
- UFO2 (Microsoft, Windows): hybrid control detection (UIA a11y tree filtered by visibility and enabled state, plus OmniParser-v2 vision for custom controls, deduplicated by box overlap). The full system with GPT-4o scored 27.9% on WAA (vs Operator 20.8%) and 28.6% on OSWorld-W (vs Operator 14.3%). The UIA-only base scored 23.4% on WAA. The full-vs-base gap also includes API actions and other features, so it does not isolate detection. — [UFO2 paper](https://arxiv.org/html/2504.14603v2) (via search summary)
- Fara-7B shows a pixel-only 7B model beating a GPT-4o SoM agent on WebTailBench (38.4 vs 30.0). — [Microsoft Research](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/)
- The Codex app's background computer use reportedly reads the macOS AX tree (HN commenter, unconfirmed). — [mjtsai](https://mjtsai.com/blog/2026/04/17/)

**Planner + grounder, coding agent, and best-of-N judges**
- **Agent S3** (Simular; arXiv 2510.02250, rev. Feb 2026):
  - Flat worker policy (hierarchy removed) plus a **coding agent in the action space** (Python/Bash in a sandbox, returns DONE/FAIL with a summary that the GUI agent verifies on screen).
  - OSWorld (100 steps, 361 tasks): Agent S2 + GPT-5 48.8% → Agent S3 + GPT-5 62.6%. Agent S2 without hierarchy scored 57.9%.
  - With **Behavior Best-of-N / Behavior Judge** at N=10: GPT-5 69.9%; GPT-5 + Opus 4.5 mixed rollouts **72.6%**, at the 72.36% human level. Prior best was GTA1 step-wise scaling with GPT-5 at 63.4%.
  - Judge method: a VLM writes a per-step "behavior narrative" from the before screenshot, the action, and the after screenshot (taken **3 s post-action**, with a pointer marker and a zoomed crop). A single-round multiple-choice comparative judge then picks the best rollout.
  - WindowsAgentArena 50.2% → 56.6% (N=3). AndroidWorld 68.1% → 71.6%.
  - Cost per GPT-5 rollout: about $0.72 and 891 s. Agent S3 vs S2: 52.3% fewer LLM calls, 62.4% less time.
  - Open-weight Qwen3-VL-30B-A3B rollouts: 33.3%, rising to 51.5% with a GPT-5 judge.
  — [Agent S3 paper (HTML v2)](https://arxiv.org/html/2510.02250v2); [arXiv abstract](https://arxiv.org/abs/2510.02250)
- UiPath Screen Agent (planner GPT-5 / GPT-5-mini / Gemini-2.5-Flash plus a UI-TARS-1.5 grounder): 53.6% on OSWorld at 50 steps (undated). — [UiPath](https://www.uipath.com/ai/research/screen-agent) (via search summary)
- Frontier models now ground natively at 85–88% on ScreenSpot-Pro (Q5). Since mid-2026, the top OSWorld-Verified rows are single frontier models or thin agent wrappers around them (Pointer + Opus 4.7, Claude Fable 5), not planner+grounder stacks. — [BenchLM](https://benchlm.ai/benchmarks/osworld-verified); [Presenc](https://presenc.ai/research/osworld-computer-use-leaderboard-2026)

**Batching, pruning, waits, thinking effort**
- Batching is native for all three vendors: Anthropic parallel `tool_use` blocks with a halt rule; OpenAI's `actions[]`; Gemini parallel function calls each answered with a `function_result`. Anthropic advises batching only independent actions (form fields), not exploration or recovery. The Claude in Chrome `browser_batch` notes that coordinates in a batch refer to the screenshot taken *before* the batch. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool); [OpenAI guide](https://developers.openai.com/api/docs/guides/tools-computer-use); [Gemini docs](https://ai.google.dev/gemini-api/docs/computer-use); [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude); **[local observation]** browser_batch schema
- OSWorld 2.0's top v2.0 result explicitly used "batched tool calls". — [OSWorld 2.0](https://osworld-v2.xlang.ai/)
- History pruning: about 1,000–1,800 tokens per screenshot means a 200k window fills in under 100 screenshots. Keep the 3 most recent, prune every 25 turns for cache efficiency, and compact at about 150k. — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude). OSWorld found extra screenshot history did not help, while text history did. — [OSWorld paper](https://arxiv.org/html/2404.07972)
- Waits: Anthropic `wait.duration` up to 300 s; Claude in Chrome up to 10 s; Gemini `wait` default 1 s; UI-TARS `wait()` = 5 s; Agent S3 takes after-screenshots 3 s post-action. — [Anthropic docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool); [Gemini docs](https://ai.google.dev/gemini-api/docs/computer-use); [UI-TARS prompt.py](https://raw.githubusercontent.com/bytedance/UI-TARS/main/codes/ui_tars/prompt.py); [Agent S3](https://arxiv.org/html/2510.02250v2)
- Thinking effort: Opus 4.7 `low` matches Sonnet 4.6 `max` at about 1/10 the tokens; `max` gave no benefit over `high` on 4.6. Gemini docs say lower thinking levels "generally achieve a good balance". — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude); [Gemini docs](https://ai.google.dev/gemini-api/docs/computer-use)
- Advisor pattern (beta): the executor consults a stronger advisor mid-run. It pays off after about 3 consults; nudge after about 20 turns without one. — [Claude blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)
- Code as action: OpenAI recommends code execution (PyAutoGUI/Playwright) for GPT-6 Astra. Agent S3's coding agent contributes roughly +4.7 points (inferred from its ablation). — [OpenAI guide](https://developers.openai.com/api/docs/guides/tools-computer-use.md); [Agent S3](https://arxiv.org/html/2510.02250v2)

### Inferences
- For a coding-agent harness, the highest-leverage design choices are:
  1. Expose structured targets (a11y refs via macOS AX / Windows UIA / AT-SPI) next to pixel coordinates, preferring refs where they exist.
  2. Provide zoom.
  3. Support ordered batching with halt-on-failure, returning one fresh screenshot at the end of the batch.
  4. Return change-aware screenshots with an automatic short settle delay (about 0.5–3 s, or wait until the frame stops changing) so the model doesn't spend turns on `wait`.
  5. Let the agent drop to bash/scripting (AppleScript, PyAutoGUI, Playwright) for bulk operations.

  Best-of-N with judges is an eval and offline technique, too costly for interactive use (about 10× rollouts).
- No published evidence was found that cursor-overlay rendering helps frontier models. Agent S3 uses a pointer marker only in the judge narratives. Anthropic's negative result on grid overlays suggests treating overlays as optional and debug-only.

### Gaps
- No quantitative study isolates "wait-for-UI-stable / screenshot diffing" against fixed sleeps for frontier CUAs.
- The architecture of Intelligence-Indeed Agent (90.19%) and Coasty CUA v1 is undisclosed.
- UFO3 and the UFO2 detection-ablation numbers (RQ1) were not retrieved. OCR-assisted targeting has no 2026 head-to-head numbers in the sources fetched.
- GTA1 details beyond the 63.4% (GPT-5 step-wise scaling) and GTA1-32B 63.6% ScreenSpot-Pro figures were not fetched.

---

## Q7. Safety/security patterns used by vendors

### Takeaway
Vendors layer five kinds of control:
1. Server-side prompt-injection classifiers on screenshots and page text (Anthropic on by default for its official tools; Gemini opt-in).
2. Per-action safety decisions or confirmations (Gemini `safety_decision`, OpenAI confirmation guidance, Anthropic confirmation advice).
3. App and site allowlists with **tiered permissions** (Claude desktop: browsers read-only, terminals/IDEs click-only, others full).
4. UX guardrails: Esc kill switch, hiding other apps, excluding the agent's own terminal from screenshots, a single-session lock.
5. Sandboxing guidance.

A self-built MCP server does not inherit Anthropic's server-side classifiers.

### Cited Findings
- Anthropic: classifiers scan tool-returned screenshots for prompt injection and steer the model to verify instructions with the user. Opt-out is via support. Recommendations: a dedicated VM or container, a domain allowlist, no credentials, human confirmation for consequential actions (payments, accepting terms or cookies), and informing users and getting consent. — [Anthropic computer use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- "Built-in prompt injection classifiers run by default on the official `computer_20251124` tool. They are not available for custom tool definitions." — [Claude blog best practices](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)
- Browser toolset hardening:
  - Fresh profile, no internal network access.
  - Network-layer domain allowlist, re-checked after redirects; `navigate` accepts only http/https, parsed with a real URL parser.
  - All page-supplied fields treated as untrusted.
  - `javascript_exec` and `file_upload` off by default; uploads restricted to an allowlisted directory.
  - Confirmation for purchases, account changes, messaging, and accepting terms.
  — [Anthropic browser use tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/browser-use-tool)
- Claude desktop / Cowork computer use tiers:
  - Browsers get **"read"** (visible, but clicks and typing blocked).
  - Terminals and IDEs get **"click"** (left-click only; typing, key presses, right-click, modifier-clicks, and drag blocked).
  - Everything else gets **"full"**.
  - Enforced by a frontmost-app check that returns an error explaining the tier. `open_application` is allowed at any tier.
  - Link safety: never click web links in native apps with computer-use tools; open them in a browser tool after checking the full URL.
  - Never execute trades or money transfers.
  — **[local observation]** Anthropic `computer-use` skill SKILL.md. The CLI docs confirm "browsers and trading platforms are view-only, terminals and IDEs are click-only" — [Claude Code docs](https://code.claude.com/docs/en/computer-use)
- Claude Code CLI guardrails: per-app per-session approval; "sentinel warnings" for apps equivalent to shell access (Terminal, iTerm, VS Code, Warp), Finder (any file), and System Settings; terminal excluded from screenshots; Esc consumed so injections can't use it; lock file; "Claude checks each action and flags potential prompt injection from on-screen content." The Desktop app adds a configurable denied-apps list. — [Claude Code docs](https://code.claude.com/docs/en/computer-use). Third-party reports describe default-blocked categories (trading, crypto, banking, adult, piracy) in the desktop product — [botmonster](https://botmonster.com/ai/claude-computer-use-hands-on-ai-desktop-control-cowork/) (secondary)
- Claude in Chrome:
  - Two classifiers: one screens incoming content, and one checks every planned action before it runs. Flagged actions are blocked or paused for approval.
  - Per-site permissions; adult and piracy sites blocked; financial sites need permission; high-risk actions (publishing, purchasing, sharing personal data) need confirmation.
  - Attack success rate below 0.08% for Opus 4.8 on Anthropic's internal suite (vendor-reported). At the 2025 launch it was 23.6% → 11.2% with mitigations.
  — [Claude help center: Using Claude in Chrome safely](https://support.claude.com/en/articles/12902428); [Anthropic: Claude for Chrome](https://www.anthropic.com/news/claude-for-chrome); [Simon Willison critique](https://feeds.simonwillison.net/2025/Aug/26/piloting-claude-for-chrome)
- Gemini:
  - Per-action `safety_decision` {`explanation`, `decision`}; on `require_confirmation`, prompt the user and return `safety_acknowledgement`.
  - Policy categories: `FINANCIAL_TRANSACTIONS`, `SENSITIVE_DATA_MODIFICATION`, `COMMUNICATION_TOOL`, `ACCOUNT_CREATION`, `DATA_MODIFICATION`, `USER_CONSENT_MANAGEMENT`, `LEGAL_TERMS_AND_AGREEMENTS`; adjustable via `disabled_safety_policies`.
  - `enable_prompt_injection_detection` is opt-in (default false, Gemini 3.5 Flash+).
  - Actions can be removed with `excluded_predefined_functions`.
  — [Gemini computer use docs](https://ai.google.dev/gemini-api/docs/computer-use). The Gemini 3.5 Flash launch adds adversarial training plus optional "stop on indirect prompt injection" and confirmation safeguards — [Google blog](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-computer-use-gemini-3-5-flash/)
- OpenAI: treat screen content as untrusted; page text "cannot grant permission"; confirm purchases, transmission, and destructive changes; typing sensitive data counts as transmission; step, time, and cost limits; keep PyAutoGUI's fail-safe on. GPT-5.4 lets developers set confirmation policies. — [OpenAI computer use guide](https://developers.openai.com/api/docs/guides/tools-computer-use.md); [VentureBeat GPT-5.4](https://venturebeat.com/technology/openai-launches-gpt-5-4-with-native-computer-use-mode-financial-plugins-for)
- Anthropic's support article: computer use has "no sandbox between Claude and your applications" and advises against sensitive data (financial, legal, health). — [Claude support: computer use safety](https://support.claude.com/en/articles/14128542-computer-use-safety) (via search summary)

### Inferences
- A harness-agnostic toolkit should do the following itself, because MCP or CLI tools don't get vendor-side screenshot classifiers:
  - per-session app allowlist with tiers (read / click / full) enforced at the frontmost-app check
  - sentinel warnings for shell-equivalent apps
  - exclusion of the host terminal from captures
  - a global hotkey abort that consumes the keypress
  - a single-controller lock
  - a mandatory `intent` / `action_summary` string on mutating actions (Gemini and Claude in Chrome pattern) for logging and optional local policy checks
  - confirmation hooks for consequential-action categories (reuse Gemini's taxonomy)
- Hiding non-approved apps during control (Claude Code) and running in a background virtual display (Codex app) are the two approaches for not taking over the user's desktop. The second allows parallel agents.

### Gaps
- Anthropic's classifier internals and false-positive rates are not published.
- OpenAI's 2026 status for `pending_safety_checks` is unconfirmed (the legacy mechanism is not mentioned in the current guide).
- No independent (non-vendor) measurement of prompt-injection robustness for 2026 CUAs was found.
