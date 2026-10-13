"""Behavioral tests for bounded delegation, including adversarial state changes."""

import asyncio
import copy
import pytest

from cctl.config import Config
from cctl.cua_client import CuaError, CuaResult
from cctl.executor import Executor
from cctl.results import ToolError


def control(label, role="AXTextField", value="", **extra):
    return {"label": label, "role": role, "value": value, "enabled": True,
            "frame": {"x": 10, "y": 10, "w": 80, "h": 25}, **extra}


class Desktop:
    """Small observable app, with independent state and changing element tokens."""

    def __init__(self, controls, *, ignore_input=False, stale_once=False):
        self.controls = copy.deepcopy(controls)
        self.snapshots = 0
        self.tokens = {}
        self.calls = []
        self.mutations = []
        self.ignore_input = ignore_input
        self.stale_once = stale_once
        self.saved = False

    async def call(self, tool, args=None, **_):
        args = dict(args or {})
        self.calls.append((tool, args))
        if tool == "get_window_state":
            self.snapshots += 1
            self.tokens = {f"s{self.snapshots}:{i}": item for i, item in enumerate(self.controls)}
            elements = [{**copy.deepcopy(item), "element_token": token} for token, item in self.tokens.items()]
            return CuaResult(structured={"pid": 7, "window_id": 42, "elements": elements,
                                         "elements_complete": True, "truncated": False,
                                         "nodes_pending": 0, "returned_element_count": len(elements),
                                         "total_element_count": len(elements)})
        if tool not in ("set_value", "click"):
            raise AssertionError(f"executor used an unexpected capability: {tool}")
        if self.stale_once:
            self.stale_once = False
            raise CuaError(tool, "old token", {"refusal": {"code": "stale_element_token"}})
        token = args.get("element_token")
        if token not in self.tokens:
            raise CuaError(tool, "old token", {"refusal": {"code": "stale_element_token"}})
        item = self.tokens[token]
        self.mutations.append((tool, item["label"], args))
        if not self.ignore_input:
            if tool == "set_value":
                item["value"] = args["value"]
            elif item["role"] == "AXCheckBox":
                item["checked"] = not item.get("checked", False)
                item["value"] = "1" if item["checked"] else "0"
            elif item["label"] == "Save draft":
                self.saved = True
                self.controls[:] = [control("Saved draft", "AXButton")]
        return CuaResult(structured={"ok": True, "summary": "done"})


class FakeEngine:
    def __init__(self, controls, **kwargs):
        self.cfg = Config()
        self.cua = Desktop(controls, **kwargs)
        self.logs = []
        self.pid = 7

    async def _window(self, window):
        assert window == 42
        return {"window_id": 42, "id": 42, "pid": self.pid, "title": "Own test app"}

    def _log(self, tool, args, result, elapsed):
        self.logs.append((tool, args, result))


class Chooser:
    def __init__(self, answer=0, before=None, error=None):
        self.answer = answer
        self.before = before
        self.error = error
        self.calls = []

    async def choose(self, task, state, choices, timeout):
        self.calls.append({"task": task, "state": state, "choices": choices, "timeout": timeout})
        if self.before:
            self.before(len(self.calls))
        if self.error:
            raise self.error
        return self.answer


def run(engine, stages, success, chooser=None, **options):
    result = asyncio.run(Executor(engine, chooser=chooser or Chooser()).run(
        task="Fill supplied test data and save locally", window=42, stages=stages,
        success=success, intent="Only edit the own test window", **options))
    assert not result.is_error
    return result.data


def fields_stage(**fields):
    return {"fields": [{"label": label, "value": value} for label, value in fields.items()]}


def test_single_eligible_action_is_deterministic_and_read_back():
    engine = FakeEngine([control("Full name")])
    chooser = Chooser(error=AssertionError("deterministic action called a model"))
    result = run(engine, [fields_stage(**{"Full name": "Avery — 日本語 ✓"})],
                 [{"label": "Full name", "value": "Avery — 日本語 ✓"}], chooser)
    assert result["status"] == "completed"
    assert result["model_calls"] == 0 and chooser.calls == []
    assert len(engine.cua.mutations) == 1
    assert engine.cua.controls[0]["value"] == "Avery — 日本語 ✓"
    assert engine.cua.snapshots >= 2


