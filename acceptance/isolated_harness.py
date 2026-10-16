#!/usr/bin/env python3
"""Run a real harness against one configured isolated MCP target.

The caller prepares an empty owned document and independently checks its contents
and session event log afterwards. This runner never treats model DONE as a pass.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import time


def opencode_config(command, mode):
    """v1 --pure and v2 --standalone use different MCP/permission schemas."""
    if mode == "pure":
        return {"$schema": "https://opencode.ai/config.json",
                "mcp": {"isolated": {"type": "local", "command": command, "timeout": 120000}},
                "permission": {"bash": "deny", "edit": "deny", "write": "deny"}}
    # https://opencode.ai/v2/docs/mcp-servers and /permissions
    return {"$schema": "https://opencode.ai/config.json",
            "mcp": {"servers": {"isolated": {"type": "local", "command": command,
                "codemode": False, "timeout": {"startup": 30000, "catalog": 30000, "execution": 120000}}}},
            "permissions": [{"action": "*", "resource": "*", "effect": "deny"},
                            {"action": "isolated_*", "resource": "*", "effect": "allow"}]}


def start_opencode_server(executable, out, env, command):
    """Register v2 MCP in an owned server, scoped to this exact run directory."""
    env["OPENCODE_PASSWORD"] = secrets.token_urlsafe(32)
    catalog_path = out / "mcp-tool-catalog.json"
    guarded_command = [sys.executable, str(Path(__file__).resolve()), "--mcp-catalog-proxy",
                       str(catalog_path), json.dumps(command)]
    private_config = opencode_config(guarded_command, "standalone")
    (out / "opencode.json").write_text(json.dumps(private_config, indent=2))
    log_path = out / "server.log"
    with log_path.open("w") as log:
        os.chmod(log_path, 0o600)
        proc = subprocess.Popen([executable, "serve", "--hostname", "127.0.0.1", "--port", "0"],
            cwd=out, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt")
    metadata = {"pid": proc.pid, "started_at": time.time(), "owned": True}
    (out / "server-process.json").write_text(json.dumps(metadata, indent=2))
    try:
        for _ in range(100):
            match = re.search(r"http://127\.0\.0\.1:\d+", log_path.read_text())
            if match:
                break
            if proc.poll() is not None:
                raise RuntimeError("Owned OpenCode server exited during startup")
            time.sleep(.1)
        else:
            raise RuntimeError("Owned OpenCode server did not publish its loopback URL")
        url = match.group(0)
        metadata["url"] = url
        (out / "server-process.json").write_text(json.dumps(metadata, indent=2))

        def api(args):
            result = subprocess.run([executable, "api", "--server", url] + args,
                cwd=out, env=env, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise RuntimeError("Owned OpenCode MCP registration API failed")
            return json.loads(result.stdout) if result.stdout.strip() else None

        config = private_config["mcp"]["servers"]["isolated"]
        api(["experimental.mcp.add", "--param", "server=isolated", "--data", json.dumps({"config": config})])
        catalog = None
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            catalog = api(["mcp.list"])
            servers = catalog.get("data", [])
            if len(servers) == 1 and servers[0].get("name") == "isolated":
                state = servers[0].get("status", {}).get("status")
                if state == "connected":
                    (out / "mcp-registration.json").write_text(json.dumps(catalog, indent=2))
                    if catalog_path.exists():
                        observed = json.loads(catalog_path.read_text())
                        required = {"apps", "screenshot", "click", "type_text", "key", "ocr"}
                        if required <= set(observed.get("tools", [])) and not observed.get("error"):
                            return proc, url
                elif state not in ("pending", "connecting"):
                    break
            time.sleep(.25)
        (out / "mcp-registration.json").write_text(json.dumps(catalog, indent=2))
        raise RuntimeError("The owned server did not receive the required isolated MCP tool catalog")
    except BaseException:
        stop_opencode_server(proc, out, env)
        raise


def stop_opencode_server(proc, out, env):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait()
    # The process group belongs to this test; remove any remaining MCP child too.
    if os.name != "nt":
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    log = out / "server.log"
    if log.exists():
        log.write_text(log.read_text().replace(env["OPENCODE_PASSWORD"], "[redacted ephemeral password]"))
    (out / "server-cleanup.json").write_text(json.dumps({"pid": proc.pid, "exit_code": proc.returncode}))


def mcp_catalog_proxy(path, command):
    """Transparent stdio; retain only tools/list metadata, never tool payloads."""
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr.buffer)
    requests = set()

    def forward_requests():
        try:
            for line in sys.stdin.buffer:
                try:
                    value = json.loads(line)
                    if value.get("method") == "tools/list" and "id" in value:
                        requests.add(value["id"])
                except (ValueError, TypeError):
                    pass
                proc.stdin.write(line)
                proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            proc.stdin.close()

    threading.Thread(target=forward_requests, daemon=True).start()
    try:
        for line in proc.stdout:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            try:
                value = json.loads(line)
                if value.get("id") in requests:
                    requests.discard(value["id"])
                    result = {"received_at": time.time(), "forwarded": True,
                              "tools": [tool["name"] for tool in value.get("result", {}).get("tools", [])],
                              "error": "tools/list failed" if "error" in value else None}
                    temporary = path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(result, indent=2))
                    temporary.replace(path)
            except (ValueError, TypeError, KeyError):
                pass
        return proc.wait()
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("harness", choices=["codex", "opencode", "claude"])
    p.add_argument("--command-json", required=True, help="MCP command array, including mcp argument")
    p.add_argument("--app-json", required=True, help="Arguments for cctl apps(action=launch)")
    p.add_argument("--marker", required=True)
    p.add_argument("--save-key", default="ctrl+s")
    p.add_argument("--replace-existing", action="store_true", help="Select all in the editor before typing")
    p.add_argument("--select-all-key", default="ctrl+a")
    p.add_argument("--hold-ms", type=int, default=0, help="Optional bounded held-key acceptance before saving (1–5000 ms)")
    p.add_argument("--hold-key", default="Left", help="Held key/chord; default Left leaves document text unchanged")
    p.add_argument("--output", required=True)
    p.add_argument("--executable", help="Installed harness executable; model settings are inherited")
    p.add_argument("--model", help="Optional per-run model selection; never changes user configuration")
    p.add_argument("--opencode-mode", choices=["standalone", "pure"], default="standalone",
                   help="Use standalone on v2, pure on older v1 without external plugins")
    p.add_argument("--opencode-owned-server", action="store_true",
                   help="v2 only: own a loopback server and register isolated MCP through its runtime API")
    a = p.parse_args()
    if not 0 <= a.hold_ms <= 5000:
        p.error("--hold-ms must be 0–5000")
    if a.opencode_owned_server and (a.harness != "opencode" or a.opencode_mode != "standalone"):
        p.error("--opencode-owned-server requires opencode standalone mode")
    command, app = json.loads(a.command_json), json.loads(a.app_json)
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    selection = (f"First use key keys={a.select_all_key} to select the prepared document contents. "
                 if a.replace_existing else "")
    held = (f"Before saving, call key once with keys={a.hold_key} and hold_ms={a.hold_ms}; require released=true in its response. "
            if a.hold_ms else "")
    prompt = f"""This is an authorized isolated-desktop acceptance test. Use ONLY the MCP tools from the server named isolated. Do not use shell, file-writing, other computer tools or other MCP servers. The isolated tools never target the human desktop.
