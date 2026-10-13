# System One models on the Mac — 2026-10-13

**Result:** d3-mini is a promising optional executor backend. Both open-weight models run locally on Apple GPU, but neither is a reliable general desktop controller on this evidence. No production tools, contract, dependencies or configuration were changed.

## Setup

- Apple M5 Max, 128 GB unified memory, macOS 27.0.1.
- Isolated Python 3.12.15 environment; PyTorch 2.14.1, Transformers 5.17.0, torchvision 0.29.1, BF16 weights, FP32 decision readout, MPS device. Full publisher manifest verification passed.
- [d3-mini](https://huggingface.co/vllm-sr/d3-mini): `6d8971f464d6f9d4c5af7d9a8d75f3aa03be4f59` (4B class).
- [d3-nano](https://huggingface.co/vllm-sr/d3-nano): `80820624a8170104679aa99897a6e9026eae0790` (2B class).
- Publisher ROCm fast path was unavailable; PyTorch reference convolution/Gated DeltaNet kernels ran. MPS synchronization brackets the measured inference. These are Mac measurements, not the publisher's MI325X timings.
- Models were already loaded for task timings. Initial load + full integrity verification took 5.89 s mini / 4.39 s nano. First short decisions were 1.35 s / 1.87 s. Both model servers were stopped after testing; weights and the isolated runtime remain in `/tmp/cctl-s1-test` for reuse.

## Measured results

| Probe | d3-mini | d3-nano |
|---|---:|---:|
| Text decisions, both harnesses | 28/32 (87.5%) | 26/32 (81.25%) |
| Warm text median, Codex desktop / OpenCode repeat | 394 / 319 ms | 152 / 131 ms |
| Warm text p95, Codex desktop / OpenCode repeat | 651 / 329 ms | 409 / 135 ms |
| Screenshot decisions | 8/8 | 8/8 |
| Warm screenshot median | 800 ms | 343 ms |
| First screenshot request | 2.15 s | 1.62 s |
| Native forms completed correctly | 2/2 | 1/2 |
| Canonical form, complete task | 12.81 s | 11.17 s |
| Synonym-label form, complete task | 12.83 s | Failed: skipped required follow-up; saved after 7.51 s |

The text probe has **16 hand-authored situations in two option orders**, not 32 independent tasks. Screenshot testing has **four questions in two option orders on one 650×432 screenshot**, not eight independent screens. No training or tuning used these cases.

The native fixture has two text fields, a checkbox and Save draft / Send now decoy buttons. The second variant uses Full name, Electronic mail and Contact me with updates. Source values are randomized synthetic data. The model receives only the current test window's controls and supplied values, then selects one complete action from a newly enumerated, shuffled candidate table. `cctl` acts through actual accessibility element tokens. An independent JSON artifact from the app verifies exact field values, follow-up state and the saved-vs-sent action. Failures are counted, not silently repaired.

## Baselines and harness evidence

- Deterministic macro: 2/2 native forms, 7.06 / 7.25 s. This explicitly scripted fixture baseline matches known labels; it is an automation lower bound, not a general semantic agent.
- Codex CLI 0.162.1, gpt-6.1-sol, reasoning effort none: synonym form passed in **30.36 s**, six successful cctl calls (observe, two type_text, two click, observe). This timer includes CLI/MCP startup and host-model turns; local executor timers exclude model loading and fixture launch. The observed ratio of roughly 2.4× is a small warm-executor trial, not a general speedup estimate.
- Codex desktop ran the full local suite. OpenCode 2.0.23 with `opencode/ling-3.1-flash-free` executed the identical offline acceptance command through its shell tool. Both produced identical choices on all 64 decision calls across the two models. The lower latency on the repeat is compatible with warm runtime/shape caches and changing ordinary desktop load; it is not a harness speed comparison.
- Claude Code could not run due to its session usage limit. OpenCode's default provider returned a billing configuration error; the free provider completed the check. No account settings or credentials were changed.
- The first Codex CLI attempt refused MCP calls under its default never-approve exec policy. Automatic approval review enabled the actual GUI run. Its first grader missed the events because `CCTL_RUN_TAG` was not inherited by the MCP server; matching the unique randomized input values recovered the exact event run. Future runs explicitly configure the MCP environment. No second GUI run was needed for that grader correction.

## Failures and implication

Both models chose Send now when Save draft was disabled, and guessed an unlabeled field instead of escalating. Nano additionally mishandled a negated checkbox goal. All were consistent across option orderings.

On the live synonym form, nano saved the draft with follow-up still off. That wrong selection had confidence **0.830**, so confidence gating alone is insufficient. In the small text probe, a post-hoc 0.8 threshold retained 22/32 correct choices for each model; this is not a calibrated deployment threshold and did not catch the live failure.

Recommendation: continue with d3-mini as an optional, bounded selector using fresh a11y/DOM candidates, code-enforced action preconditions and explicit escalation. Use deterministic batching when the steps are already known. Evaluate larger held-out native/browser workflows and failure recovery before adding `delegate` to the public contract. Training a new model remains unnecessary at this stage.

## Artifacts

- [Full text + live results](20261013-system-one-mac-codex.json)
- [OpenCode repeat](20261013-system-one-mac-opencode.json)
- [Screenshot results](20261013-system-one-mac-images.json)
- [Main-agent baseline and GUI event evidence](20261013-system-one-mac-host-codex.json)
- [Own-window screenshot](20261013-system-one-mac-fixture.png)
- [Reproduction scripts](../system_one_mac/README.md)