def test_model_can_order_only_authorized_changes_and_commit_is_gated():
    engine = FakeEngine([control("Full name"), control("Email address"),
                         control("Internal reference", value="KEEP-42"),
                         control("Send now", "AXButton"), control("Save draft", "AXButton")])
    chooser = Chooser(answer=1)
    stage = fields_stage(**{"Full name": "Avery", "Email address": "a@example.invalid"})
    stage["button"] = {"label": "Save draft"}
    result = run(engine, [stage], [{"label": "Saved draft"}], chooser)
    assert result["status"] == "completed" and engine.cua.saved
    assert [label for _, label, _ in engine.cua.mutations] == ["Email address", "Full name", "Save draft"]
    assert result["model_calls"] == len(chooser.calls) == 1
    assert len(chooser.calls[0]["choices"]) == 2
    assert not any("Send now" in choice or "KEEP-42" in choice for choice in chooser.calls[0]["choices"])


@pytest.mark.parametrize("controls", [
    [control("Full name")],
    [control("Full name"), control("Email address"), control("Email address")],
])
def test_missing_or_ambiguous_required_target_hands_back_without_partial_edits(controls):
    engine = FakeEngine(controls)
    result = run(engine, [fields_stage(**{"Full name": "Avery", "Email address": "a@example.invalid"})],
                 [{"label": "Saved draft"}])
    assert result["status"] == "escalated"
    assert engine.cua.mutations == [] and result["actions"] == []


@pytest.mark.parametrize("answer", [None, -1, 999, True, "0"])
def test_invalid_model_choice_never_becomes_a_mutation(answer):
    engine = FakeEngine([control("Full name"), control("Email address")])
    result = run(engine, [fields_stage(**{"Full name": "Avery", "Email address": "a@example.invalid"})],
                 [{"label": "Saved draft"}], Chooser(answer=answer))
    assert result["status"] == "escalated"
    assert engine.cua.mutations == []


def test_model_outage_returns_observed_state_without_fallback_clicks():
    engine = FakeEngine([control("Full name"), control("Email address")])
    result = run(engine, [fields_stage(**{"Full name": "Avery", "Email address": "a@example.invalid"})],
                 [{"label": "Saved draft"}], Chooser(error=ToolError("decision_unavailable", "offline")))
    assert result["status"] == "escalated"
    assert engine.cua.mutations == []


def test_reflow_during_inference_discards_choice_and_uses_new_tokens():
    engine = FakeEngine([control("Full name", frame={"x": 10, "y": 10, "w": 80, "h": 25}),
                         control("Email address", frame={"x": 10, "y": 50, "w": 80, "h": 25})])

    def swap(call):
        if call == 1:
            a, b = engine.cua.controls
            a["frame"], b["frame"] = b["frame"], a["frame"]

    chooser = Chooser(before=swap)
    result = run(engine, [fields_stage(**{"Full name": "Avery", "Email address": "a@example.invalid"})],
                 [{"label": "Full name", "value": "Avery"},
                  {"label": "Email address", "value": "a@example.invalid"}], chooser)
    assert result["status"] == "completed" and result["stale_rejections"] >= 1
    assert len(chooser.calls) == 2
    assert [(item["label"], item["value"]) for item in engine.cua.controls] == [
        ("Full name", "Avery"), ("Email address", "a@example.invalid")]
    assert len(engine.cua.mutations) == 2


def test_cua_stale_refusal_reobserves_instead_of_retrying_stale_token():
    engine = FakeEngine([control("Full name")], stale_once=True)
    result = run(engine, [fields_stage(**{"Full name": "Avery"})], [{"label": "Full name", "value": "Avery"}])
    assert result["status"] == "completed" and result["stale_rejections"] >= 1
    attempts = [args["element_token"] for tool, args in engine.cua.calls if tool == "set_value"]
    assert len(attempts) == 2 and attempts[0] != attempts[1]
    assert len(engine.cua.mutations) == 1


