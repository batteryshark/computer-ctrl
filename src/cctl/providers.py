"""Select the control implementation once, before any desktop discovery."""
from .config import Config


def create_engine(cfg: Config):
    if cfg.session:
        from .isolated import IsolatedEngine
        return IsolatedEngine(cfg)
    from .engine import Engine
    return Engine(cfg)
