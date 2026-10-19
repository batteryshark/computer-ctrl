# Optional grounding endpoint (host mode only)

`locate` sends an image and target description to an OpenAI-compatible vision
endpoint. The model must return a point as JSON `{"x": 500, "y": 250}` on a
0–1000 scale relative to the exact submitted image. It is hidden without a
configured endpoint and unavailable in the isolated adapter.

Configure a dedicated private host-mode config, not a live shared default:

```toml
profile = "personal"
grounder_url = "http://127.0.0.1:8080/v1" # placeholder: only an approved local endpoint
grounder_model = "operator-selected-model"
grounder_api_key_env = "CCTL_DEMO_GROUNDER_KEY"
grounder_image_max = 1280
```

The key belongs in a deliberately allowlisted environment variable, not source.
This example does not start or authorize any endpoint. No GPU, model, hosted API
pricing, retention policy or weight license is verified here. Use operator-provided,
rights-cleared resources and consult their current terms. Local binding is not
authentication; do not expose an unauthenticated inference server publicly.

After separately approved setup, reload only the identified owned controller;
do not pattern-kill processes. `locate` returns coordinates, a frame and a marked
image. Inspect the mark before any click. Default refinement makes a second
request on a crop. Screen contents can be private and model coordinates can be
wrong; neither the endpoint nor its response grants permission to act.

Speech-to-text is independent: `stt_url` selects an OpenAI-compatible transcription
endpoint, otherwise the optional `stt` extra can use local faster-whisper. Neither
endpoint nor weights are included or launched here. Host capture requires its own
explicit approval; isolated mode does not gain grounding/audio by setting these.
