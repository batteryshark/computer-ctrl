"""Exercise the public subprocess interface, never a host desktop."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from cctl.config import Config, load
from cctl.isolated import IsolatedEngine
from cctl.providers import create_engine


@pytest.fixture
def target(tmp_path):
    helper = tmp_path / "provider.py"
    helper.write_text('''import json,sys,os
from pathlib import Path
from PIL import Image
a=sys.argv[1:]; op=a[0]; root=Path(os.environ['FAKE_ROOT'])
state=root/'generation'; generation=state.read_text() if state.exists() else None
def reply(ok=True,**kw):
 print(json.dumps(dict(schemaVersion=1,ok=ok,platform='linux',**kw)));sys.exit(0 if ok else 1)
if '--expect-generation' in a and a[a.index('--expect-generation')+1]!=generation:
 reply(False,error=dict(code='generation_changed',message='different instance'))
if op=='start' and not generation:
 generation='gen-one';state.write_text(generation)
caps={k:bool(generation) for k in ['capture','input','keyboard','pointer','exec']}
caps['key_hold']=bool(generation) and (root/'supports-hold').exists()
caps['pointer_drag']=bool(generation) and (root/'supports-drag').exists()
d=dict(schemaVersion=1,id=a[a.index('--id')+1],platform='linux',generation=generation,
 state='running' if generation else 'stopped',capabilities=caps,
 connection=dict(kind='local-cli',protocolVersion=1),lifecycle=dict(acquire='start',release='stop-owned'))
if op in ['capture','input','exec']:
 with (root/'calls').open('a') as f:f.write(json.dumps(a)+'\\n')
if op=='capture':
 path=a[a.index('--output')+1];Image.new('RGB',(800,600),'white').save(path)
if op=='stop':state.unlink()
result=dict(operation=op)
if '--drag' in a:result['released']=True
if '--hold-ms' in a:
 ms=int(a[a.index('--hold-ms')+1]);result.update(heldMs=ms,elapsedMs=ms,released=not (root/'bad-release').exists())
reply(descriptor=d,result=result)
''')
    cfg = Config(session="work", sessions={"work": {"command": [sys.executable, str(helper)],
                  "env": {"FAKE_ROOT": str(tmp_path)}, "id": "owned"}},
                 state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")
    cfg.isolate_paths()
    return IsolatedEngine(cfg), tmp_path


def call(engine, tool, **args):
    return asyncio.run(engine.dispatch(tool, args))


def test_no_host_discovery_and_native_loop(target, monkeypatch):
    from cctl.engine import Engine
    monkeypatch.setattr(Engine, "__init__", lambda *a: pytest.fail("host Engine constructed"))
    engine, root = target
    assert isinstance(create_engine(engine.cfg), IsolatedEngine)
    shot = call(engine, "screenshot", max_dim=400)
    assert not shot.is_error, shot.data
    click = call(engine, "click", x=100, y=50, frame=shot.data['frame'])
    assert click.data['clicked'] == [200, 100]
    text = '--help ; $(never) café 日本語'
    assert not call(engine, "type_text", text=text).is_error
    records = [json.loads(x) for x in (root/'calls').read_text().splitlines()]
    assert records[-1][-2:] == ['--type', text]
    assert all('--expect-generation' in x for x in records)
    assert text not in (engine.cfg.state_dir/'events.jsonl').read_text()


def test_replacement_cannot_receive_old_actions_or_old_frame(target):
    engine, root = target
    shot = call(engine, "screenshot")
    (root/'generation').write_text('gen-two')
    before = (root/'calls').read_text()
    for tool,args in [('type_text',{'text':'must not type'}),('click',{'x':1,'y':2,'frame':shot.data['frame']}),
                      ('apps',{'action':'launch','name':'editor'}),('screenshot',{})]:
        result = call(engine, tool, **args)
        assert result.is_error and result.data['error']=='generation_changed'
    assert (root/'calls').read_text() == before
    assert not call(engine, '_session', action='start').is_error
    result = call(engine, 'click', x=1, y=2, frame=shot.data['frame'])
    assert result.is_error
    assert (root/'calls').read_text() == before


def test_stop_is_owned_and_explicit_restart_needed(target):
    engine,root=target
    call(engine,'screenshot')
    assert not call(engine,'_session',action='stop').is_error
    assert not (root/'generation').exists()
    assert call(engine,'type_text',text='no').data['error']=='session_stopped'
    assert not call(engine,'_session',action='start').is_error
    assert not call(engine,'type_text',text='yes').is_error


def test_stop_before_acquisition_still_prevents_implicit_start(target):
    engine,root=target
    stopped=call(engine,'_session',action='stop')
    assert not stopped.is_error and stopped.data['already_stopped']
    assert call(engine,'screenshot').data['error']=='session_stopped'
    assert not (root/'generation').exists()
    assert not call(engine,'_session',action='start').is_error
    assert not call(engine,'screenshot').is_error


def test_repeated_stop_does_not_touch_a_later_replacement(target):
    engine,root=target
    assert not call(engine,'screenshot').is_error
    assert not call(engine,'_session',action='stop').is_error
    assert not call(engine,'_session',action='stop').is_error
    (root/'generation').write_text('external-replacement')
    assert call(engine,'_session',action='stop').data['binding_released']
    assert (root/'generation').read_text()=='external-replacement'
    assert call(engine,'type_text',text='no').data['error']=='session_stopped'


def test_stop_missing_linux_instance_blocks_later_implicit_acquisition(target):
    engine,root=target
    provider=root/'provider.py'
    source=provider.read_text().replace("if op=='start' and not generation:",
        "if op=='describe' and not generation:\n reply(False,error=dict(code='SESSION_NOT_FOUND',message='absent'))\n"
        "if op=='start' and not generation:")
    provider.write_text(source)
    assert call(engine,'_session',action='stop').data['already_stopped']
    assert call(engine,'screenshot').data['error']=='session_stopped'
    assert not (root/'generation').exists()
    assert not call(engine,'_session',action='start').is_error


@pytest.mark.parametrize('name',['observe','browser_open','run','audio_capture','record_clip','delegate'])
def test_unsupported_does_not_even_start_provider(target,name):
    engine,root=target
    result=call(engine,name)
    assert result.is_error and result.data['error']=='unsupported_capability'
    assert not (root/'generation').exists()


def test_unsupported_input_options_fail_before_delivery(target):
    engine,root=target
    call(engine,'screenshot')
    before=(root/'calls').read_text()
    for name,args in [('click',dict(element='host-token')),('key',dict(keys='a',window=12)),
                      ('type_text',dict(text='x',mode='set_value')),
                      ('type_text',dict(text='x',then='observe'))]:
        assert call(engine,name,**args).is_error
    assert (root/'calls').read_text()==before


def test_zoom_coordinates_and_generation(target):
    engine,_=target
    shot=call(engine,'screenshot',max_dim=400)
    zoom=call(engine,'zoom',frame=shot.data['frame'],region=[50,50,100,100],fresh=False)
    assert not zoom.is_error
    assert call(engine,'click',frame=zoom.data['frame'],x=200,y=200).data['clicked']==[150,150]


def test_cli_literal_argument_array(target):
    engine,root=target
    args=['--help','two words',"apostrophe's",'$(do-not-execute)']
    assert not call(engine,'apps',action='launch',name='editor',args=args).is_error
    record=json.loads((root/'calls').read_text().splitlines()[-1])
    assert record[record.index('--')+1:]==['editor',*args]


def test_config_paths_target_and_command_scoped(tmp_path,monkeypatch):
    path=tmp_path/'config.toml'
    path.write_text('session="one"\n[sessions.one]\ncommand=["one-helper"]\n[sessions.two]\ncommand=["two-helper"]\n')
    monkeypatch.setenv('CCTL_CONFIG',str(path));monkeypatch.delenv('CCTL_SESSION',raising=False)
    first=load()
    monkeypatch.setenv('CCTL_SESSION','two');second=load()
    assert first.cache_dir!=second.cache_dir and first.state_dir!=second.state_dir
    monkeypatch.setenv('CCTL_SESSION','missing')
    with pytest.raises(ValueError,match='no host fallback'):load()


def test_host_default_is_unchanged(tmp_path,monkeypatch):
    monkeypatch.setenv('CCTL_CONFIG',str(tmp_path/'absent'))
    monkeypatch.delenv('CCTL_SESSION',raising=False)
    from cctl.engine import Engine
    cfg=load()
    assert not cfg.session
    assert isinstance(create_engine(cfg),Engine)


def test_remote_configuration_does_not_resolve_target_on_caller(tmp_path,monkeypatch):
    path=tmp_path/'caller.toml'
    path.write_text('[hosts."user@remote"]\nremote_bin="/remote/cctl"\n')
    monkeypatch.setenv('CCTL_CONFIG',str(path))
    monkeypatch.setenv('CCTL_SESSION','remote-only-session')
    from cctl.cli import remote_target
    assert remote_target('user@remote')[1]=='/remote/cctl'


def test_status_reports_replacement_without_rebinding_actions(target):
    engine,root=target
    call(engine,'screenshot')
    (root/'generation').write_text('replacement')
    status=call(engine,'_session',action='status')
    assert not status.is_error and status.data['requires_rebind']
    assert status.data['descriptor']['generation']=='replacement'
    assert call(engine,'type_text',text='no').data['error']=='generation_changed'


def test_double_click_refuses_before_input(target):
    engine,root=target
    shot=call(engine,'screenshot')
    before=(root/'calls').read_text()
    result=call(engine,'click',x=1,y=2,count=2,frame=shot.data['frame'])
    assert result.is_error and result.data['error']=='unsupported_capability'
    assert (root/'calls').read_text()==before


def test_windows_launcher_loads_configured_source_before_installed_module(tmp_path,monkeypatch):
    import subprocess
    from types import SimpleNamespace
    from cctl.cli import start_isolated_controller
    source=tmp_path/'source'; package=source/'cctl';package.mkdir(parents=True)
    (package/'__init__.py').write_text('')
    proof=tmp_path/'loaded.json'
    (package/'cli.py').write_text('import os,json\nfrom pathlib import Path\ndef main(args):\n'
        + f' Path({str(proof)!r}).write_text(json.dumps([args,os.environ["CCTL_SESSION"]]))\n')
    state=tmp_path/'state';state.mkdir()
    cfg=Config(session='work',state_dir=state)
    monkeypatch.setenv('PYTHONPATH',str(source))
    monkeypatch.setenv('CCTL_CONFIG',str(tmp_path/'config.toml'))
    monkeypatch.setattr(subprocess,'CREATE_NO_WINDOW',0,raising=False)
    commands=[]
    with monkeypatch.context() as ctx:
        ctx.setattr(subprocess,'run',lambda argv,**kw: commands.append(argv) or SimpleNamespace(returncode=0))
        start_isolated_controller(cfg)
    ps=commands[0][-1]
    assert 'RunLevel Limited' in ps and 'finally' in ps and 'Unregister-ScheduledTask' in ps
    subprocess.run([sys.executable,str(state/'controller-launch.py')],check=True,
                   env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'})
    assert json.loads(proof.read_text())==[['serve'],'work']


def test_downloaded_remote_artifacts_are_target_scoped(tmp_path,monkeypatch,capsys):
    from types import SimpleNamespace
    from cctl import cli
    monkeypatch.setattr(cli.tempfile,'gettempdir',lambda: str(tmp_path))
    monkeypatch.setattr(cli,'remote_target',lambda host: ([], '/remote/cctl', False))
    destinations=[]
    def run(argv,**kwargs):
        if argv[0]=='scp':
            destinations.append(Path(argv[-1]))
            Path(argv[-1]).write_bytes(b'isolated capture')
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0,stdout='{"path":"/remote/capture.png"}',stderr='')
    monkeypatch.setattr(cli.subprocess,'run',run)
    for target in ('one','two'):
        assert cli.run_remote('user@remote',['--session',target,'screenshot'])==0
        result=json.loads(capsys.readouterr().out)
        assert Path(result['path']).read_bytes()==b'isolated capture'
    assert destinations[0].parent!=destinations[1].parent


def test_bounded_hold_requires_capability_and_uses_pinned_literal_request(target):
    engine, root = target
    (root/'supports-hold').touch()
    result = call(engine, 'key', keys='CTRL+LEFT', hold_ms=120)
    assert not result.is_error, result.data
    assert result.data['released'] is True and result.data['hold_ms']==120
    records=[json.loads(line) for line in (root/'calls').read_text().splitlines()]
    assert len(records)==1
    assert records[0][-4:]==['--key','CTRL+LEFT','--hold-ms','120']
    assert '--expect-generation' in records[0]


def test_old_helper_refuses_hold_without_silently_tapping(target):
    engine, root=target
    result=call(engine,'key',keys='Return',hold_ms=100)
    assert result.is_error and result.data['error']=='unsupported_capability'
    assert not (root/'calls').exists()
    assert not call(engine,'key',keys='Return').is_error
    assert '--hold-ms' not in (root/'calls').read_text()


@pytest.mark.parametrize('args',[{'hold_ms':True},{'hold_ms':-1},{'hold_ms':5001},{'hold_ms':1.5},{'hold_ms':100,'repeat':2},{'hold_ms':100,'window':12}])
def test_invalid_hold_never_sends_input(target,args):
    engine,root=target
    (root/'supports-hold').touch()
    assert call(engine,'key',keys='A',**args).is_error
    assert not (root/'calls').exists()


def test_hold_cannot_follow_a_replaced_generation(target):
    engine,root=target
    (root/'supports-hold').touch()
    assert not call(engine,'screenshot').is_error
    before=(root/'calls').read_text()
    (root/'generation').write_text('replacement')
    result=call(engine,'key',keys='A',hold_ms=100)
    assert result.is_error and result.data['error']=='generation_changed'
    assert (root/'calls').read_text()==before


def test_unconfirmed_release_is_an_error_without_replay(target):
    engine,root=target
    (root/'supports-hold').touch();(root/'bad-release').touch()
    result=call(engine,'key',keys='Return',hold_ms=100)
    assert result.is_error and result.data['error']=='provider_protocol'
    assert len((root/'calls').read_text().splitlines())==1


def test_direct_host_hold_refuses_before_focus_or_input():
    from cctl.engine import Engine
    from cctl.results import ToolError
    engine=object.__new__(Engine)
    with pytest.raises(ToolError) as error:
        asyncio.run(engine.tool_key('A',hold_ms=100))
    assert error.value.code=='unsupported_capability'


def test_drag_crosses_public_cli_once_with_pinned_generation(target):
    engine, root=target
    (root/'supports-drag').touch()
    shot=call(engine,'screenshot',max_dim=400)
    result=call(engine,'drag',**{'from':[10,20],'to':[100,150],'frame':shot.data['frame'],'button':'right'})
    assert not result.is_error, result.data
    records=[json.loads(line) for line in (root/'calls').read_text().splitlines()]
    assert len(records)==2
    assert records[-1]==['input','--id','owned','--expect-generation','gen-one',
                         '--drag','20','40','200','300','--button','3']
    (root/'generation').write_text('replacement')
    result=call(engine,'drag',**{'from':[1,2],'to':[3,4],'frame':shot.data['frame']})
    assert result.is_error and result.data['error']=='generation_changed'
    assert len((root/'calls').read_text().splitlines())==2
