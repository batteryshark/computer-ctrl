"""Offline guest targets: no host engine, network, subprocess or native access."""
import asyncio
import socket
import subprocess
from unittest.mock import AsyncMock

import pytest

from cctl.config import Config
from cctl.isolated import IsolatedEngine
from cctl.results import ToolError


@pytest.fixture
def engine(tmp_path, monkeypatch):
    def denied(*a, **kw):
        pytest.fail('offline target test attempted an external effect')
    monkeypatch.setattr(subprocess, 'Popen', denied)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'bind', denied)
    from cctl.engine import Engine
    monkeypatch.setattr(Engine, '__init__', denied)
    e = IsolatedEngine(Config(session='test', sessions={'test': {'command': ['unused'], 'id': 'owned'}},
                              state_dir=tmp_path/'state', cache_dir=tmp_path/'cache'))
    e.binding = {'generation': 'fixed', 'platform': 'macos', 'capabilities': {'guest_windows': True, 'guest_processes': True}}
    e._ensure = AsyncMock()
    e._call = AsyncMock(return_value={'result': {'processes': [{'pid': 123, 'name': 'editor', 'cmd': '--help ; $(literal)', 'target': 'opaque'}]}})
    return e


def call(e, name, **args):
    return asyncio.run(e.dispatch(name, args))


def test_exact_window_only(engine):
    assert not call(engine, 'windows', action='focus', window=234).is_error
    engine._call.assert_awaited_once_with('windows', '--action', 'focus', '--window-id', '234')
    engine._call.reset_mock()
    for args in [dict(action='move', window=234), dict(action='close'), dict(action='close', window=True), dict(action='close', window=234, x=1)]:
        assert call(engine, 'windows', **args).is_error
    engine._call.assert_not_awaited()


def test_only_visible_listed_pid_authorizes_action(engine):
    assert call(engine, 'processes', action='kill', pid=123).is_error
    assert not call(engine, 'processes', action='list', filter='literal', sort='pid').is_error
    assert not call(engine, 'processes', action='kill', pid=123).is_error
    engine._call.assert_awaited_with('processes', '--action', 'terminate', '--pid', '123', '--target', 'opaque')
    assert call(engine, 'processes', action='kill', pid=123).is_error


def test_hidden_rows_and_replacements_do_not_authorize(engine):
    call(engine, 'processes', action='list', filter='absent')
    assert call(engine, 'apps', action='quit', pid=123).is_error
    call(engine, 'processes', action='list')
    engine.binding['generation'] = 'replacement'
    assert call(engine, 'apps', action='quit', pid=123).data['error'] == 'generation_changed'


def test_quit_is_graceful_and_unsupported_signal_never_delivers(engine):
    call(engine, 'processes', action='list')
    engine._call.reset_mock()
    assert call(engine, 'processes', action='kill', pid=123, signal='KILL').is_error
    engine._call.assert_not_awaited()
    assert not call(engine, 'apps', action='quit', pid=123).is_error
    engine._call.assert_awaited_once_with('processes', '--action', 'quit', '--pid', '123', '--target', 'opaque')


def test_missing_capability_and_unknown_outcome_never_fall_back(engine):
    engine.binding['capabilities'] = {}
    for tool in ('windows', 'processes'):
        assert call(engine, tool, action='list').data['error'] == 'unsupported_capability'
    engine._call.assert_not_awaited()
    engine.binding['capabilities']['guest_windows'] = True
    engine._call.side_effect = ToolError('generation_changed', 'replaced')
    assert call(engine, 'windows', action='close', window=234).data['error'] == 'generation_changed'
    assert engine._call.await_count == 1


def test_unknown_process_outcome_consumes_cached_target(engine):
    call(engine, 'processes', action='list')
    engine._call.reset_mock()
    engine._call.side_effect = ToolError('provider_timeout', 'unknown outcome')
    assert call(engine, 'processes', action='kill', pid=123).data['error'] == 'provider_timeout'
    assert call(engine, 'processes', action='kill', pid=123).data['error'] == 'bad_arguments'
    assert engine._call.await_count == 1
