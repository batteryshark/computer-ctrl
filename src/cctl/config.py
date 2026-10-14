"""Settings: profile, image budgets, paths. Read from ~/.config/cctl/config.toml, overridden by CCTL_* env vars."""

from __future__ import annotations

import os
import shutil
import sys
import tomllib
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PROFILES = ("sandbox", "personal")


@dataclass
class Config:
    # sandbox: a disposable machine the agent fully controls (shell tool on).
    # personal: someone's own machine (shell tool off).
    profile: str = "sandbox"
    max_dim: int = 1568            # long edge of screenshots sent to the model
    zoom_dim: int = 1024           # long edge of zoom images
    input_backend: str = "auto"    # auto | xdotool | cua
    cua_bin: str = ""
    cua_socket: str = ""
    cua_http_url: str = ""         # loopback HTTP MCP of the Cua daemon (Windows over SSH); empty = stdio
    cua_http_token_file: str = ""
    stt_url: str = ""              # OpenAI-compatible base URL (…/v1); empty = local faster-whisper if installed
    stt_model: str = "small"
    stt_api_key_env: str = ""      # name of the env var holding the endpoint's API key
    grounder_url: str = ""         # OpenAI-compatible base URL (…/v1) of a GUI grounding model; empty hides `locate`
    grounder_model: str = ""
    grounder_api_key_env: str = ""
    grounder_image_max: int = 1280
    executor_enabled: bool = False  # opt-in experimental native form/wizard executor
    decision_url: str = ""         # optional choice-model endpoint; no model dependencies in cctl
    decision_model: str = ""
    decision_protocol: str = "openai"  # openai chat/completions | d3 system_one sidecar
    decision_api_key_env: str = ""
    # Remote targets for `cctl --host`: {"user@host": {"ssh_args": [...], "remote_bin": "...", "os": "windows"}}
    hosts: dict = field(default_factory=dict)
    session: str = ""              # optional named isolated target; empty preserves host control
    sessions: dict = field(default_factory=dict)
    state_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "state" / "cctl")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "cctl")

    @property
    def artifacts(self) -> Path:
        return self.cache_dir / "artifacts"

    @property
    def shell_enabled(self) -> bool:
        return self.profile == "sandbox"

    @property
    def session_options(self) -> dict:
        if not self.session or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", self.session):
            raise ValueError("session must be a configured name containing letters, digits, - or _")
        entry = self.sessions.get(self.session)
        if not isinstance(entry, dict):
            raise ValueError(f"isolated session {self.session!r} is not configured; no host fallback")
        command = entry.get("command", ["deskhelper"])
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError("session command must be a nonempty argument array")
        name = entry.get("id", self.session)
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
            raise ValueError("invalid companion session id")
        acquire = entry.get("acquire", "start")
        if acquire not in ("start", "attach"):
            raise ValueError("session acquire must be start or attach")
        env = entry.get("env", {})
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise ValueError("session env must contain string values")
        extra = entry.get("acquire_args", [])
        if not isinstance(extra, list) or not all(isinstance(x, str) for x in extra):
            raise ValueError("session acquire_args must be an argument array")
        return dict(entry, command=command, id=name, acquire=acquire, env=env, acquire_args=extra)

    def isolate_paths(self) -> None:
        """A configured target cannot reuse the host's daemon, frames or profiles."""
        entry = self.session_options
        identity = json.dumps([self.session, entry], sort_keys=True).encode()
        suffix = hashlib.sha256(identity).hexdigest()[:16]
        self.state_dir = self.state_dir / "sessions" / suffix
        self.cache_dir = self.cache_dir / "sessions" / suffix


def load(*, select_session: bool = True) -> Config:
    cfg = Config()
    path = Path(os.environ.get("CCTL_CONFIG", Path.home() / ".config" / "cctl" / "config.toml"))
    if path.is_file():
        data = tomllib.loads(path.read_text())
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, Path(value) if key.endswith("_dir") else value)
    env = {
        "profile": "CCTL_PROFILE", "max_dim": "CCTL_MAX_DIM", "zoom_dim": "CCTL_ZOOM_DIM",
        "input_backend": "CCTL_INPUT_BACKEND", "cua_bin": "CCTL_CUA_BIN", "cua_socket": "CCTL_CUA_SOCKET",
        "cua_http_url": "CCTL_CUA_HTTP_URL", "cua_http_token_file": "CCTL_CUA_HTTP_TOKEN_FILE",
        "stt_url": "CCTL_STT_URL", "stt_model": "CCTL_STT_MODEL", "stt_api_key_env": "CCTL_STT_API_KEY_ENV",
        "grounder_url": "CCTL_GROUNDER_URL", "grounder_model": "CCTL_GROUNDER_MODEL",
        "grounder_api_key_env": "CCTL_GROUNDER_API_KEY_ENV", "grounder_image_max": "CCTL_GROUNDER_IMAGE_MAX",
        "executor_enabled": "CCTL_EXECUTOR_ENABLED", "decision_url": "CCTL_DECISION_URL",
        "decision_model": "CCTL_DECISION_MODEL", "decision_protocol": "CCTL_DECISION_PROTOCOL",
        "decision_api_key_env": "CCTL_DECISION_API_KEY_ENV",
        "session": "CCTL_SESSION",
    }
    for key, var in env.items():
        if var in os.environ:
            value = os.environ[var]
            if key == "executor_enabled":
                if value.lower() not in ("true", "false", "1", "0"):
                    raise ValueError("CCTL_EXECUTOR_ENABLED must be true, false, 1 or 0")
                cfg.executor_enabled = value.lower() in ("true", "1")
                continue
            setattr(cfg, key, int(value) if key in ("max_dim", "zoom_dim", "grounder_image_max") else value)
    if not isinstance(cfg.executor_enabled, bool):
        raise ValueError("executor_enabled must be a boolean")
    if cfg.decision_protocol not in ("openai", "d3"):
        raise ValueError("decision_protocol must be openai or d3")
    if cfg.profile not in PROFILES:
        raise ValueError(f"profile must be one of {PROFILES}, got {cfg.profile!r}")
    if not cfg.cua_bin:
        cfg.cua_bin = shutil.which("cua-driver") or str(Path.home() / ".local" / "bin" / "cua-driver")
        if sys.platform == "win32" and not Path(cfg.cua_bin).exists():
            found = sorted((Path.home() / ".cua-driver").glob("*/*/cua-driver.exe"))
            if found:
                cfg.cua_bin = str(found[-1])
    if not cfg.cua_socket:
        cfg.cua_socket = str(Path.home() / ".cache" / "cua-driver" / "cua-driver.sock")
    if cfg.session and select_session:
        cfg.isolate_paths()
    return cfg
