# Grounding sidecar: Holo on the 4090 desktop (or H's API)

`locate` asks a dedicated GUI-grounding model where something is. Any OpenAI-compatible vision endpoint works, as long as the model follows H Company's element-localization contract: given an image plus a target, it returns JSON `{"x", "y"}` scaled 0–1000 to the exact image sent. The `locate` tool appears only once cctl knows the endpoint.

## Option A: Holo4 on the Windows desktop (RTX 4090 24 GB, 96 GB RAM)

Run llama.cpp's CUDA build natively on Windows. vLLM would need WSL2. Pick one model:

- `Hcompany/Holo4-35B-A3B-GGUF` (Q4_K_M, about 21 GB): Apache-2.0, an MoE with 3B active parameters. With 24 GB of VRAM the KV cache gets tight, so move some expert layers to system RAM with `--n-cpu-moe N`. It stays fast because only 3B parameters are active.
- `Hcompany/Holo4-27B-GGUF` (Q4, about 16–17 GB): dense, CC BY-NC; fits entirely in VRAM.
- `Hcompany/Holo-3.1-35B-A3B-GGUF`: the previous generation, the one H's own llama.cpp example uses.

```powershell
llama-server -hf Hcompany/Holo4-35B-A3B-GGUF --host 0.0.0.0 --port 8080 --n-gpu-layers 999 --n-cpu-moe 8 `
  --ctx-size 16384 --flash-attn 1 --cache-type-k q8_0 --cache-type-v q8_0 --image-min-tokens 1024 `
  --alias holo4
```

Grounding requests are single-turn (one screenshot plus about 100 tokens), so 16k of context is plenty. Lower `--n-cpu-moe` until VRAM is nearly full. Put the server on your tailnet only: either bind to the Tailscale IP, or keep `0.0.0.0` and firewall port 8080 to the tailnet.

## Option B: H's hosted API

- Base URL `https://api.hcompany.ai/v1`.
- `holo3-1-35b-a3b` is free at 10 requests/min.
- `holo4-35b-a3b` costs about $0.0008 per grounding call.
- Zero data retention is the default.

You need an API key from H; cctl reads it from an environment variable.

## Point cctl at it (on the controlled machine)

`~/.config/cctl/config.toml`:

```toml
grounder_url = "http://<desktop-tailnet-name>:8080/v1"   # or https://api.hcompany.ai/v1
grounder_model = "holo4"                                 # llama.cpp alias, or "holo4-35b-a3b" on H's API
grounder_api_key_env = ""                                # e.g. "HAI_API_KEY" for H's API
grounder_image_max = 1280                                # long edge sent to the grounder
```

Restart the harness (or `pkill -f "cctl.cli serve"` for the CLI). `locate` will then show up in `cctl tools`.

## Using it

- `locate --target "the Save button in the Export dialog"` returns `{x, y, frame}` and the screenshot marked at that point. Check the mark, then `click --x … --y … --frame …`.
- `refine` (on by default) asks a second time on a crop around the first answer.
- Speech-to-text can use the same desktop: set `stt_url` to any OpenAI-compatible `/v1/audio/transcriptions` server, such as whisper.cpp's server or faster-whisper-server on the 4090.

## Where it helps (the Phase 3 eval decides whether it stays)

- Hosts with weak or no vision, such as local text-only models in pi or opencode. They use `observe`/`ocr` for structure and `locate` as their eyes.
- Dense professional UIs with tiny targets, where frontier models' own grounding drops.
- Keeping full-resolution screenshots out of an expensive host's context: the grounder sees the pixels, and the host sees only coordinates and a marked thumbnail.
