"""Offline drag tests: no processes, sockets, native driver or real config."""
import asyncio
import socket
import subprocess
from unittest.mock import AsyncMock

import pytest

from cctl.config import Config
from cctl.frames import Frame
from cctl.isolated import IsolatedEngine
from cctl.results import ToolError


@pytest.fixture
def engine(tmp_path, monkeypatch):
    def denied(*a, **kw):
        pytest.fail("offline drag test attempted an external effect")
    monkeypatch.setattr(subprocess, 'Popen', denied)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'bind', denied)
    cfg = Config(session='test', sessions={'test': {'command': ['unused-provider'], 'id': 'owned'}},
                 state_dir=tmp_path/'state', cache_dir=tmp_path/'cache')
    e = IsolatedEngine(cfg)
    e.binding = {'generation': 'fixed', 'platform': 'macos', 'capabilities': {'input': True, 'pointer_drag': True}}
    e._ensure = AsyncMock()
    e._call = AsyncMock(return_value={'result': {'released': True}})
    e.frames.add(Frame('scaled', 'desktop', 0, 0, 2, 2, 512, 384, extra={'generation': 'fixed'}))
    e.frames.add(Frame('zoom', 'zoom', 100, 80, .25, .25, 400, 400, extra={'generation': 'fixed'}))
    return e


def drag(e, **args):
    return asyncio.run(e.dispatch('drag', {'from': [20, 40], 'to': [80, 100], **args}))


@pytest.mark.parametrize('button,number', [('left', 1), ('middle', 2), ('right', 3)])
@pytest.mark.parametrize('frame,points', [('scaled', [40, 80, 160, 200]), ('zoom', [105, 90, 120, 105]),
                                        ('screen', [20, 40, 80, 100])])
def test_maps_both_points_in_one_request(engine, button, number, frame, points):
    result = drag(engine, frame=frame, button=button)
    assert not result.is_error, result.data
    engine._call.assert_awaited_once_with('input', '--drag', *map(str, points), '--button', str(number))
    assert result.data['dragged'] == [points[:2], points[2:]]
    assert result.data['released'] is True


@pytest.mark.parametrize('args', [{'from': None}, {'from': [1]}, {'to': [1, 2, 3]}, {'to': [True, 2]},
                                 {'to': [float('nan'), 2]}, {'to': [1, float('inf')]},
                                 {'to': ['1', 2]}, {'button': 'other'}, {'modifiers': ['shift']}])
def test_invalid_arguments_never_deliver(engine, args):
    result = drag(engine, frame='scaled', **args)
    assert result.is_error and result.data['error'] == 'bad_arguments'
    engine._call.assert_not_awaited()


def test_old_provider_refuses_and_doctor_explains(engine):
    engine.binding['capabilities'].pop('pointer_drag')
    assert drag(engine, frame='scaled').data['error'] == 'unsupported_capability'
    engine._call.assert_not_awaited()
    doctor = asyncio.run(engine.dispatch('doctor', {}))
    assert 'drag' in doctor.data['supported_tools']
    assert any('pointer_drag' in limit for limit in doctor.data['limitations'])
    assert any('scroll' in limit for limit in doctor.data['limitations'])


def test_stale_frame_refuses_before_delivery(engine):
    engine.frames.get('scaled').extra['generation'] = 'old'
    assert drag(engine, frame='scaled').data['error'] == 'stale_frame'
    engine._call.assert_not_awaited()


def test_generation_changed_refuses_without_replay(engine):
    engine._call.side_effect = ToolError('generation_changed', 'replacement')
    assert drag(engine, frame='scaled').data['error'] == 'generation_changed'
    assert engine._call.await_count == 1


@pytest.mark.parametrize('reply', [{}, {'released': False}, {'released': 'true'}])
def test_missing_release_receipt_is_not_replayed(engine, reply):
    engine._call.return_value = {'result': reply}
    assert drag(engine, frame='scaled').data['error'] == 'provider_protocol'
    assert engine._call.await_count == 1


def test_batch_and_then_keep_drag_supported(engine):
    result = asyncio.run(engine.dispatch('batch', {'actions': [{'tool': 'drag', 'args': {
        'from': [1, 2], 'to': [3, 4], 'frame': 'screen'}}]}))
    assert not result.is_error and result.data['completed'] == 1
    engine.tool_wait_for = AsyncMock(return_value=result)
    assert not drag(engine, frame='screen', then='wait_stable').is_error
    engine.tool_wait_for.assert_awaited_once()
