# d3-mini: changing workflows and guarded execution

Date: 2026-10-13. Continuation of the [initial Mac experiment](20261013-system-one-mac.md). Same pinned d3-mini weights, BF16/MPS runtime and Mac. No model training, production tools, public contract or account configuration changes.

**Result:** with observed progress memory and a screenshot fallback, the raw chooser handled 6/8 expected outcomes. Adding caller-supplied predicates, action filtering and preflight freshness checks handled 8/8: six completed workflows and two expected handoffs. Two separate TextEdit tasks also completed. This supports a constrained executor experiment, not a general autonomous desktop agent.

## Fixed workflow suite

All eight definitions were written before model calls. Each ran through the actual cctl MCP tools on its own temporary native window, first raw and then guarded. Save/Send/Discard in the fixture only write synthetic local artifacts. The independent app output checks all field values, checkbox states and terminal action.

| Scenario | Raw chooser | Guarded executor | Guarded time |
|---|---|---|---:|
| Correct wrong prefill; preserve unrelated reference | Completed | Completed | 6.52 s |
| Disable marketing; preserve security alerts | Completed | Completed | 9.53 s |
| Complete a two-page wizard | Completed | Completed | 15.36 s |
| Recover from unexpected notice | Completed | Completed | 15.78 s |
| Wait for a disabled Save button to become available | Completed | Completed | 7.65 s |
| Required email field absent | Expected handoff | Expected handoff after filling the available name field | 3.20 s |
| Two indistinguishable Recipient fields | Guessed and saved incomplete data | Handoff without any input | 0.18 s |
| Fields exchange positions during model inference | Saved with name missing | Rejected one stale choice, re-observed, completed | 14.36 s |

Raw completed **5/6 completable workflows**, handled **1/2 blocked workflows** correctly and committed two incorrect test artifacts overall. Guarded completed **6/6**, handled **2/2 blocked workflows** correctly and committed no incorrect test artifacts in this suite. Handoffs are not task completions.

The notice is a simulated interruption inside the fixture window: inputs disappear until Continue editing or Discard draft is selected. Position changes are deliberately triggered 80 ms after observation, during model inference. These are controlled failures, not arbitrary real-world popups or adversarial race coverage.

## What the first run taught us

The [preserved first run](20261013-system-one-mac-challenges-initial.json) handled 4/8 raw and 6/8 guarded outcomes. Both modes lost the name field after advancing the wizard because the last-three-action history no longer contained the earlier fill. Guarded mode also handed back the loading case because the current accessibility observation omitted the disabled loading indicator and disabled Save button.

Two general runner changes were then applied to **both modes**, without changing the task definitions, instructions or model weights:

1. Include values previously read back from required fields in the model's state, preserving progress across pages.
2. Capture only the own window when required values are verified but the final control is absent. Let the model inspect the screenshot for loading instead of inventing readiness from the accessibility tree.

Both modes then completed the wizard and loading case. The screenshot fallback was used twice per mode on the loading case; its [saved images](system-one-challenge-images/) contain only the synthetic fixture.

This is an iterative prototype evaluation; it is **not a blind held-out benchmark** after the controller repairs. Initial failures remain in the raw evidence rather than being replaced.

## Why the guard matters

The model receives a natural-language goal, current controls, recent actions and observed progress. The guarded executor additionally uses explicit caller-provided field/value and checkbox predicates to:

- exclude unrelated, duplicate or already-completed targets;
- exclude Send/Discard when the goal permits only local saving;
- withhold Next/Save until the required observed values and states match;
- return control when no valid progress action is available;
- re-observe immediately before input and reject a choice if the control snapshot changed.

These checks are code behavior, not learned judgment or calibrated model confidence. Some states consequently have only one eligible action; deterministic automation would also work there and should usually be preferred.

In the unguarded movement trial, the stale name-field reference placed the name in the email field. Later observations showed the name field still empty, but the model saved anyway. The toolkit's current element refresh favors same-role/same-bounds matching; the prototype's preflight prevented that observed misdispatch. Observation and dispatch remain separate calls, so this does not establish atomic protection from all UI races. No core element-identity change was made in this session.

## Existing native app: TextEdit

The guarded model chose actions on two temporary `.txt` documents in the existing TextEdit app. Source text and success predicates were supplied by the caller. The file was independently checked after saving, and only the test document was closed/deleted.

| Task | Result | Time |
|---|---|---:|
| Enter and save `Local model test — café 日本語 ✓` | Exact file content | 4.29 s |
| Preserve `Keep this prefix. ` and append `Append: Morgan Lee ✓` | Exact prefix + appended text | 4.06 s |

Each used two model decisions: text entry and File > Save. Predicate filtering allows only the appropriate mutation at each step, with escalation available. This validates the existing-app plumbing, not independent understanding of a large editor workflow.

## Cross-harness check

Codex desktop ran the live suite. OpenCode 2.0.23 with the previously available free Ling provider executed the replay command through its shell tool: the first and last model decision in each applicable trial. **29/29 choices matched**, including screenshot-backed decisions. Code-only escalations have no model call to replay. The second harness replayed recorded states; it did not repeat the native GUI trials.

No new host-model speed baseline was measured for these expanded tasks. The earlier 30.36-second Codex form baseline cannot establish a speedup for these workflows.

## Recommendation and artifacts

Keep the proposed fast executor optional and experimental. A useful interface needs an explicit target scope, supplied data, machine-checkable success conditions, budgets and an escalation result. Prefer deterministic actions when predicates leave one choice; use the model to rank genuinely ambiguous valid alternatives. Do not expose an unrestricted goal-only `delegate` based on this suite.

Next validation should cover longer tasks and more existing apps, with independently frozen cases, true recovery to the parent agent and stronger element identity before any public contract addition.

- [Final live suite](20261013-system-one-mac-challenges.json)
- [Initial live suite, preserved](20261013-system-one-mac-challenges-initial.json)
- [OpenCode decision replay](20261013-system-one-mac-challenges-opencode.json)
- [TextEdit results](20261013-system-one-mac-textedit.json)
- [Scripts and reproduction](../system_one_mac/README.md)
