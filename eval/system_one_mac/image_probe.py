#!/usr/bin/env python3
"""Small screenshot-only selection probe on the inspected own-window fixture image."""
import argparse
import json
import random
import statistics
from pathlib import Path

from run import request

ap = argparse.ArgumentParser()
ap.add_argument("--image", required=True)
ap.add_argument("--output", required=True)
a = ap.parse_args()
image = str(Path(a.image).resolve())
cases = [
    ("save_without_send", "Select the button that saves a draft without sending it.",
     {"left": "The left of the two bottom buttons", "right": "The right of the two bottom buttons",
      "none": "The required button is not visible"}, "right"),
    ("email_field", "Select the input for an email address.",
     {"upper": "The upper text input", "lower": "The lower text input", "none": "No email input is visible"}, "lower"),
    ("checkbox_state", "Is the follow-up checkbox currently checked?",
     {"checked": "Checked", "unchecked": "Unchecked"}, "unchecked"),
    ("missing_export", "Select the Export PDF button. If it is absent, return none.",
     {"left": "The left bottom button", "right": "The right bottom button", "none": "There is no Export PDF button"}, "none"),
]
out = {"scope": "one own-window 650x432 screenshot; bounded selection, not arbitrary coordinate grounding", "models": {}}
for model in ["d3-mini", "d3-nano"]:
    rows = []
    for order in range(2):
        for case, question, criteria, gold in cases:
            items = list(criteria.items())
            random.Random(900 + order).shuffle(items)
            response, elapsed = request(model, "Inspect the attached screenshot of a test window.", dict(items),
                images=[image], instructions=question + " Use only the visible screenshot.")
            answer = response["result"]["answers"]["next"]
            rows.append({"case": case, "order": order, "expected": gold, "answer": answer,
                         "correct": answer["choice"] == gold, "roundtrip_s": elapsed,
                         "model_s": response["model_s"], "usage": response["result"]["usage"]})
            print(model, case, order, answer["choice"], answer["choice"] == gold, round(elapsed, 3), flush=True)
    out["models"][model] = {"correct": sum(r["correct"] for r in rows), "total": len(rows),
        "first_image_s": rows[0]["roundtrip_s"],
        "warm_median_s": statistics.median(r["roundtrip_s"] for r in rows[1:]), "rows": rows}
Path(a.output).write_text(json.dumps(out, indent=2))
print(json.dumps({k: {x: v[x] for x in ["correct", "total", "first_image_s", "warm_median_s"]}
                  for k, v in out["models"].items()}, indent=2))
