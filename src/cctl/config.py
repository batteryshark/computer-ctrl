"""Settings: profile, image budgets, paths. Read from ~/.config/cctl/config.toml, overridden by CCTL_* env vars."""

from __future__ import annotations

import os
import shutil
import sys
import tomllib
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
    state_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "state" / "cctl")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "cctl")

    @property
    def artifacts(self) -> Path:
        return self.cache_dir / "artifacts"

    @property
    def shell_enabled(self) -> bool:
        return self.profile == "sandbox"


def load() -> Config:
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
    }
    for key, var in env.items():
        if var in os.environ:
            value = os.environ[var]
            setattr(cfg, key, int(value) if key in ("max_dim", "zoom_dim", "grounder_image_max") else value)
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
    return cfg
