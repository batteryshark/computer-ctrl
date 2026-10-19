# Mac System One experiment

Exploratory evaluation scripts and an optional local D3 sidecar. The opt-in `delegate` tool is documented in [executor setup](../../docs/executor-setup.md); its acceptance suite is separate from these probes. These drivers can open apps, capture windows, launch harnesses and contact model servers. Obtain explicit target/task approval before running them. Saved measurements remain in Git history. The native fixture's Send now button records a local test outcome; it sends nothing externally.

## Environment and models

Use an isolated Python 3.12 environment. Do not install these packages into cctl's normal environment.

```sh
uv venv --python 3.12 /tmp/cctl-s1-test/venv
uv pip install --python /tmp/cctl-s1-test/venv/bin/python \
  'transformers==5.17.0' 'torch==2.14.1' 'torchvision==0.29.1' \
  pillow accelerate safetensors huggingface-hub
```

Download the complete pinned snapshots, including files required by their integrity manifests:

```sh
HF_HOME=/tmp/cctl-s1-test/hf /tmp/cctl-s1-test/venv/bin/python - <<'PY'
import json
from pathlib import Path
from huggingface_hub import snapshot_download
pins = {
    'd3-mini': '6d8971f464d6f9d4c5af7d9a8d75f3aa03be4f59',
    'd3-nano': '80820624a8170104679aa99897a6e9026eae0790',
}
models = {}
for name, revision in pins.items():
    repo = 'vllm-sr/' + name
    path = snapshot_download(repo, revision=revision)
    models[name] = {'model': repo, 'revision': revision, 'path': path}
Path('/tmp/cctl-s1-test/models.json').write_text(json.dumps(models, indent=2))
PY
```

The model loader executes the publisher's pinned inference Python with manifest verification enabled. Review that code and the model terms before loading it. MPS is explicitly selected; this recipe doesn't install flash-linear-attention or the publisher's ROCm fast path.

From the repository root, start each server in a separate terminal (stop with Ctrl-C):

```sh
PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HOME=/tmp/cctl-s1-test/hf \
  /tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/model_server.py --model d3-mini --port 18761
```

```sh
PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HOME=/tmp/cctl-s1-test/hf \
  /tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/model_server.py --model d3-nano --port 18762
```

These bind only loopback. Run GPU measurements sequentially so requests do not contend.

## Native fixture

Compile the test app from the repository root:

```sh
mkdir -p '/tmp/cctl-s1-test/cctl S1 Lab.app/Contents/MacOS'
swiftc eval/system_one_mac/Fixture.swift -o '/tmp/cctl-s1-test/cctl S1 Lab.app/Contents/MacOS/Fixture'
/tmp/cctl-s1-test/venv/bin/python - <<'PY'
import plistlib
from pathlib import Path
Path('/tmp/cctl-s1-test/cctl S1 Lab.app/Contents/Info.plist').write_bytes(plistlib.dumps({
    'CFBundleExecutable': 'Fixture', 'CFBundleIdentifier': 'local.cctl.s1-lab',
    'CFBundleName': 'cctl S1 Lab', 'CFBundlePackageType': 'APPL',
    'NSHighResolutionCapable': True,
}))
PY
```

An existing cctl installation and Cua desktop permissions are required. The runner opens each fixture, targets its exact window and closes it afterward. The app briefly raises its own window; input uses accessibility tokens rather than the shared keyboard or pointer.

```sh
/tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/run.py \
  --mode all --harness codex-desktop --output /tmp/cctl-s1-test/results.json
```

Ask a second configured harness to execute the same command with `--mode offline`, using a separate output file and its actual harness name. The label is provenance, not a substitute for invoking that harness. Results record every choice and incorrect action; compare both option orders. The offline suite includes absent/ambiguous/disabled targets, negation, already-complete states, explicit loading and an untrusted-text instruction.

For a real main-agent GUI baseline:

```sh
/tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/host_trial.py \
  --harness codex --output /tmp/cctl-s1-test/host-baseline.json
```

Screenshot probe, using the saved own-window fixture image:

```sh
/tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/image_probe.py \
  --image /REPLACE_WITH_APPROVED_SYNTHETIC_FIXTURE.png --output /tmp/cctl-s1-test/images.json
```

Interpret these as a small feasibility test: sixteen text situations, one screenshot and two variants of one form. The macro knows fixture labels. Host CLI startup is included in its timer, while decision-model loading is excluded from warm executor timings. For adoption, add held-out apps and longer workflows, lock thresholds before testing and independently verify all required state before terminal actions.

## Expanded workflow test

`Challenge.swift` is a separate fixture, leaving the initial fixture unchanged. Compile and register it as a local bundle:

```sh
mkdir -p '/tmp/cctl-s1-test/cctl S1 Challenge.app/Contents/MacOS'
swiftc eval/system_one_mac/Challenge.swift -o '/tmp/cctl-s1-test/cctl S1 Challenge.app/Contents/MacOS/Challenge'
/tmp/cctl-s1-test/venv/bin/python - <<'PY'
import plistlib
from pathlib import Path
Path('/tmp/cctl-s1-test/cctl S1 Challenge.app/Contents/Info.plist').write_bytes(plistlib.dumps({
    'CFBundleExecutable': 'Challenge', 'CFBundleIdentifier': 'local.cctl.s1-challenge',
    'CFBundleName': 'cctl S1 Challenge', 'CFBundlePackageType': 'APPL',
    'NSHighResolutionCapable': True,
}))
PY
```

Run from the repository root with the d3-mini server ready, sequentially:

```sh
mkdir -p eval/results/system-one-challenge-images
/tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/challenge.py \
  --output /tmp/cctl-s1-test/challenges.json
/tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/textedit_probe.py \
  --output /tmp/cctl-s1-test/textedit.json
```

The suite definitions and explicit predicates are written before execution. Raw and guarded modes share observed progress memory and a screenshot fallback. Guarded mode applies caller-provided predicates, restricts terminal actions and compares fresh control snapshots before dispatch. The native fixture has six completable tasks and two expected handoffs. Its notice is simulated inside the own window. The swap test deliberately changes control positions during inference. TextEdit tests use only temporary documents and window-scoped AX/menu input.

To check the second-harness path, ask another configured harness to execute:

```sh
/tmp/cctl-s1-test/venv/bin/python eval/system_one_mac/challenge.py \
  --replay /tmp/cctl-s1-test/challenges.json --harness ACTUAL_HARNESS \
  --output /tmp/cctl-s1-test/replay.json
```

Replay invokes the model on the first/last recorded decision per trial without GUI input. Images are stored under `eval/results/system-one-challenge-images` and paths are relative to the repository root; keep the model server's working directory there. This does not substitute for cross-harness live GUI testing of a future public tool.
