"""Settings: profile, image budgets, paths. Read from ~/.config/cctl/config.toml, overridden by CCTL_* env vars."""

from __future__ import annotations

import os
import shutil
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
    }
    for key, var in env.items():
        if var in os.environ:
            value = os.environ[var]
            setattr(cfg, key, int(value) if key in ("max_dim", "zoom_dim") else value)
    if cfg.profile not in PROFILES:
        raise ValueError(f"profile must be one of {PROFILES}, got {cfg.profile!r}")
    if not cfg.cua_bin:
        cfg.cua_bin = shutil.which("cua-driver") or str(Path.home() / ".local" / "bin" / "cua-driver")
    if not cfg.cua_socket:
        cfg.cua_socket = str(Path.home() / ".cache" / "cua-driver" / "cua-driver.sock")
    return cfg
