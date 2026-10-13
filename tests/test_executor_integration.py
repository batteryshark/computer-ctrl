"""Opt-in visibility and dispatch guards, without starting a desktop."""
import asyncio
import pytest

from cctl.config import Config, load
from cctl.engine import Engine
from cctl.server import build


def test_disabled_delegate_does_not_start_engine(tmp_path):
    engine = Engine(Config(state_dir=tmp_path))
    async def unexpected_start():
        pytest.fail("disabled tool started a desktop connection")
    engine.start = unexpected_start
    result = asyncio.run(engine.dispatch("delegate", {}))
    assert result.is_error and result.data["error"] == "disabled"


@pytest.mark.parametrize("enabled", [False, True])
def test_delegate_visibility_is_opt_in(enabled, tmp_path):
    server = build(Engine(Config(executor_enabled=enabled, state_dir=tmp_path)))
    # Exercise the same list callback that serves tools/list.
    response = asyncio.run(server._request_handlers["tools/list"].handler(None, None))
    assert ("delegate" in [tool.name for tool in response.tools]) == enabled


@pytest.mark.parametrize("value,want", [("true", True), ("1", True), ("false", False), ("0", False)])
def test_executor_env_boolean(monkeypatch, tmp_path, value, want):
    monkeypatch.setenv("CCTL_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("CCTL_EXECUTOR_ENABLED", value)
    assert load().executor_enabled is want


def test_invalid_executor_boolean_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("CCTL_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("CCTL_EXECUTOR_ENABLED", "perhaps")
    with pytest.raises(ValueError, match="CCTL_EXECUTOR_ENABLED"):
        load()


def test_log_does_not_store_delegate_values(tmp_path):
    from cctl.results import ToolResult
    engine = Engine(Config(state_dir=tmp_path))
    engine._log("delegate", {"window": 42, "stages": [{"secret": "PRIVATE"}],
                            "success": [{"value": "PRIVATE"}], "task": "PRIVATE", "intent": "PRIVATE"},
                ToolResult(data={"status": "completed"}), .01)
    text = (tmp_path / "events.jsonl").read_text()
    assert "PRIVATE" not in text
    assert '"window": 42' in text
