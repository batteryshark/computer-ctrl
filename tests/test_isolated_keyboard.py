"""Offline keyboard routing: deny real process/network/native access."""
import asyncio
import socket
import subprocess

import pytest

from cctl.config import Config
from cctl.isolated import IsolatedEngine


@pytest.fixture
def keyboard(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('Unexpected process/network effect in offline test')
    monkeypatch.setattr(subprocess, 'Popen', denied)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'bind', denied)
    cfg = Config(session='guest', sessions={'guest': {'command': ['/synthetic/quietwing'], 'id': 'owned'}},
                 state_dir=tmp_path/'state', cache_dir=tmp_path/'cache')
    engine = IsolatedEngine(cfg)
    engine.binding = {'generation': 'fixed', 'platform': 'macos',
                      'capabilities': {'input': True, 'key_hold': True}}
    calls = []
    async def request(op, *args, **kwargs):
        calls.append((op, args))
        if '--hold-ms' in args:
            ms = int(args[args.index('--hold-ms')+1])
            return {'result': {'heldMs': ms, 'elapsedMs': ms+50, 'released': True}}
        return {'result': {'text_entry': 'guest-clipboard'}}
    monkeypatch.setattr(engine, '_call', request)
    return engine, calls


def test_long_text_is_literal_single_request_and_not_falsely_verified(keyboard):
    engine, calls = keyboard
    text = ('--help ; $(literal) café 日本語\n'*40)[:1000]
    result = asyncio.run(engine.tool_type_text(text))
    assert calls == [('input', ('--type', text))]
    assert result.data == {'typed': len(text), 'verified': False, 'mode': 'guest-clipboard'}


@pytest.mark.parametrize('keys', ['Space', 'Left', 'Right', 'Up', 'Down', 'shift+Left', 'cmd+n', 'Shift'])
def test_mac_holds_are_one_bounded_request(keyboard, keys):
    engine, calls = keyboard
    result = asyncio.run(engine.tool_key(keys, hold_ms=300))
    assert calls == [('input', ('--key', keys, '--hold-ms', '300'))]
    assert result.data['hold_ms'] == 300 and result.data['released'] is True


def test_text_submit_follows_paste_not_before_it(keyboard):
    engine, calls = keyboard
    asyncio.run(engine.tool_type_text('literal', submit=True))
    assert calls == [('input', ('--type', 'literal')), ('input', ('--key', 'Return'))]


def test_older_text_receipts_keep_compatible_mode(keyboard, monkeypatch):
    engine, _ = keyboard
    async def request(*args, **kwargs):
        return {'result': {}}
    monkeypatch.setattr(engine, '_call', request)
    result = asyncio.run(engine.tool_type_text('literal'))
    assert result.data['mode'] == 'provider-native' and result.data['verified'] is False


def test_failed_paste_never_submits_or_replays(keyboard, monkeypatch):
    from cctl.results import ToolError
    engine, _ = keyboard
    calls = []
    async def request(*args, **kwargs):
        calls.append(args)
        raise ToolError('generation_changed', 'replacement')
    monkeypatch.setattr(engine, '_call', request)
    with pytest.raises(ToolError):
        asyncio.run(engine.tool_type_text('literal', submit=True))
    assert calls == [('input', '--type', 'literal')]