1. Launch the prepared ordinary text editor document with isolated apps using exactly these arguments: {json.dumps(app, ensure_ascii=False)}.
2. Take an isolated screenshot. Click inside the editable document using coordinates from that screenshot (one left click; use its frame ID).
3. {selection}Type exactly the following marker once using type_text mode=auto: {a.marker}
4. {held}Save with key keys={a.save_key}. Take another screenshot and verify the document displays the marker. OCR is available if images are inaccessible. Do not close the document or stop the session.
Reply DONE only after completing these operations. If a tool fails or you cannot identify the document, report the problem; do not bypass the isolated tools.
"""
    if a.harness == "codex":
        argv = [a.executable or "codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                "-c", "mcp_servers.isolated.command=" + json.dumps(command[0]),
                "-c", "mcp_servers.isolated.args=" + json.dumps(command[1:]),
                "-c", "mcp_servers.isolated.required=true",
                "-c", "mcp_servers.isolated.startup_timeout_sec=60",
                "-c", "mcp_servers.isolated.tool_timeout_sec=120"]
    elif a.harness == "opencode":
        config = opencode_config(command, a.opencode_mode)
        (out / "opencode.json").write_text(json.dumps(config, indent=2))
        argv = [a.executable or "opencode", "run", "--" + a.opencode_mode, "--auto", "--format", "json"]
    else:
        config = {"mcpServers": {"isolated": {"command": command[0], "args": command[1:]}}}
        config_path = out / "mcp.json"
        config_path.write_text(json.dumps(config, indent=2))
        allowed = ",".join("mcp__isolated__" + name for name in
                           ("apps", "screenshot", "click", "type_text", "key", "ocr"))
        argv = [a.executable or "claude", "--print", "--no-session-persistence", "--no-chrome",
                "--strict-mcp-config", "--mcp-config", str(config_path), "--tools", "",
                "--allowedTools", allowed, "--permission-mode", "dontAsk",
                "--disable-slash-commands", "--output-format", "stream-json", "--verbose"]
    if a.model:
        argv += ["--model", a.model]
    argv.append(prompt)
    began = time.time()
    (out / "request.json").write_text(json.dumps({"harness": a.harness, "mcp_command": command,
        "app": app, "marker": a.marker, "model": a.model, "save_key": a.save_key,
        "replace_existing": a.replace_existing, "select_all_key": a.select_all_key,
        "hold_ms": a.hold_ms, "hold_key": a.hold_key,
        "started_at": began}, indent=2))
    env = dict(os.environ, PWD=str(out))
    if a.harness == "opencode":
        env["OPENCODE_CONFIG"] = str(out / "opencode.json")
    owned_server = None
    try:
        if a.opencode_owned_server:
            owned_server, url = start_opencode_server(a.executable or "opencode", out, env, command)
            argv[argv.index("--standalone"):argv.index("--standalone") + 1] = ["--server", url]
        with (out / "transcript.txt").open("w") as log:
            proc = subprocess.Popen(argv, cwd=out, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    env=env, start_new_session=os.name != "nt")
            (out / "process.json").write_text(json.dumps({"pid": proc.pid, "started_at": began}))
            try:
                code = proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
                code = 124
    finally:
        if owned_server:
            stop_opencode_server(owned_server, out, env)
    result = {"harness": a.harness, "exit_code": code, "elapsed_s": round(time.time() - began, 2),
              "acceptance": "unverified: independently inspect saved document, tool calls and host/session invariants"}
    (out / "execution.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--mcp-catalog-proxy":
        raise SystemExit(mcp_catalog_proxy(Path(sys.argv[2]), json.loads(sys.argv[3])))
    raise SystemExit(main())