def test_window_id_reuse_by_another_process_stops_before_mutation():
    engine = FakeEngine([control("Full name"), control("Email address")])
    chooser = Chooser(before=lambda _: setattr(engine, "pid", 999))
    result = run(engine, [fields_stage(**{"Full name": "Avery", "Email address": "a@example.invalid"})],
                 [{"label": "Saved draft"}], chooser)
    assert result["status"] == "escalated"
    assert engine.cua.mutations == []


def test_step_budget_does_not_report_field_edits_as_committed_work():
    engine = FakeEngine([control("Full name"), control("Save draft", "AXButton")])
    stage = fields_stage(**{"Full name": "Avery"})
    stage["button"] = {"label": "Save draft"}
    result = run(engine, [stage], [{"label": "Saved draft"}], max_steps=1)
    assert result["status"] == "escalated" and not engine.cua.saved
    assert [label for _, label, _ in engine.cua.mutations] == ["Full name"]


def test_disabled_required_target_waits_within_step_budget_without_input():
    engine = FakeEngine([control("Full name", enabled=False)])
    result = run(engine, [fields_stage(**{"Full name": "Avery"})],
                 [{"label": "Full name", "value": "Avery"}], max_steps=2)
    assert result["status"] == "escalated" and result["steps"] <= 2
    assert engine.cua.mutations == []


def test_a_success_label_already_present_does_not_skip_required_commit():
    engine = FakeEngine([control("Full name", value="Avery"), control("Saved draft", "AXButton"),
                         control("Save draft", "AXButton")])
    stage = fields_stage(**{"Full name": "Avery"})
    stage["button"] = {"label": "Save draft"}
    result = run(engine, [stage], [{"label": "Saved draft"}])
    assert result["status"] == "completed" and engine.cua.saved
    assert [label for _, label, _ in engine.cua.mutations] == ["Save draft"]


def test_silent_failed_typing_cannot_unlock_commit():
    engine = FakeEngine([control("Full name"), control("Save draft", "AXButton")], ignore_input=True)
    stage = fields_stage(**{"Full name": "Avery"})
    stage["button"] = {"label": "Save draft"}
    result = run(engine, [stage], [{"label": "Saved draft"}], max_steps=6)
    assert result["status"] == "escalated" and not engine.cua.saved
    assert all(label != "Save draft" for _, label, _ in engine.cua.mutations)


def test_checkbox_false_is_an_explicit_requirement_not_a_truthy_skip():
    engine = FakeEngine([control("Marketing messages", "AXCheckBox", "1", checked=True),
                         control("Security alerts", "AXCheckBox", "1", checked=True)])
    result = run(engine, [{"checks": [{"label": "Marketing messages", "checked": False},
                                      {"label": "Security alerts", "checked": True}]}],
                 [{"label": "Marketing messages", "checked": False},
                  {"label": "Security alerts", "checked": True}])
    assert result["status"] == "completed"
    assert [label for _, label, _ in engine.cua.mutations] == ["Marketing messages"]


def test_empty_success_cannot_claim_completion_vacuously():
    engine = FakeEngine([control("Full name")])
    with pytest.raises(ToolError) as failure:
        asyncio.run(Executor(engine).run(task="fill", window=42,
                                        stages=[fields_stage(**{"Full name": "Avery"})], success=[]))
    assert failure.value.code == "bad_arguments" and engine.cua.calls == []


def test_timeout_after_dispatch_reports_the_possible_edit_to_the_parent():
    engine = FakeEngine([control("Full name")])
    original_call = engine.cua.call

    async def delayed_ack(tool, args=None, **kwargs):
        reply = await original_call(tool, args, **kwargs)
        if tool == "set_value":
            # The app receives the input, but the controller never receives
            # acknowledgement before its deadline. Recovery must see this.
            await asyncio.sleep(1)
        return reply

    engine.cua.call = delayed_ack
    result = run(engine, [fields_stage(**{"Full name": "Avery"})],
                 [{"label": "Full name", "value": "Avery"}], timeout_ms=300)
    assert result["status"] == "escalated" and result["reason"] == "timeout"
    assert engine.cua.controls[0]["value"] == "Avery"
    assert len(result["actions"]) == 1 and result["actions"][0]["status"] == "uncertain"
    assert result["actions"][0]["label"] == "Full name"


