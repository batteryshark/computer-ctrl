# Holo4, H Company's agent harness, and open GUI-grounding models for a local "grounding specialist"

Research date: 2026-10-07. Every claim below comes from a page fetched or searched in this session unless it is explicitly labelled **[background, unverified]**. Several H Company and leaderboard pages publish their benchmark tables only as images; where text extraction failed, this is recorded under Gaps rather than guessed. Many 2026 model names (Qwen3.8, GPT-6 Astra, Muse Glimmer, Opus 5.5, Fable 5, etc.) appear in the sources; they are reported as the sources state them.

---

## Q1. What exactly is Holo4 (release, sizes, base, license, context, I/O format) and how does it benchmark against earlier Holo generations?

### Takeaway
Holo4 (released 2026-09-28) is a pair of general computer-use VLMs fine-tuned from Qwen bases: **Holo4-27B** (dense, Qwen3.8-27B base, **CC BY-NC 4.0**, non-commercial) and **Holo4-35B-A3B** (MoE with 3B active, Qwen3.6-35B-A3B base, **Apache 2.0**). Both have 262,144-token context. They are agent "policy" models that click, type, write code and call MCP/API tools, not narrow grounders. H reports OSWorld 85.2% / OSWorld 2.0 61.7% for the 27B. No grounding-benchmark text (ScreenSpot-Pro, OSWorld-G) for Holo4 could be extracted. When used for element localization through H's API, the output is JSON `{x, y}` as integers in 0–1000, normalized to the image that was sent.

