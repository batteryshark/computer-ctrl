# Optional native workflow executor

`delegate` is experimental and disabled by default. It completes a caller-defined form or wizard inside one explicit native window. The caller supplies exact accessibility labels, complete replacement values, desired checkbox states, permitted stage buttons, and observable success checks. Use `observe` to obtain those labels before delegating.

This is **host-mode only**, not available through the isolated adapter. Host mode
controls the real selected desktop and needs separate explicit approval; do not
remove `--session` from an isolated launch to try this. Enable only in a dedicated
private host config selected with `CCTL_CONFIG` and private state/cache paths:

```toml
executor_enabled = true
decision_url = "http://127.0.0.1:18761"
decision_protocol = "d3"
decision_model = "d3-mini"
```

Environment overrides are `CCTL_EXECUTOR_ENABLED`, `CCTL_DECISION_URL`, `CCTL_DECISION_PROTOCOL`, `CCTL_DECISION_MODEL`, and `CCTL_DECISION_API_KEY_ENV`. Restart an existing CLI daemon after changing its configuration; MCP reads settings when it starts. A configured endpoint receives supplied task data and accessibility content from the selected window. Choose an endpoint appropriate for that data. Keys belong in the named environment variable, never in the repository.

For an OpenAI-compatible chat endpoint, set `decision_protocol = "openai"`, `decision_url = "http://127.0.0.1:8080/v1"`, and the served model name. The adapter asks for a bounded choice index; generated text never becomes an action. For D3, `decision_url` is the exact operator-provided sidecar URL. The optional sidecar owns model loading and dependencies; cctl installs neither PyTorch nor model weights. These endpoint/model values are synthetic examples, not verified local services or deployment recommendations.

If only one action is eligible, cctl performs it without inference. When several actions are eligible, it asks the configured model to select one or return control. With no endpoint, workflows with one eligible action at a time still work; multiple choices return control.

Tool-argument example, replacing `123` with a freshly observed approved disposable
native-app window. This JSON is not an instruction to run a CLI on the current host:

```json
{
  "task": "Fill the contact form and save a draft",
  "intent": "Create the requested local contact draft",
  "window": 123,
  "stages": [{
    "fields": [
      {"label": "Full name", "value": "Morgan Lee"},
      {"label": "Email address", "value": "morgan@example.invalid"}
    ],
    "checks": [{"label": "Allow follow-up", "checked": true}],
    "button": {"label": "Save draft"}
  }],
  "success": [{"label": "Saved draft"}],
  "max_steps": 12,
  "timeout_ms": 30000
}
```

Each stage verifies every field and checkbox before clicking its optional button once. All stage targets must be visible at the start; if a button appears only after typing, put it in a separate stage. Use multiple stages for a wizard. Values are exact replacements, so include an existing prefix when appending text. An optional `role` disambiguates selectors; duplicate matches still return control. Success predicates support unique presence, exact `value`, boolean `checked`, or `absent: true`. Select a success check that proves the requested result: fields alone do not prove a save occurred. The supplied stages authorize actions; the task text guides ordering within them.

Absence checks require the engine to explicitly report a complete tree. Pinned Cua on macOS can report `elements_complete: false` even with no pending nodes and matching returned/total counts. In that case the executor accepts positive checks only when those counts also match the actual rows and `truncated` is false; absence checks return control. Use a visible confirmation for completion on macOS.

The result has `status: completed` only after fresh success checks. `status: escalated` returns the reason, verified progress, action summary and timing for the parent to inspect. Actions distinguish attempted, acknowledged, confirmed, refused and uncertain input. A timeout can leave native input in flight; cancellation does not undo an edit. Inspect the window before resuming after escalation. Step and time budgets bound each call. Missing or ambiguous controls, unsupported checkbox states, a model failure, or progress that cannot be verified return control. Transient loading is bounded by the same deadline.

This version uses native accessibility with exact nonempty labels and supplied values. Unlabeled editor areas, pixel-only canvases, browser DOM workflows, menus, free text generation and unexpected dialogs remain with the parent. It re-observes before mutation and uses fresh tokens without the generic element-refresh fallback. Observation and dispatch are separate operations, so it does not guarantee atomic protection from concurrent UI changes. Keep one controller on the target window while a call runs.

Native executor validation has been macOS-only; Linux and Windows need their own
native acceptance. The bounded form/wizard scope doesn't establish a general
desktop speedup.