def test_inner_action_logs_and_model_state_exclude_supplied_private_values():
    private = "PRIVATE-SUPPLIED-INPUT-29"
    engine = FakeEngine([control("Full name"), control("Email address"),
                         control("Unrelated private label 47", value="PRIVATE-OBSERVED-INPUT-47")])
    chooser = Chooser()
    result = asyncio.run(Executor(engine, chooser).run(
        task="Set this task's explicit fields", window=42,
        stages=[fields_stage(**{"Full name": private, "Email address": private + "@example.invalid"})],
        success=[{"label": "Full name", "value": private}],
        intent=private, max_steps=8))
    assert result.data["status"] == "completed"
    calls_text = repr(chooser.calls)
    assert private not in calls_text and "PRIVATE-OBSERVED-INPUT-47" not in calls_text
    assert "Unrelated private label 47" not in calls_text
    assert private not in repr(engine.logs)


def test_last_permitted_action_can_complete_without_an_extra_iteration():
    engine = FakeEngine([control("Full name")])
    result = run(engine, [fields_stage(**{"Full name": "Avery"})],
                 [{"label": "Full name", "value": "Avery"}], max_steps=1)
    assert result["status"] == "completed" and len(engine.cua.mutations) == 1


def test_declared_partial_snapshot_cannot_support_absence_success():
    engine = FakeEngine([control("Full name", value="Avery")])
    original_call = engine.cua.call

    async def truncated(tool, args=None, **kwargs):
        reply = await original_call(tool, args, **kwargs)
        if tool == "get_window_state":
            reply.structured.update(truncated=True, elements_complete=False, nodes_pending=10)
        return reply

    engine.cua.call = truncated
    result = run(engine, [fields_stage(**{"Full name": "Avery"})], [{"label": "Save draft", "absent": True}])
    assert result["status"] == "escalated" and engine.cua.mutations == []


def test_macos_finished_walk_with_false_complete_flag_supports_positive_checks_only(monkeypatch):
    monkeypatch.setattr("cctl.executor.sys.platform", "darwin")

    def native_engine():
        engine = FakeEngine([control("Full name", value="Avery")])
        original_call = engine.cua.call

        async def completed_walk(tool, args=None, **kwargs):
            reply = await original_call(tool, args, **kwargs)
            if tool == "get_window_state":
                # Observed on native macOS 0.34.0: the walk is exhausted and
                # every indexed row returned, while the flag remains false.
                reply.structured["elements_complete"] = False
            return reply

        engine.cua.call = completed_walk
        return engine

    positive = run(native_engine(), [fields_stage(**{"Full name": "Avery"})],
                   [{"label": "Full name", "value": "Avery"}])
    negative_engine = native_engine()
    negative = run(negative_engine, [fields_stage(**{"Full name": "Avery"})],
                   [{"label": "Missing control", "absent": True}])
    assert positive["status"] == "completed"
    assert negative["status"] == "escalated" and negative_engine.cua.mutations == []


@pytest.mark.parametrize("metadata", [{"nodes_pending": 1}, {"returned_element_count": 0},
                                      {"total_element_count": 2}, {"truncated": True}])
def test_macos_partial_counts_are_not_accepted_as_a_finished_walk(monkeypatch, metadata):
    monkeypatch.setattr("cctl.executor.sys.platform", "darwin")
    engine = FakeEngine([control("Full name")])
    original_call = engine.cua.call

    async def incomplete(tool, args=None, **kwargs):
        reply = await original_call(tool, args, **kwargs)
        if tool == "get_window_state":
            reply.structured.update(elements_complete=False, **metadata)
        return reply

    engine.cua.call = incomplete
    result = run(engine, [fields_stage(**{"Full name": "Avery"})], [{"label": "Full name", "value": "Avery"}])
    assert result["status"] == "escalated" and engine.cua.mutations == []