### Cited Findings
**Release, variants, base, license, context**
- Released **September 28, 2026**. Two sizes: "Holo4 27B" (dense, labelled "Flagship") and "Holo4 35B-A3B" (MoE, 35B total / 3B active, labelled "Fast"). Released alongside **Holotron4 Nano** (`Hcompany/Holotron4-30B-A3B`), built on NVIDIA Nemotron 3 Nano Omni — [H Company newsroom: Holo4](https://hcompany.ai/newsroom/holo4)
- Holo4-27B: base **Qwen/Qwen3.8-27B**. License **CC BY-NC 4.0** ("The model weights are available under the Non-commercial (CC BY-NC 4.0) license"). BF16 safetensors. Max context **262,144** tokens. Pipeline tag image-text-to-text — [HF: Hcompany/Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B)
- Holo4-35B-A3B: base **Qwen/Qwen3.6-35B-A3B**, architecture tagged `qwen3_5_moe`. License **Apache 2.0** ("The model weights are available under the Apache License 2.0"). Max context **262,144** tokens. Supports function calling and takes screenshots plus tool results as input — [HF: Hcompany/Holo4-35B-A3B](https://huggingface.co/Hcompany/Holo4-35B-A3B)
- H's local-inference docs describe Holo4-27B as "for research use" and Holo4-35B-A3B as Apache 2.0 — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)
- Secondary coverage says the 27B's non-commercial weights mean commercial use of the 27B goes through the H Models API. One secondary report conflicts on bases (it names Qwen3-VL 8B/27B and Qwen3 30B-A3B), which contradicts the primary model cards above — [MarkTechPost](https://www.marktechpost.com/2026/09/29/h-company-releases-holo4-open-weight-computer-use-models-that-click-code-and-call-tools-across-desktop-web-android-and-apis/), [DataNorth](https://datanorth.ai/news/h-company-releases-holo4) (via search summary; the primary model cards win)
- Interfaces: GUI (clicking and typing), code, MCP and APIs, across desktop, web, Android, code sandboxes and business APIs. One checkpoint covers all of them — [H newsroom](https://hcompany.ai/newsroom/holo4)

**Training (as described by H)**
- SFT on **127B tokens**, about three quarters of it successful agentic trajectories: desktop 45%, web 14%, MCP/API 12%, mobile 3%. Asynchronous online RL trained **two LoRA experts** (desktop+web; terminal+MCP+API), which were then merged into the SFT model "with equal weight and no further training". The "Agentic Task Factory" has ~10,000 tasks (~4k web apps, ~3k MCP servers, ~3k desktop/OS) — [H newsroom](https://hcompany.ai/newsroom/holo4)
- The harness was "rebuilt using failure feedback on OSWorld 2.0". The major changes were a **persistent memory mechanism** and a **shell on the desktop machine**. The page does not name the harness — [H newsroom](https://hcompany.ai/newsroom/holo4)

**Benchmarks claimed by H (score, cost per task). Holo4-27B / Holo4-35B-A3B / Qwen3.8-27B run in Holo's harness**
- OSWorld: **85.2% ($0.08)** / 80.8% ($0.05) / 84.3% ($0.22) — [H newsroom](https://hcompany.ai/newsroom/holo4)
- OSWorld 2.0 (score / success / cost): **61.7% / 41.5% / $1.22** / 30.9% / 12.3% / $0.61 / 48.0% / 19.4% / $3.49 — [H newsroom](https://hcompany.ai/newsroom/holo4)
- ALE-CLI (score / success / cost): 44.1% / 19.4% / $0.82; 30.9% / 13.5% / $0.29; 43.5% / 19.0% / – — [H newsroom](https://hcompany.ai/newsroom/holo4)
- AutomationBench: 45.4% ($0.05) / 34.5% ($0.02) / 40.3%. Held-out 120 tasks: 49.3% / 31.7% / 40.3%, with Qwen3.6-35B-A3B at 13.1% — [H newsroom](https://hcompany.ai/newsroom/holo4)
- AndroidWorld: **85.1% ($0.08)** / 77.6% ($0.07) / 81.9% ($0.13) — [H newsroom](https://hcompany.ai/newsroom/holo4)
- ATF Web (47 apps) 80.2 / 70.8 / 77.6; ATF MCP (14 servers) 89.4 / 85.4 / 74.2; ATF Desktop (17 apps) 72.0 / 64.8 / 68.9 — [H newsroom](https://hcompany.ai/newsroom/holo4)
- Frontier references quoted by H (public scores, different harnesses): OSWorld — Fable 5 86.0%, GPT-5.5 78.7%, Qwen3.8 Max 86.1%. OSWorld 2.0 — Opus 5.5 81.8%, GPT-6 Astra 73.5%, Muse Spark 1.3 66.9%. AndroidWorld — Fable 5 88.8%, GPT-5.6 Sol 77.6%, Qwen3.8 Max 85.3% — [H newsroom](https://hcompany.ai/newsroom/holo4)
- Holotron4 Nano vs Nemotron 3 Nano Omni: OSWorld CUA GUI **21.0 → 76.3**; OSWorld 2.0 CUA+Code 0.2 → 7.9; AutomationBench MCP 19.4 → 35.6 — [H newsroom](https://hcompany.ai/newsroom/holo4)
- The newsroom page does **not** report ScreenSpot-Pro, ScreenSpot-v2, OSWorld-G, OSWorld-Verified, WebVoyager or WindowsAgentArena for Holo4. The HF card comparison tables are images that could not be read — [H newsroom](https://hcompany.ai/newsroom/holo4), [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B)

**Output format for clicks (element localization via H API)**
- Single-turn, no history. Message = image followed by the prompt "Localize an element on the GUI image according to the provided target and output a click position." + " * You must output a valid JSON following the format: {schema}" + " Your target is:" + description. Settings: `temperature=0.0`, `extra_body={"structured_outputs": {"json": schema}, "chat_template_kwargs": {"enable_thinking": False}}`. The example uses `holo4-27b` — [H docs: Element localization](https://hub.hcompany.ai/models-api/element-localization)
- Response: integer JSON `{"x":…, "y":…}` with each value in **[0, 1000]** (pydantic `Field(ge=0, le=1000)`), "normalized to the image you sent". Mapping: `abs_x = int(point.x / 1000 * SCREENSHOT_WIDTH)`. Pitfall listed: a screenshot "resized or cropped after the request" produces off-target clicks — [H docs: Element localization](https://hub.hcompany.ai/models-api/element-localization)

**Predecessors (lineage and grounding numbers)**
- **Holo1** (paper June 2025): 3B and 7B, fine-tuned from **Qwen2.5-VL-Instruct**. Holo1-7B: ScreenSpot v1 87.42, v2 89.85, **ScreenSpot-Pro 26.06**, GroundUI-Web 78.50, WebClick-agent 89.77. Holo1 counts 1280 tokens per 1200x1200 image — [arXiv 2506.02865 (Surfer-H Meets Holo1)](https://arxiv.org/html/2506.02865v2)
- **Holo1.5** (3B/7B/72B, ~Sept 2025): Holo1.5-7B ScreenSpot-Pro **57.9%**, OSWorld-G 66.2%, SS-v2 93.3%. Holo1.5-72B SS-Pro 63.3%, OSWorld-G 71.8% — [HF: Holo2-4B card, Table 2](https://huggingface.co/Hcompany/Holo2-4B). Holo1.5-3B SS-Pro 51.5, OSWorld-G 61.6 per an aggregator — [LLM Reference](https://www.llmreference.com/model/holo-1-5-3b) (secondary)
- **Holo2** (announced ~Nov 2025; 4B/8B/30B-A3B; 4B fine-tuned from **Qwen3-VL-4B-Thinking**). Single-pass ScreenSpot-Pro / OSWorld-G / SS-v2: Holo2-4B **57.2 / 69.4 / 93.2**; Holo2-8B 58.9 / 70.1 / 93.2; Holo2-30B-A3B **66.1 / 76.1 / 94.9**. Holo2-4B "Agentic" ScreenSpot-Pro = **68.6**. License: Holo2-4B and 8B Apache 2.0; 30B-A3B research-only — [HF: Hcompany/Holo2-4B](https://huggingface.co/Hcompany/Holo2-4B); launch tweet "66.1% (+3%) on ScreenSpot-Pro and 76.1% (+5%) on OSWorld-G" — [H on X](https://x.com/hcompany_ai/status/1989013556134638039)
- **Holo2-235B-A22B** (research preview, localization-focused): ScreenSpot-Pro **70.6%** single step and **78.5%** in agent mode within 3 steps; OSWorld-G 79.0%. "Agentic localization" (iterative refinement) gives "10-20% relative gains across all Holo2 model sizes" — [H: Holo2-235B-A22B preview](https://hcompany.ai/holo2-235b-a22b-preview) (via search summary)
- **Holo3** (March 2026): 122B-A10B (API-only per secondary sources) and 35B-A3B (open, Apache 2.0). OSWorld-Verified ≈ **78.85%** for 122B-A10B (company-reported) — [Wikipedia: H (company)](https://en.wikipedia.org/wiki/H_(company)), [BenchLM](https://benchlm.ai/compare/holo3-122b-a10b-vs-o3) (secondary)
- **Holo3.1** (June 1, 2026): 0.8B, 4B, 9B and 35B-A3B, "based on the Qwen family" (the HF tree points to Qwen3.5). AndroidWorld for the 35B-A3B rose from 67% (Holo3) to **79.3%**; the 4B/9B rose from 58% to **71%**. Native function calling was added — [H: Holo3.1 blog](https://hcompany.ai/holo3.1), [HF: Holo-3.1-4B](https://huggingface.co/Hcompany/Holo-3.1-4B). The 0.8B/4B/9B are Apache 2.0, with the 0.8B pitched "for grounding and simple actions" on-device — [H docs: Models API intro](https://hub.hcompany.ai/models-api/introduction)

### Inferences
- Holo4 is built to be the *main agent*, not a click-only grounder. For the user's split ("main LLM decides WHAT, small model returns WHERE"), Holo4's relevant feature is the stateless element-localization call pattern, which H exposes for any of its models.
- Because Holo2 used Qwen3-VL and Holo3.1/Holo4 use Qwen3.5/3.6/3.8 bases, they presumably inherit Qwen's native 0–1000 relative coordinates (consistent with the API docs). Holo1/1.5 were Qwen2.5-VL-based and so likely emitted absolute pixels in the resized image **[background, unverified for Holo1.5]**.

### Gaps
- No machine-readable Holo4 grounding scores (ScreenSpot-Pro, OSWorld-G, SS-v2). The tables are images on the HF cards. Also no Holo4 OSWorld-Verified, WebVoyager or WindowsAgentArena numbers were found.
- Holo4's input-resolution handling (min/max pixels, image-token budget) is undocumented in the text fetched. So is the coordinate format used in its *agent* tool calls, as opposed to the localization API.
- Secondary coverage claims that 480 of AutomationBench's 600 public tasks were in H's training split, which would raise a contamination concern. I could not attribute this to a specific outlet or verify it.
- Holo3.1-0.8B/4B/9B grounding scores (ScreenSpot-Pro, OSWorld-G) appear only in image tables; not found in text.

---

## Q2. Where are the weights, how are they served, what quantizations exist, what memory do they need, and is there a hosted API?

### Takeaway
All Holo4/Holo3.1 weights are on Hugging Face under `Hcompany/…` in BF16, FP8, NVFP4 and Q4 GGUF. They serve with vLLM ≥0.28, SGLang, Transformers, Docker Model Runner, and llama.cpp (`llama-server -hf …`). Even Q4 GGUF of a 35B-A3B is ~21 GB of weights, so neither Holo4 size fits an 11 GiB VM. The small Holo3.1 checkpoints (0.8B = 2.2 GB BF16, 4B = 10.4 GB BF16, plus community GGUFs) do. The H Models API is OpenAI-compatible at `https://api.hcompany.ai/v1`. `holo4-35b-a3b` costs $0.30/$2.00 per 1M input/output tokens, and `holo3-1-35b-a3b` is **free at 10 requests/min**.

### Cited Findings
**Repos**
- `Hcompany/Holo4-27B`, `Hcompany/Holo4-35B-A3B`, collection `Hcompany/holo4`, `Hcompany/Holotron4-30B-A3B`, dataset `Hcompany/trajectories` (viewer at trajectories.hcompany.ai) — [H newsroom](https://hcompany.ai/newsroom/holo4)
- Quantized: `Holo4-35B-A3B-FP8`, `-NVFP4`, `-GGUF` (Q4); the same set for 27B. The HF model tree lists 9 (35B-A3B) and 11 (27B) quantizations — [HF Holo4-35B-A3B](https://huggingface.co/Hcompany/Holo4-35B-A3B), [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B)
- GGUF repos named by H: `Hcompany/Holo4-27B-GGUF`, `Hcompany/Holo4-35B-A3B-GGUF`, `Hcompany/Holo-3.1-35B-A3B-GGUF` (Q4_K_M). Other Holo3.1 repos: `Hcompany/Holo-3.1-9B`, `-4B`, `-0.8B` — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)
- Community GGUFs exist for the small Holo3.1 models (official repos are safetensors only): `mradermacher/Holo-3.1-0.8B-GGUF` and `-i1-GGUF`, `ijohn07/Holo-3.1-0.8B-Q4_K_M-GGUF`, `mradermacher/Holo-3.1-4B-GGUF` (5,156 downloads), `ijohn07/Holo-3.1-4B-Q4_K_M-GGUF`, `prithivMLmods/Holo-3.1-9B-GGUF`, `mradermacher/Holo-3.1-9B-GGUF` — [HF API search](https://huggingface.co/api/models?search=Holo-3.1&limit=50)

**Serving commands**
- vLLM: `vllm serve "Hcompany/Holo4-35B-A3B"` (OpenAI API on :8000). SGLang: `python3 -m sglang.launch_server --model-path "Hcompany/Holo4-35B-A3B" --port 30000`. Transformers: `AutoModelForMultimodalLM.from_pretrained(..., device_map="auto")`. Docker Model Runner: `docker model run hf.co/Hcompany/Holo4-35B-A3B` — [HF Holo4-35B-A3B](https://huggingface.co/Hcompany/Holo4-35B-A3B)
- Tuned Holo4 vLLM (needs **vLLM 0.28+**): `vllm serve Hcompany/Holo4-35B-A3B-FP8 --served-model-name holo4-35b-a3b --max-model-len 262144 --enable-prefix-caching --chat-template-content-format openai --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 --limit-mm-per-prompt '{"image": 5, "video": 0}'`. NVFP4 needs vLLM on Blackwell — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)
- llama.cpp: `llama-server -hf Hcompany/Holo-3.1-35B-A3B-GGUF`. The tuned example adds `--n-gpu-layers 999 --ctx-size 65536 --flash-attn 1 --cache-type-k q8_0 --cache-type-v q8_0 --image-min-tokens 1024 --ctx-checkpoints 8 --cache-ram 32768 --kv-unified`. Note: "llama.cpp does not yet cache prefixes or images for the Qwen architecture", which limits throughput — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)
- The docs mention no CPU-only, AMD, Vulkan or ROCm guidance, and no MLX instructions — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)

**Memory (weights only; KV cache and vision encoder add on top)**
- 35B-A3B: BF16 70.2 GB, FP8 37.6 GB, NVFP4 23.7 GB, **Q4_K_M GGUF 21.3 GB**. Holo3.1 9B BF16 18.8 GB (24 GB GPU), **4B BF16 10.4 GB** (16 GB GPU), **0.8B BF16 2.2 GB** ("on-device, for grounding and simple actions"). Mac recommendation for the 35B-A3B: M3+ with ≥36 GB unified memory — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference), [H docs: Models API intro](https://hub.hcompany.ai/models-api/introduction)

**Measured speed (H's numbers, Holo3.1-35B-A3B)**
- DGX Spark throughput (12k in / 1k out, three 1080p images, concurrency 1): BF16 326 tok/s, FP8 404, NVFP4 568. Average step time 6.8 s → 3.3 s with NVFP4 plus harness optimizations — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference), [H: Holo3.1](https://hcompany.ai/holo3.1)
- Model requests/min in HoloDesktop CLI. Default harness: MacBook M4 Pro Q4 (llama.cpp) **3.6**, Spark FP8 8.9, Spark Q4 9.5, Spark NVFP4 13.5. Fast harness: MacBook Q4 **5.5**, Spark NVFP4 18.1 — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)

**Hosted API (H Models API)**
- Base URL `https://api.hcompany.ai/v1`, OpenAI-compatible ("tools in, `tool_calls` out"). Up to 5 images/request (JPEG/PNG/WebP). Zero data retention by default — [H docs: Models API intro](https://hub.hcompany.ai/models-api/introduction)
- Prices per 1M tokens (input / cached / output): `holo4-35b-a3b` $0.30 / $0.03 / $2.00 (paid, 262,144 ctx); `holo4-27b` $0.40 / $0.04 / $3.00 (paid); `holo3-1-35b-a3b` $0.25 / $0.025 / $1.80 (**free tier, 10 req/min**, 65,536 ctx); `holo3-122b-a10b` $0.40 / $0.04 / $3.00 (paid). H says "Start with `holo4-35b-a3b`" — [H docs: Models API intro](https://hub.hcompany.ai/models-api/introduction)
- No Holo model was found on OpenRouter. One aggregator lists a $1.00 image-input rate for Holo3.1 that I could not confirm on H's own page — [LLM Reference: Holo3.1 on H API](https://www.llmreference.com/model/holo-3-1-35b-a3b/h-company-api) (secondary)

### Inferences
- Cost per grounding call on `holo4-35b-a3b`: ~2.5k input tokens (one 1080p screenshot plus prompt) × $0.30/M ≈ $0.00075, plus ~20 output tokens × $2/M ≈ $0.00004, so **≈ $0.0008 per click** (my arithmetic). The free Holo3.1 tier (10 rpm) is enough to prototype a grounding tool.
- For local use on the target VM, only Holo3.1-0.8B (Q4–Q8 GGUF, under 1.5 GB) and Holo3.1-4B (Q4_K_M ≈ 3 GB weights plus mmproj, estimated) are realistic. Holo4 is not.

### Gaps
- Exact file sizes of Holo4 GGUFs were not fetched. By analogy with Holo3.1-35B-A3B Q4_K_M (21.3 GB), the 35B-A3B is likely ~21 GB, and the 27B Q4 likely ~16–17 GB **[estimate]**.
- No official Holo4 MLX or Ollama-library build was found.

---

## Q3. What is H Company's harness (Surfer-H → successors), is it open source, how is it built, and what design ideas are worth copying?

### Takeaway
H's harness has evolved from **Surfer-H** (2025, web-only, described in a paper but not released as code) to today's **HoloDesktop CLI** (`hcompai/holo-desktop-cli`, Apache-2.0). HoloDesktop CLI is a thin, open Python client around a **closed-source `hai-agent-runtime` binary** that does the actual observation and action. It exposes CLI, MCP, ACP, A2A and Python surfaces, plus an Agent Skill for Claude Code, Codex and opencode. It can point at any OpenAI-compatible local server. On Linux it supports **x86_64 + X11 only**, which matches the user's Debian 13/XFCE/X11 VM. Separately, `hai-agents-python` (MIT) is an SDK for H's hosted Agents API. The Holo4 newsroom post describes an unnamed rebuilt harness with persistent memory and a desktop shell.

### Cited Findings
**Surfer-H (Holo1 paper, 2025)**
- Three trainable modules in sequence, screenshots only (no DOM or accessibility tree). The **policy** emits thought → optional note → action. The **localizer** turns the policy's textual element description into 2D coordinates. The **validator** checks the final answer against supporting screenshots and returns a success boolean plus an explanation. On rejection, the feedback is written to the notepad and the run continues — [arXiv 2506.02865](https://arxiv.org/html/2506.02865v2)
- Memory holds the task, past actions, thoughts, notes, **the last 3 screenshots**, and the current view. Action space: click/type into element, scroll up/down, wait, refresh, go to URL, go back, answer. Limits: 30 policy steps per attempt, up to 10 validation attempts — [arXiv 2506.02865](https://arxiv.org/html/2506.02865v2)
- WebVoyager: Surfer-H + Holo1-7B **92.2% at $0.13/task**, vs Surfer-H + GPT-4.1 92.0% at $0.54/task. Holo1-3B 89.7% at $0.11/task. Baselines: BrowserUse 89.1%, Operator 87.0%, Mariner 83.5% — [arXiv 2506.02865](https://arxiv.org/html/2506.02865v2)

**HoloDesktop CLI (current desktop harness)**
- Repo `hcompai/holo-desktop-cli`: "Desktop agent built on H Company's Holo3 vision-language models". Client is Apache-2.0. The agent "runs inside `hai-agent-runtime`", described as **closed-source**, downloaded on first run and sha256-verified. The client↔runtime contract is the open `hai-agent-api` package. 51 stars, 29 commits, no releases listed — [GitHub: hcompai/holo-desktop-cli](https://github.com/hcompai/holo-desktop-cli)
- Platforms: macOS Apple Silicon (needs Screen Recording + Accessibility), Windows x86_64/ARM64, **Linux x86_64 "needs an X11 session… Wayland is not supported"**, macOS Intel bring-your-own runtime. It currently "drives the visible screen and shares your mouse and keyboard". A background/own-window mode is on the roadmap — [H docs: HoloDesktop CLI overview](https://hub.hcompany.ai/holo-desktop-cli.md). Conflict: the GitHub README mentions Linux only in the context of Wayland having "no global key listener" (probably the kill switch), not as unsupported — [GitHub README](https://github.com/hcompai/holo-desktop-cli)
- Surfaces: `holo run "task"`; `holo mcp` / `holo install` (MCP for Claude Code, Cursor, Codex); `holo acp` (stdio, beta; "ACP hosts can cancel an in-flight task", whereas an MCP task "blocks until it finishes"); `holo serve` (A2A HTTP on 127.0.0.1); Python `holo_desktop.agent_client` — [H docs overview](https://hub.hcompany.ai/holo-desktop-cli.md), [GitHub](https://github.com/hcompai/holo-desktop-cli)
- Local inference: `holo run "..." --base-url http://localhost:8000/v1 --model holo3-1-35b-a3b`. "Any OpenAI-compatible server". With a local server, "no screenshots, keystrokes, or app content leave your machine" — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference), [H docs overview](https://hub.hcompany.ai/holo-desktop-cli.md)
- Architecture: "a thin client around a local computer-use agent runtime". The client starts or attaches to the runtime on loopback. All surfaces route to the same runtime. The runtime "owns desktop observation and action" (click, type, scroll, switch apps). "The agent observes and acts; it does not verify", and H recommends verifying results "with code, not another model call". User context is read from `~/.holo/` (`agents.md` standing instructions, memories, rules, installed skills) and snapshotted at run start. An event stream is emitted and saved locally — [H docs: Architecture](https://hub.hcompany.ai/holo-desktop-cli/architecture)
- Fast vs default harness: `holo run --fast` "takes one screenshot per step, skips thinking, and uses smaller images". It is faster but less accurate on fiddly UIs — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)
- Safety: double-Esc panic stop; plain stop is "step-bounded" (halts the next action); `holo stop --force` sends SIGKILL; `--no-kill-switch` disables it; `max_steps` and `max_time_s` limits — [GitHub](https://github.com/hcompai/holo-desktop-cli)
- Agent Skill: ships a `holo-desktop` skill installed to `~/.claude/skills/holo-desktop` (Claude Code), `~/.agents/skills/holo-desktop` (Codex), `~/.config/opencode/skills/holo-desktop` (OpenCode), plus Grok Build and OpenClaw. "MCP tells the host how to reach HoloDesktop CLI; the skill tells it when to." The CLI does not see the host conversation, so the host must put the app, account, person and **success condition into the `task` string**. "A skill is guidance, not a safety boundary." For irreversible actions the host should confirm first or ask Holo to only observe and report — [H docs: Use as skill](https://hub.hcompany.ai/holo-desktop-cli/integrations/use-as-skill)

**hai-agents-python (hosted Agents API SDK)**
- MIT. `pip install hai-agents` (plus a `[cli]` extra with the `hai` command). `Client().run_session(agent="h/web-surfer-pro", ...)`. Includes start/steer/pause/resume/force_answer/cancel, pydantic `answer_schema` structured output, custom Python tools, browser profiles/vaults, webhooks. `Client.local()` supports a `workstation` environment (`user_device` or `cloud`), and self-hosted inference goes through `Inference.self_hosted(url, model=...)`. `hai mcp install` targets Cursor, VS Code and Claude Code. 42 stars — [GitHub: hcompai/hai-agents-python](https://github.com/hcompai/hai-agents-python)
- The Holo4 HF cards call this repo the "hai-agents harness" — [HF Holo4-35B-A3B](https://huggingface.co/Hcompany/Holo4-35B-A3B)

**Related ideas from other harnesses**
- Microsoft Fara1.5 is trained to stop at "critical points" (personal info, payments, submissions, sign-ins, sending messages, irreversible actions). Its 4B card recommends the co-designed MagenticLite harness — [Decrypt](https://decrypt.co/368807/microsoft-fara15-open-source-ai-beats-openai-gemini), [HF microsoft/Fara1.5-4B](https://huggingface.co/microsoft/Fara1.5-4B) (via search summary)

### Inferences
- **Design ideas worth copying for a harness-agnostic toolkit:**
  1. A **stateless `locate(image, description) → {x,y}` tool**: temperature 0, thinking off, JSON-schema-constrained output in 0–1000 relative to the exact bytes sent, then mapped deterministically (H localization API).
  2. **Agentic/zoom localization** as an optional second pass: crop around the first guess and re-ask. This gives 10–20% relative gains for Holo2 and similar zoom gains for UI-Venus and MAI-UI.
  3. The **policy/localizer/validator split** (Surfer-H). Keep the host LLM as policy, the small model as localizer, and verification in code (pixel diff, accessibility query, file check), per H's "verify with code" advice.
  4. A **thin client over a long-lived local daemon** on loopback, with many surfaces (CLI, MCP, ACP, A2A, Python) routing to one runtime.
  5. **Skill = when, MCP = how**, with self-contained task strings that include the success condition.
  6. **Standing instructions/memories/rules** in a dotdir (`~/.holo/agents.md`) snapshotted per run, plus a local event log.
  7. **Fast mode** (one screenshot, no thinking, smaller images) vs an accurate mode.
  8. A **double-Esc kill switch**, step-bounded stop, and step/time budgets.
  9. A **shell on the desktop** alongside GUI actions (Holo4 harness).
- HoloDesktop CLI could run on the user's Debian/XFCE/X11 VM as a reference implementation, but its runtime is a closed binary. Treat it as a behaviour reference, not something to fork.

### Gaps
- The `hai-agent-runtime` action schema, screenshot capture method, resize policy, HiDPI/multi-monitor handling (docs say primary display only), and MCP tool names and parameters were not found in the fetched pages. They may be on `/holo-desktop-cli/integrations/agent-hosts` and `/reference/cli` (not fetched).
- Whether the Holo4 OSWorld harness ("persistent memory + shell") is the same as HoloDesktop CLI's runtime is not stated.

---

## Q4. Which competing open grounding/CUA models exist as of Oct 2026, how do they score, and which gives the best accuracy per parameter for CPU/iGPU?

### Takeaway
At the ≤4B tier, single-pass ScreenSpot-Pro has converged around **57–58%**: UI-Venus-1.5-2B **57.7**, MAI-UI-2B **57.4**, Holo2-4B **57.2**. Zoom or agentic passes add 5–11 points (UI-Venus-1.5-2B+ZoomIn 64.6; MAI-UI-2B zoom 62.8; Holo2-4B agentic 68.6). The 8B tier reaches ~65–70 (UI-Venus-1.5-8B 68.4, MAI-UI-8B 65.7, GUI-Owl-1.5-8B ~70.5 per a third-party re-eval). Best accuracy per parameter for a CPU/iGPU box: **UI-Venus-1.5-2B** (Qwen3-VL-based, Apache-2.0 badge but a "research and educational purposes only" note) and **MAI-UI-2B**. The cleanest-licensed option is **Holo2-4B** (Apache 2.0). **Holo3.1-0.8B/4B** (Apache 2.0) are newer but have no text-verified grounding scores. For comparison, UI-TARS-1.5-7B scores only 39.0 on ScreenSpot-Pro.

### Cited Findings
**Small and mid open models (ScreenSpot-Pro, single pass unless noted)**
- UI-Venus-1.5 (Ant Group, Feb 2026; 2B/8B dense, 30B-A3B MoE; "Starting from the Qwen3-VL Series"). SS-Pro / OSWorld-G / UI-Vision: **2B 57.7 / 59.4 / 44.8** (+ZoomIn 64.6 / 61.4 / 46.8); **8B 68.4 / 69.7 / 46.5** (+ZoomIn 73.9); 30B-A3B 69.6 / 70.6 / 54.7 (+ZoomIn 74.8). AndroidWorld: 2B 55.6, 8B 73.7, 30B-A3B 77.6. The README has an Apache 2.0 badge but also says "This project is for research and educational purposes only" — [GitHub: UI-Venus 1.5 README](https://github.com/inclusionAI/UI-Venus/blob/UI-Venus-1.5/README.md). The 2B card lists apache-2.0, 2B params, tag `qwen3_vl`, and 5 community quantizations — [HF: UI-Venus-1.5-2B](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B)
- MAI-UI (Alibaba Tongyi, weights released 2025-12-29 for **2B and 8B** only; 32B and 235B not released). SS-Pro "without any zoom-in tricks": 32B 67.9, **8B 65.7, 2B 57.4**. MAI-UI-235B AndroidWorld 76.7% — [GitHub: Tongyi-MAI/MAI-UI](https://github.com/Tongyi-MAI/MAI-UI). With zoom-in, 2B → 62.8 SS-Pro; headline 73.5 SS-Pro (zoom) and 70.9 OSWorld-G — [arXiv 2512.22047](https://arxiv.org/html/2512.22047) (via search summary). The repo states Apache 2.0 for the code; the weights license is stated only in secondary sources (Apache 2.0) — [Qwen-UI-Agent wiki](https://ai.miraheze.org/wiki/Qwen-UI-Agent) (secondary)
- GUI-Owl-1.5 / Mobile-Agent-v3.5 (Alibaba, Feb 2026; 2B/8B/32B; Instruct and Think). 32B-Instruct SS-Pro 72.9, or **80.3** with two-stage crop-refine — [labnotes.tech](https://labnotes.tech/blog/gui-owl-1-5-sets-new-bar-for-open-source-gui-agents), [arXiv 2602.16855](https://arxiv.org/abs/2602.16855). GUI-Owl-1.5-8B-Instruct re-evaluated at **70.5 SS-Pro / 64.7 OSWorld-G** in a third-party fine-tune card — [HF: vocaela/KV-Ground-8B](https://huggingface.co/vocaela/KV-Ground-8B-BaseGuiOwl1.5-0315). ModelScope lists MIT for the 2B/8B; Emergentmind says Apache-2.0 (conflict) — [ModelScope GUI-Owl-1.5-2B](https://modelscope.ai/models/iic/GUI-Owl-1.5-2B-Instruct). A community Ollama build exists — [ollama.com/ahmadwaqar/gui-owl](https://ollama.com/ahmadwaqar/gui-owl)
- Holo2-4B 57.2 (agentic 68.6), Holo2-8B 58.9, Holo2-30B-A3B 66.1 (agentic 75.2 per PwC). Same table: **Qwen3-VL-4B-Thinking 41.4**, Qwen3-VL-8B-Thinking 38.5, Qwen3-VL-30B-A3B-Thinking 49.9, **UI-TARS-1.5-7B 39.0** (OSWorld-G 61.0, SS-v2 94.0), UI-Venus-7B (v1.0) 50.8, UI-Venus-72B 61.9 — [HF: Holo2-4B](https://huggingface.co/Hcompany/Holo2-4B)
- Step-GUI-8B 62.6 SS-Pro, AndroidWorld 67.7 — [UI-Venus 1.5 README](https://github.com/inclusionAI/UI-Venus/blob/UI-Venus-1.5/README.md)
- OpenCUA-7B (XLANG) **50.0 SS-Pro / 55.3 OSWorld-G** — [arXiv 2508.09123 OpenCUA](https://arxiv.org/pdf/2508.09123) (via search summary)
- Gelato-30B-A3B (mlfoundations; 3B active) ~**63.9 SS-Pro / 69.15 OSWorld-G** (74.65 refined), trained on open Click-100k. Its table gives GTA1-32B 63.6 / 65.2 and Qwen3-VL-235B-A22B-Instruct 62.0 / 66.7. With GPT-5 as planner: 58.71% OSWorld vs 56.97% for GTA1-32B — [HF: mlfoundations/Gelato-30B-A3B](https://huggingface.co/mlfoundations/Gelato-30B-A3B)
- Microsoft **Fara1.5** (4B/9B/27B, Qwen3.5-based, **MIT**, weights public on HF as of a July 22, 2026 update; 262K ctx). Vision-only browser agent that predicts click/drag coordinates directly. 27B: Online-Mind2Web ~72%, WebVoyager 88.6%. The 9B demo uses normalized 0–1000 coordinates on a 1440×900 viewport. PwC lists "Fara1.5-27B (two-step zoom)" on SS-Pro but with no score shown — [Microsoft Research: Fara1.5](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent), [Decrypt](https://decrypt.co/368807/microsoft-fara15-open-source-ai-beats-openai-gemini), [Fara1.5-9B demo space](https://hugging-apps-fara-computer-use-agent.hf.space/), [PwC](https://paperswithcode.co/benchmark/screenspot-pro?eval=5370) (via search summary)
- NVIDIA **LocateAnything-3B** (arXiv 2605.27365, May 2026): a generalist grounding/detection model with "Parallel Box Decoding" and GUI element grounding among its tasks. PwC lists it at 60.3 SS-Pro, which I could not confirm in a primary source. The license is reportedly non-commercial — [HF: NVIDIA/LocateAnything-3B](https://huggingface.co/NVIDIA/LocateAnything-3B), [NVIDIA project page](https://research.nvidia.com/labs/lpr/locate-anything/index.html) (score via search summary; unverified)
- UI-TARS-2 was announced 2025-09-04. I found no primary evidence of open weights; only UI-TARS-1.5-7B and earlier are open — [TokenMix blog](https://tokenmix.ai/blog/ui-tars-2-bytedance-gui-agent-walkthrough-2026) (secondary, unverified claim of HF availability)

**Leaderboards (context, mostly closed models at the top)**
- BenchLM SS-Pro (updated 2026-10-07): GPT-6 Astra 92.7%, Claude Opus 4.8 87.9%, GPT-5.4 85.4%, Qwen3.8 Max 84.5%, Gemini 3.1 Pro 84.4% … Holo2-235B-A22B 70.6, Holo2-30B-A3B 66.1, Qwen3.5-397B 65.6, Holo2-8B 58.9, Nemotron 3 Nano Omni 30B-A3B 57.8, Holo2-4B 57.2 — [BenchLM](https://benchlm.ai/benchmarks/screenspot-pro). Note: llm-stats says all 26 of its SS-Pro entries are self-reported, 0 verified — [llm-stats](https://llm-stats.com/benchmarks/screenspot-pro) (via search summary)
- PwC SS-Pro rows include GUI-Owl-1.5-32B (crop zoom), Holo2-235B (agentic, 78.5), Muse Glimmer-30B, UI-Venus-2-27B (2026-08-27), MAI-UI-32B (zoom-in, 73.5), Holo3-122B, Holo3.1-35B-A3B, UI-Venus-1.5-30B-A3B, Fara1.5-27B, GTA1-32B, EvoCUA-OpenCUA-72B and Step-GUI-8B. The fetched page did not render the scores — [Papers with Code: ScreenSpot-Pro](https://paperswithcode.co/benchmark/screenspot-pro?eval=5370)
- The official grounding leaderboard page (last updated Sep 10, 2026) rendered only per-application tables in the fetch — [gui-agent.github.io/grounding-leaderboard](https://gui-agent.github.io/grounding-leaderboard/). The original paper's best model at launch was OS-Atlas-7B at 18.9% — [ScreenSpot-Pro paper](https://arxiv.org/abs/2504.07981)

### Inferences
- Within ~1 point, the three ≤4B options (UI-Venus-1.5-2B, MAI-UI-2B, Holo2-4B) are equivalent on SS-Pro. The choice comes down to license, runtime support (all are Qwen3-VL-derived, so llama.cpp mtmd and vLLM support should follow Qwen3-VL), and zoom behaviour. A 2B model is roughly half the compute of Holo2-4B per call, so **UI-Venus-1.5-2B / MAI-UI-2B lead on accuracy per parameter**, and Holo2-4B leads on license clarity.
- Raw base Qwen3-VL-4B (41.4) is ~16 points worse than the specialized fine-tunes. Use a GUI-specialized checkpoint.
- ScreenSpot-Pro targets professional high-res apps. On ordinary desktop UIs (SS-v2-like), all of these models score 93–96%, so a ~57% SS-Pro 2B model may be adequate for typical XFCE/Office dialogs, especially with a zoom second pass.

### Gaps
- Not researched or verified this session: OmniParser v2 (detector + captioner), Phi-Ground, Jedi, OS-Atlas beyond its launch score, ShowUI, Moondream 3, GLM-4.xV, InternVL3.x, GTA1-7B exact SS-Pro, Qwen3.5 small-size raw grounding scores, UI-Venus-2 details. **[background, unverified]**: OmniParser v2 pairs a YOLO icon detector with a captioner and was previously reported at ~39.6% SS-Pro when paired with GPT-4o; its icon-detector weights carried an AGPL license.
- No text-verified SS-Pro or OSWorld-G for Holo3.1-0.8B/4B/9B, MAI-UI-2B OSWorld-G, or GUI-Owl-1.5-2B.
- License conflicts (UI-Venus-1.5; GUI-Owl-1.5 MIT vs Apache) need checking on each HF card's LICENSE file.

---

## Q5. Is running a grounder locally on a Radeon 780M iGPU in an 11 GiB Debian 13 VM feasible? If not, what are the cheapest hosted options?

### Takeaway
**Holo4 locally: no.** It needs ≥21 GB even at Q4. A **2B–4B Qwen3-VL/3.5-derived grounder in Q4–Q8 GGUF via llama.cpp is feasible**. Use the **Vulkan (Mesa RADV) backend**, which supports gfx1103 natively; ROCm on gfx1103 needs `HSA_OVERRIDE_GFX_VERSION=11.0.0`, and recent HIP builds of llama.cpp have crashed because rocBLAS lacks gfx1103. There are no published 780M latency numbers for VLM grounding. Expect seconds per call, dominated by image-token prefill. Cheapest hosted: **H Models API free tier (`holo3-1-35b-a3b`, 10 rpm)**, then `holo4-35b-a3b` at ≈$0.0008/call, or OpenRouter `bytedance/ui-tars-1.5-7b` at $0.10/$0.20 per 1M tokens (weaker grounder, 39.0 SS-Pro).

### Cited Findings
- ROCm/HIP: an open llama.cpp issue reports gfx1103 "missing from rocBLAS TensileLibrary — HIP backend crashes on warmup in recent builds" — [llama.cpp issue #20839](https://github.com/ggml-org/llama.cpp/issues/20839)
- The usual workaround is `HSA_OVERRIDE_GFX_VERSION=11.0.0` for 780M/gfx1103 ("slow but functional"). Ollama's supported-target list omits gfx1103. AMD does not officially support iGPUs. Native support in ROCm 7.2 covers newer discrete cards, not the 780M — [InsiderLLM guide](https://insiderllm.com/guides/rocm-not-detecting-gpu-amd-fix/), [RunAIHome guide](https://runaihome.com/blog/amd-gpu-not-detected-rocm-hsa-override-fix-2026/) (secondary)
- Vulkan on Mesa RADV has native gfx1103 support and is the commonly recommended path — [Lorenzo's blog (k8s.it)](https://www.k8s.it/posts/running-a-local-llm-on-amd-radeon-780m-gfx1103-rocm-and-the-gpu-that-wasnt-supposed-to-work/) (via search summary)
- Reported 780M numbers (text LLMs, not VLMs): a Japanese write-up measured Vulkan **43.7 tok/s generation, 700.8 tok/s prefill** at 65,536 ctx vs ROCm 33.5 tok/s (model unnamed) — [note.com 780M Vulkan trends](https://note.com/samehadaonsen/n/nf45afb0f044e?hl=en). Llama-3-8B Q5_K_M via KoboldCPP Vulkan: ~11–12 tok/s generation. A Phoenix-class run of a ~7 GB model: ~39 tok/s prefill, 4.7 tok/s generation (Vulkan) vs 5.3 tok/s CPU — [llama.cpp Vulkan perf discussion #10879](https://github.com/ggml-org/llama.cpp/discussions/10879), [k8s.it](https://www.k8s.it/posts/running-a-local-llm-on-amd-radeon-780m-gfx1103-rocm-and-the-gpu-that-wasnt-supposed-to-work/) (via search summary; attribution between these two is approximate)
- One user observation: ROCm is faster for prompt processing, Vulkan for token generation — (via search summary of the same 780M sources above)
- H notes llama.cpp lacks prefix/image caching for Qwen arch, and uses `--image-min-tokens 1024` in its tuned config — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference)
- Community GGUFs for Holo-3.1-0.8B and -4B exist (Q4_K_M, Q6_K, Q8_0, imatrix) — [HF API search](https://huggingface.co/api/models?search=Holo-3.1&limit=50). UI-Venus-1.5-2B has 5 community quantizations — [HF UI-Venus-1.5-2B](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B)
- Hosted prices: H `holo4-35b-a3b` $0.30/$2.00, `holo3-1-35b-a3b` free at 10 rpm — [H docs: Models API intro](https://hub.hcompany.ai/models-api/introduction). OpenRouter `bytedance/ui-tars-1.5-7b` $0.10/M in, $0.20/M out, 128K ctx — [OpenRouter: UI-TARS-1.5-7B](https://openrouter.ai/bytedance/ui-tars-1.5-7b) (via search summary). A third-party host lists Holo2-30B-A3B at $0.30/$0.70 — [EURouter](https://www.eurouter.ai/models/holo2-30b-a3b) (secondary; Holo2-30B-A3B is non-commercial)

### Inferences
- **Memory budget:** 11 GiB is shared by the OS, the XFCE desktop, the screenshot pipeline and the iGPU (UMA). A 2B Q8 (~2.5 GB) or 4B Q4_K_M (~3 GB) plus mmproj (~0.4–0.7 GB) and a small KV cache (only ~3k tokens needed per stateless call) fits comfortably. Holo4 (16–21 GB+) does not. **[estimate]**
- **Image tokens:** at Qwen3-VL/3.5's 32-px effective patch, a 1920×1080 screenshot ≈ 60×34 ≈ **2,040 visual tokens** (smart-resized to 1920×1088). At the 780M's reported text prefill of a few hundred tok/s for small models, plus the ViT encoder, expect roughly **2–8 s per grounding call for a 2B model and longer for 4B** (my estimate; no VLM measurement on 780M found). Downscaling screenshots to ~1280×720 (~920 tokens) roughly halves this at some accuracy cost on small targets.
- **VM caveat:** the iGPU must be passed through to the VM (the presence of `/dev/kfd` suggests the amdgpu KFD node is visible). Vulkan additionally needs `/dev/dri/renderD*` and Mesa RADV inside the VM or container. If passthrough is unavailable, CPU-only inference on 6 vCPUs for a 2B VLM is feasible but likely ~2–4× slower **[estimate]**.
- **Pragmatic plan:** build the grounding tool against an OpenAI-compatible endpoint, so the same code targets (a) local llama-server (Vulkan) with UI-Venus-1.5-2B / MAI-UI-2B / Holo3.1-0.8B/4B / Holo2-4B, (b) the H API free tier, or (c) `holo4-35b-a3b` hosted, switched by config.

### Gaps
- No hands-on report of Qwen3-VL/3.5 vision (mtmd) on a 780M with timings. No confirmation that llama.cpp's Vulkan backend handles the vision encoder for `qwen3_5` arch without fallback.
- Ollama status for Holo3.1 small models or UI-Venus-1.5 not confirmed (one community GUI-Owl build exists).
- Together, Fireworks and HF Inference Endpoints pricing for grounding models was not researched.

---

## Q6. How do these models expect screenshots to be sized, and how should a toolkit map their coordinates back to physical screen pixels (HiDPI, multi-monitor)?

### Takeaway
Qwen2.5-VL-era models (Holo1, UI-TARS-1.5, OpenCUA, GTA1-7B and other Qwen2.5-VL fine-tunes) output **absolute pixels in the smart-resized image** (resize factor 28). You must keep the resized dimensions and rescale. Qwen3-VL and later (Holo2, Holo3.x, Holo4 via API, UI-Venus-1.5, Fara1.5 demo) use **relative 0–1000 coordinates** (factor 32 internally), so `px = v/1000 × width_of_the_exact_image_sent`. The toolkit should then convert from image space to capture space to OS input space, explicitly handling the per-monitor scale factor and virtual-desktop origin.

### Cited Findings
- Qwen3-VL changed from Qwen2.5-VL's absolute coordinates to **relative 0–1000**, so no resized_w is needed. To convert back, divide by 1000 and multiply by the original dimension — [CSDN write-up](https://adg.csdn.net/694cf2fa5b9f5f31781a9f5b.html), [DeepWiki: Qwen3-VL 2D grounding](https://deepwiki.com/QwenLM/Qwen3-VL/5.2-spatial-understanding-and-2d-grounding) (via search summary). One paper describes a 0–999 grid (`x = floor(x·w/999)`) — [CutVerse arXiv 2605.19484](https://arxiv.org/pdf/2605.19484) (via search summary)
- Qwen2.5-VL: coordinates refer to the resized image. qwen-vl-utils uses `IMAGE_FACTOR = 28`, and the resized size can be recovered as `image_grid_thw × 14` — [CSDN write-up](https://adg.csdn.net/694cf2fa5b9f5f31781a9f5b.html) (via search summary)
- Qwen3-VL processors use patch_size 16 × merge_size 2 (= 32). Transformers' Qwen3-VL `smart_resize` uses `factor: int = 32`. A GUI benchmark paper notes screenshots are smart-resized with factor-32 rounding, and in absolute mode coordinates are in that processed space and must be rescaled to screen resolution — [Qwen3-VL tech report](https://arxiv.org/pdf/2511.21631), [vLLM forum: Qwen3-VL 2D grounding image size](https://discuss.vllm.ai/t/qwen3-vl-2d-grounding/2648) (via search summary)
- H's API: coordinates in [0,1000] normalized to the image sent. Use the dimensions of the exact bytes sent; resizing or cropping after the request causes misses — [H docs: Element localization](https://hub.hcompany.ai/models-api/element-localization)
- H's fast harness "uses smaller images", and its llama.cpp config sets `--image-min-tokens 1024` — [H docs: Local inference](https://hub.hcompany.ai/models-api/local-inference). Holo1 used 1280 tokens per 1200×1200 image — [arXiv 2506.02865](https://arxiv.org/html/2506.02865v2)
- Fara1.5-9B demo: normalized 0–1000 mapped onto a 1440×900 viewport — [Fara1.5-9B demo](https://hugging-apps-fara-computer-use-agent.hf.space/) (via search summary)
- HiDPI/OS pitfalls. macOS screenshots are in physical pixels while input uses points (Retina scale typically 2.0; reports of fractional scales). On Windows, one MCP server reports screenshots captured at logical resolution while mouse APIs (SetCursorPos) use physical pixels: a 3840×2400 display at 175% gave 2194×1371 screenshots. Non-DPI-aware processes get skewed scale ratios (e.g., 1.5002 instead of 1.5). `LogicalToPhysicalPointForPerMonitorDPI` converts regardless of caller awareness — [MS Docs: LogicalToPhysicalPointForPerMonitorDPI](https://msdn.microsoft.com/en-us/library/dn384110.aspx), [precision-desktop MCP](https://glama.ai/mcp/servers/ikoskela/precision-desktop), [pixelcoords crate](https://docs.rs/crate/pixelcoords/0.7.6) (via search summary; attribution of individual examples is approximate)
- GNOME: under legacy scaling almost everything uses physical coordinates. Screenshot APIs that used unscaled coordinates were reverted to physical — [GNOME Shell MR 1773](https://gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/1773) (via search summary)
- Some computer-use reference code pads screenshots to 16:10 before resizing, with explicit scaling between "computer" and "API" space. A PyPI tool distinguishes letterbox from stretch resizing and maps both directions — [omnitool computer.py](https://huggingface.co/spaces/bazi88/auto/blob/main/omnitool/gradio/tools/computer.py), [gui-agent-screenshot-tools](https://pypi.org/project/gui-agent-screenshot-tools/) (via search summary)
- HoloDesktop CLI currently drives only the primary display — [GitHub: holo-desktop-cli](https://github.com/hcompai/holo-desktop-cli) (via search summary)

### Inferences
- **Recommended toolkit contract:**
  1. Capture one monitor (or a window or crop) at physical pixels, recording `{monitor_id, origin_x/y in virtual desktop, scale_factor, capture_w/h}`.
  2. Optionally downscale to a target image (e.g., long side ≤1920, or ≤1280 for speed). Record `img_w/h` and any letterbox offsets, and **send exactly those bytes**.
  3. Model returns `(u,v)`. If the model is 0–1000 relative: `x_img = u/1000·img_w`. If absolute (Qwen2.5-VL family), it is relative to the model's internal smart-resized size, so either pre-resize to a multiple of 28 (factor 28, within min/max pixels) so internal and sent sizes match, or rescale by `img_w/resized_w`.
  4. `x_cap = x_img · capture_w/img_w`.
  5. `x_input = origin_x + x_cap / scale_factor` if the OS input API takes logical points (macOS CGEvent, Windows non-per-monitor-aware), or `origin_x + x_cap` if it takes physical pixels (X11/xdotool; Windows per-monitor-v2-aware process).
- On the user's X11/XFCE VM, scale is usually 1.0 and X11 uses physical pixels, so mapping reduces to step 4 plus the monitor origin. Still, keep the abstraction for macOS and Windows.
- **Zoom refinement fits naturally:** crop a region around the first hit, upscale, re-ask, then compose the crop offset back into capture space. This is the "agentic localization" or ZoomIn pass that adds 5–11 SS-Pro points in the sources above.
- Prefer models with relative 0–1000 output (Qwen3-VL+ derivatives). This removes the resized-size bookkeeping that causes most off-by-scale bugs.

### Gaps
- No official Qwen statement of default min/max pixels for Qwen3.5/3.6 processors, and no Holo4-specific image-token budget, was found. **[background, unverified]**: qwen-vl-utils for Qwen2.5-VL defaulted to min_pixels = 4·28·28 and max_pixels = 16384·28·28.
- The grounding output format of UI-Venus-1.5 and MAI-UI (0–1000 vs absolute) is not stated on the fetched pages. Both are Qwen3-VL-derived, so likely 0–1000, but check the repos' inference code.
