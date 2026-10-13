#!/usr/bin/env python3
"""Temporary loopback server for a pinned, unquantized d3 model. No cctl changes."""
import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import torch

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="/tmp/cctl-s1-test/models.json")
ap.add_argument("--model", choices=["d3-mini", "d3-nano"], required=True)
ap.add_argument("--port", type=int, required=True)
a = ap.parse_args()
record = json.loads(Path(a.models).read_text())[a.model]
sys.path.insert(0, record["path"])
from d3_runtime import D3  # noqa: E402: publisher code inspected before this experiment

started = time.perf_counter()
model = D3.from_pretrained(record["path"], device="mps", batch_size=1, verify="full")
torch.mps.synchronize()
metadata = {"model": record["model"], "revision": record["revision"], "device": "mps",
            "dtype": "bfloat16", "load_s": time.perf_counter() - started,
            "torch": torch.__version__, "runtime": model.runtime_info(),
            "allocated_gib": torch.mps.current_allocated_memory() / 2**30}
print(json.dumps({"ready": metadata, "port": a.port}), flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send(200, metadata)

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            torch.mps.synchronize()
            t0 = time.perf_counter()
            result = model.system_one(state=data["state"], questions=data["questions"],
                                      images=data.get("images"))
            torch.mps.synchronize()
            elapsed = time.perf_counter() - t0
            self.send(200, {"result": result, "model_s": elapsed})
            print(json.dumps({"decision_s": round(elapsed, 4), "answers": result["answers"]}), flush=True)
        except Exception as exc:
            self.send(500, {"error": type(exc).__name__, "message": str(exc)})
            print(f"ERROR {type(exc).__name__}: {exc}", flush=True)


HTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
