"""Verify frozen host, embedded renderer and installed offline wheel together."""
from __future__ import annotations
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import struct
import hashlib
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]

def main():
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    payload=Path(build['payload'])
    target=ROOT/'test-results/desktop-sdk-installed'
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--disable-pip-version-check',
                    '--upgrade','--target',str(target),str(ROOT/'dist'/build['sdk'])],check=True)
    sys.path.insert(0,str(target))
    from astra_desktop_client import AstraClient,CLIENT_VERSION
    from astra_sdk import AstraClient as IndependentClient
    import astra.client
    assert Path(astra.client.__file__).is_relative_to(target)
    assert CLIENT_VERSION=='2.5.0'
    assert IndependentClient is AstraClient and hasattr(AstraClient,'pause')
    # A stale astra package earlier on sys.path must not shadow the new SDK.
    collision=ROOT/'test-results/sdk-shadow';(collision/'astra').mkdir(parents=True,exist_ok=True)
    (collision/'astra/__init__.py').write_text('',encoding='utf-8')
    (collision/'astra/client.py').write_text('class AstraClient: pass\n',encoding='utf-8')
    probe="import sys;sys.path.insert(0,"+repr(str(target))+");sys.path.insert(0,"+repr(str(collision))+");import astra.client as old;assert not hasattr(old.AstraClient,'pause');from astra_sdk import AstraClient,CLIENT_VERSION;assert hasattr(AstraClient,'pause');assert CLIENT_VERSION=='2.5.0';print(AstraClient.client_info())"
    subprocess.run([sys.executable,'-B','-c',probe],cwd=collision,check=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    output=ROOT/'test-results/native-frozen-host'
    for suffix in ('.log','.json'):
        old=Path(str(output)+suffix)
        if old.exists():old.unlink()
    command=[str(payload/'ASTRA.exe'),'--port',str(port),'--quality','high','--smoke',str(output)]
    process=subprocess.Popen(command,cwd=payload,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        client=AstraClient(f'http://127.0.0.1:{port}',timeout_s=10)
        deadline=time.monotonic()+30
        while True:
            if process.poll() is not None:raise RuntimeError('Packaged host exited early')
            try:
                status=client.status()
                if status.get('process_id')==process.pid:break
            except (ConnectionError,RuntimeError):pass
            if time.monotonic()>deadline:raise TimeoutError('Frozen API startup')
            time.sleep(.1)
        # Allow the native GUI to finish its initial mission bootstrap.
        time.sleep(2)
        assert status['browser_required'] is False
        assert status['desktop_version']==build['version']
        assert status['client_version']==CLIENT_VERSION and 'astra_sdk' in status['client_module']
        catalog=client.game_catalog()
        missions=[mission for rows in catalog.values() for mission in rows]
        assert set(catalog)=={'space','aircraft','drone'}
        assert len(missions)==12
        assert Counter(item['category'] for item in missions)=={
            'INGEGNERIA':3,'ESPLORAZIONE':3,'PILOTAGGIO':3,'SCIENZA':3}
        assert [len(catalog[key]) for key in ('space','aircraft','drone')]==[6,3,3]
        free=client.free_flight('aircraft',advanced_models=True)
        assert free['desktop']['play_mode']=='free' and free['state']['command']['mode']=='manual'
        assert not free['desktop']['running']
        before_details=client.state()
        details=client.flight_details()
        assert len(details)==6 and client.state()==before_details
        client.pause();client.reset('drone',advanced_models=True);client.launch()
        client.command(mode='python',throttle_pct=55,roll_deg=2)
        state=client.step(.4)
        assert len(state['science']['disciplines'])==13
        assert client.snapshot()['desktop']['clock_owner']=='external'
        assert client.state()==state
        assert len(client.engineering_solvers()['solvers'])==18
        assert client.engineering('beam')['analysis']=='beam'
        assert client.recording()['samples']
        assert client.verify_requirements([dict(id='mass',field='mass_kg',operator='>',value=0)])
        assert len(client.celestial('2026-10-28T00:00:00Z')['objects'])>8
        assert client.visual_models()['defaults']['merlo-h6']=='px4-typhoon-h480'
        before=client.state()
        client.set_view(model='auto',show_ui=False,resolution_scale=1.)
        client.set_camera(55,20,1.8)
        shot=client.capture(ROOT/'test-results/sdk-real-capture.png',overwrite=True)
        data=Path(shot['path']).read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n'
        assert struct.unpack_from('>II',data,16)==(1440,900)
        assert client.state()==before
        deadline=time.monotonic()+15
        while True:
            render=client.renderer_status()
            if render.get('connected') and render.get('asset_id')=='innerscene-quadcopter':break
            if time.monotonic()>deadline:raise TimeoutError('Renderer heartbeat not ready: '+str(render))
            time.sleep(.1)
        assert render['asset_loaded']
        assert process.wait(timeout=75)==0
        report=json.loads(Path(str(output)+'.json').read_text())
        log=Path(str(output)+'.log').read_text(encoding='utf-8',errors='replace')
        assert 'SCRIPT ERROR:' not in log and '\nERROR:' not in log,log[-10000:]
        assert report['screenshot_saved'] and report['vehicle']=='drone'
        assert report['science_disciplines']==13 and report['solvers']==18
        report.update(frozen_host='PASS',offline_wheel='PASS',wheel_import_path=str(astra.client.__file__),
                      free_flight_api='PASS',detailed_instruments_api='PASS',independent_sdk='PASS',legacy_module_collision='PASS',
                      game_activities=sorted(catalog),game_missions=len(missions),
                      career_categories=dict(Counter(item['category'] for item in missions)),
                      exact_external_clock='PASS',python_mode='PASS',camera_api='PASS',real_png_capture=shot,
                      presentation_does_not_advance_physics=True,desktop_version=status['desktop_version'],
                      host_sha256=hashlib.sha256((payload/'ASTRA.exe').read_bytes()).hexdigest(),
                      renderer_sha256=hashlib.sha256((payload/'ASTRA-Renderer.exe').read_bytes()).hexdigest(),
                      sdk_sha256=hashlib.sha256((ROOT/'dist'/build['sdk']).read_bytes()).hexdigest())
        (ROOT/'test-results/desktop-package-validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if process.poll() is None:
            # Only our own temporary test process; renderer uses the smoke timeout.
            process.terminate();process.wait(timeout=10)

if __name__=='__main__':main()
