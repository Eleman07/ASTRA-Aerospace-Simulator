"""Native desktop host. Scientific equations remain in astra/ unchanged.

One simulation clock, immutable HTTP snapshots, native renderer as a child process.
The renderer is not a browser and never owns/integrates physical state.
"""
from __future__ import annotations
import argparse
import copy
import csv
import io
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import browser_bridge
from astra.attitude import _q_rotate
from native_visuals import NativeVisuals
from native_telemetry import flight_details
from astra.celestial import celestial_catalog
from astra.gameplay import GameSession
from astra.career_runtime import (career_defaults, initialize_game, before_game_step, advance_game, game_snapshot, dispatch_game)
from datetime import datetime,timedelta,timezone

DESKTOP_VERSION='2.5.1'


def unit(v):
    length=math.sqrt(sum(x*x for x in v))
    return [x/max(length,1e-20) for x in v]


def cross(a,b):
    return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def start_renderer(command,cwd):
    """Keep the frozen Python DLL directory out of the native GPU process.

    https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
    The Windows bootloader's DLL search path is inherited by subprocesses.
    Restore it immediately in the host after creating the renderer process.
    """
    kernel=None;previous=None
    if sys.platform=='win32' and getattr(sys,'frozen',False):
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        previous=ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(previous),previous)
        if not kernel.SetDllDirectoryW(None):raise ctypes.WinError(ctypes.get_last_error())
    try:
        return subprocess.Popen(command,cwd=cwd,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    finally:
        if kernel is not None:kernel.SetDllDirectoryW(previous.value or None)


def visual_frame(state):
    """Subtract/rotate ECI doubles before uploading metre-scale float GPU data."""
    if state.get('scenario')=='planetary':
        p=state['position_enu_m']
        q=state['quaternion_body_to_enu']
        columns=[_q_rotate(q,v) for v in ([1,0,0],[0,0,1],[0,-1,0])]
        return dict(domain='moon',altitude_m=p[2],position_m=[p[0],p[2],-p[1]],
                    vehicle_basis=[[v[0],v[2],-v[1]] for v in columns],
                    ground_offset_m=[-p[0],-p[2],p[1]],planet_radius_m=1737400.)
    if state['vehicle']!='space':
        n,e,d=state['position_ned_m']
        return dict(domain='air',altitude_m=-d,position_m=[e,-d,-n],
                    attitude_deg=state.get('attitude_deg',[0,0,0]),
                    ground_offset_m=[-e,d,n],planet_radius_m=6378137.)
    position=state['position_eci_m']
    radius=math.sqrt(sum(v*v for v in position));up=unit(position)
    east=unit(cross([0,0,1] if abs(up[2])<.99 else [0,1,0],up));north=cross(up,east)
    def local(v):return [sum(v[i]*a[i] for i in range(3)) for a in (east,up,[-x for x in north])]
    q=state.get('attitude_quaternion_body_to_eci')
    if q:
        columns=[local(_q_rotate(q,v)) for v in ([1,0,0],[0,0,1],[0,-1,0])]
    else:
        direction=unit(state.get('body_axis_z_eci',up))
        y=local(direction);x=unit(cross([0,0,1],y));columns=[x,y,cross(x,y)]
    target=state.get('target_position_eci_m')
    site_latitude=math.radians(28.5721)
    site_longitude=math.radians(-80.6480)+float(state.get('time_s',0))*7.292115e-5
    site=[6378137.*math.cos(site_latitude)*math.cos(site_longitude),6378137.*math.cos(site_latitude)*math.sin(site_longitude),6378137.*math.sin(site_latitude)]
    return dict(domain='orbit' if state.get('scenario')=='orbital' else 'earth',
                altitude_m=radius-6378137.,position_m=[0,0,0],vehicle_basis=columns,
                ground_offset_m=[0,-(radius-6378137.),0],planet_center_m=[0,-radius,0],
                planet_basis=[local(v) for v in ([1,0,0],[0,0,1],[0,-1,0])],
                planet_radius_m=6378137.,
                launch_site_offset_m=local([site[i]-position[i] for i in range(3)]),
                target_offset_m=local([target[i]-position[i] for i in range(3)]) if target else None)


class DesktopRuntime:
    def __init__(self,step_s=.02):
        self.lock=threading.RLock()
        self.step_s=step_s;self.running=False;self.speed=1.;self.clock_owner='desktop'
        self.stop_event=threading.Event();self.revision=0;self.samples=[];self.events=[]
        self.dropped_samples=0;self.next_sample=0.;self.last_pilot_wall=None
        self.controller_armed=False;self.last_error=None;self.compute_ms=0.
        self.last_visual={};self.api_calls=0
        self.visuals=NativeVisuals()
        self.play_mode='mission'
        self.game_session=GameSession()
        self.game_awarded=False
        self.career=self._load_career()
        initialize_game(self)
        self.sky_epoch=datetime(2026,10,28,tzinfo=timezone.utc)
        self.sky_cache_time=None;self.sky_catalog={}
        self.engine=browser_bridge.engine
        self.engine.reset('space',advanced_models=True)
        self.worker=threading.Thread(target=self._loop,name='ASTRA-physics-clock',daemon=True)

    @staticmethod
    def _career_file():
        base=Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_STATE_HOME') or
                  (Path.home()/'.local'/'state'))
        return base/'ASTRA Desktop'/'career.json'

    @classmethod
    def _load_career(cls):
        defaults=career_defaults()
        try:
            data=json.loads(cls._career_file().read_text(encoding='utf-8'))
            for key in defaults:
                if key in data and isinstance(data[key],type(defaults[key])):
                    defaults[key]=data[key]
        except (OSError,ValueError,TypeError):pass
        return defaults

    def _save_career(self):
        path=self._career_file()
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(self.career,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)

    def _command(self,command):
        result=self.engine.set_command(command)
        if (not result.get('radio_command_receipt') and self.engine.vehicle=='space' and self.engine.scenario in {'mission','leo-return'}
                and 'pitch_deg' in command):
            value=float(command['pitch_deg'])
            if not math.isfinite(value):raise ValueError('pitch_deg must be finite')
            # The native launch attitude control exposes vertical 90 degrees.
            # This corrects the old UI's ±45-degree command clipping only.
            self.engine.command['pitch_deg']=max(-45.,min(90.,value))
            result=self.engine.state()
        return result

    def start(self):self.worker.start()
    def close(self):self.stop_event.set();self.worker.join(timeout=5)

    def _record(self,state):
        t=state['time_s']
        if t+1e-8<self.next_sample:return
        self.next_sample=t+.1
        row={key:copy.deepcopy(state.get(key)) for key in (
            'time_s','vehicle','scenario','phase','altitude_m','speed_m_s','mass_kg',
            'propellant_pct','battery_pct','position_eci_m','position_ned_m',
            'attitude_deg','load_factor_g','command')}
        row['dynamic_pressure_Pa']=state.get('environment',{}).get('dynamic_pressure_Pa')
        row['visual']=visual_frame(state)
        self.samples.append(row)
        if len(self.samples)>10000:self.samples.pop(0);self.dropped_samples+=1

    def _step(self,dt):
        if self.play_mode=='free' and self.running and self.clock_owner=='desktop' and not self.engine.mission_started:self._launch_desktop()
        before_game_step(self)
        start=time.perf_counter();state=self.engine.step(dt)
        self.compute_ms=(time.perf_counter()-start)*1000
        advance_game(self,state,dt)
        self._record(state)
        if state['phase'] in {'LANDED','CRASHED','ABORTED'}:self.running=False
        return state

    def _launch_desktop(self):
        command=copy.deepcopy(self.engine.command)
        if self.play_mode=='free' and self.engine.vehicle=='space' and self.engine.scenario=='mission' and not self.engine.mission_started:
            state=self.engine.state()
            available=state.get('propulsion',{}).get('net_thrust_N',0)*float(command.get('throttle_pct',0))/100
            if available<=state['mass_kg']*9.80665*1.02:return
        if not self.engine.mission_started:self.engine.launch()
        if self.play_mode=='free':self._command(dict(command,mode='manual'))

    def _loop(self):
        while not self.stop_event.is_set():
            start=time.monotonic()
            try:
                with self.lock:
                    if (self.controller_armed and self.last_pilot_wall is not None
                            and start-self.last_pilot_wall>.6):
                        self._disarm('INPUT_HEARTBEAT_LOST')
                    if self.running and self.clock_owner=='desktop':
                        self._step(self.step_s*self.speed)
            except Exception as exc:
                with self.lock:self.running=False;self.last_error=str(exc)
            self.stop_event.wait(max(.001,self.step_s-(time.monotonic()-start)))

    def _disarm(self,reason):
        self.controller_armed=False
        if self.play_mode=='free':
            self.running=False
        else:self.engine.set_command(dict(mode='auto',brakes_pct=0))
        self.events.append(dict(type='INPUT_DISARMED',reason=reason,time_s=self.engine.t))
        self.events=self.events[-100:]

    def _snapshot(self):
        state=self.engine.state()
        visual=visual_frame(state)
        # Presentation ephemerides never feed back into the scientific state.
        if self.sky_cache_time is None or abs(state['time_s']-self.sky_cache_time)>60:
            self.sky_cache_time=state['time_s']
            self.sky_catalog={b['id']:b for b in celestial_catalog((self.sky_epoch+timedelta(seconds=state['time_s'])).isoformat())['objects']}
        moon=self.sky_catalog['moon']['position_parent_relative_m']
        if visual['domain'] in ('earth','orbit'):
            obliquity=math.radians(23.43928)
            m=[moon[0],moon[1]*math.cos(obliquity)-moon[2]*math.sin(obliquity),moon[1]*math.sin(obliquity)+moon[2]*math.cos(obliquity)]
            position=state['position_eci_m'];up=unit(position);east=unit(cross([0,0,1] if abs(up[2])<.99 else [0,1,0],up));north=cross(up,east)
            delta=[m[i]-position[i] for i in range(3)]
            visual['companion_center_Mm']=[sum(delta[i]*axis[i] for i in range(3))*1e-6 for axis in (east,up,[-x for x in north])]
            visual['companion_radius_Mm']=1.7374;visual['companion_body']='moon'
        elif visual['domain']=='moon':
            # Local landing patch is a sub-Earth illustrative reference, not
            # a selected selenographic site. Keep actual Earth/Moon separation.
            visual['companion_center_Mm']=[-state['position_enu_m'][0]*1e-6,math.sqrt(sum(v*v for v in moon))*1e-6-state['altitude_m']*1e-6,state['position_enu_m'][1]*1e-6]
            visual['companion_radius_Mm']=6.378137;visual['companion_body']='earth'
        if self.engine.vehicle=='space' and self.engine.scenario!='planetary':
            visual['reference_geometry']=copy.deepcopy(getattr(self.engine,'launch_vehicle',{}))
        return dict(state=state,visual=visual,flight_details=flight_details(state),view=self.visuals.view(),capture_requests=self.visuals.pending(),
                    game=game_snapshot(self),career=copy.deepcopy(self.career),desktop=dict(
            version=DESKTOP_VERSION,running=self.running,speed=self.speed,
            play_mode=self.play_mode,
            clock_owner=self.clock_owner,revision=self.revision,
            physics_step_s=self.step_s,physics_compute_ms=self.compute_ms,
            controller_armed=self.controller_armed,input_events=copy.deepcopy(self.events),
            error=self.last_error,recorded_samples=len(self.samples),
            dropped_samples=self.dropped_samples))

    def dispatch(self,endpoint,payload=None,method='GET'):
        payload={} if payload is None else payload
        if not isinstance(payload,dict):raise ValueError('Payload must be an object')
        with self.lock:
            self.api_calls+=1
            if endpoint=='/desktop/snapshot':return self._snapshot()
            if endpoint.startswith('/desktop/game/'):
                return dispatch_game(self,endpoint,payload)
            if endpoint=='/desktop/flight-details':return flight_details(self.engine.state())
            if endpoint=='/desktop/free':
                vehicle=payload.get('vehicle','space');scenario=payload.get('scenario','mission')
                if vehicle not in ('space','aircraft','drone') or scenario not in ('mission','orbital','planetary'):
                    raise ValueError('Choose space/aircraft/drone and mission/orbital/planetary')
                if vehicle!='space' and scenario!='mission':raise ValueError('Aircraft/UAV free flight starts at the airfield')
                self.dispatch('/reset',payload,'POST')
                self.play_mode='free';self.clock_owner='desktop'
                self.game_session=GameSession();self.game_awarded=False;initialize_game(self)
                self._command(dict(mode='manual',throttle_pct=0,pitch_deg=90 if vehicle=='space' and scenario=='mission' else 0))
                return self._snapshot()
            if endpoint=='/desktop/view':return self.visuals.update(payload) if method=='POST' else self.visuals.view()
            if endpoint=='/desktop/assets':return copy.deepcopy(self.visuals.catalog)
            if endpoint=='/desktop/render':return self.visuals.render_report(payload if method=='POST' else None)
            if endpoint=='/desktop/capture' and method=='POST':return self.visuals.capture(payload)
            if endpoint.startswith('/desktop/capture?'):
                from urllib.parse import parse_qs
                job_id=parse_qs(urlsplit(endpoint).query).get('id',[''])[0]
                if job_id not in self.visuals.jobs:raise ValueError('Capture ID not found')
                return copy.deepcopy(self.visuals.jobs[job_id])
            if endpoint=='/desktop/capture/complete':return self.visuals.complete(payload)
            if endpoint=='/desktop/play':
                self.clock_owner='desktop';self._launch_desktop();self.running=True
                return self._snapshot()
            if endpoint=='/desktop/pause':self.running=False;return self._snapshot()
            if endpoint=='/desktop/speed':
                value=float(payload.get('speed',1))
                if not math.isfinite(value) or not .1<=value<=100:raise ValueError('speed must be 0.1–100')
                self.speed=value;return self._snapshot()
            if endpoint=='/desktop/clock':
                owner=payload.get('owner','external')
                if owner not in ('desktop','external'):raise ValueError('clock owner must be desktop or external')
                self.clock_owner=owner;self.running=False
                if owner=='external':self.controller_armed=False;self.last_pilot_wall=None
                return self._snapshot()
            if endpoint=='/desktop/pilot':
                if not payload.get('armed',False):self._disarm('EXPLICIT_OR_DEVICE_LOST');return self._snapshot()
                if self.clock_owner=='external':raise ValueError('External clock owns control; resume desktop play before arming local input')
                if not self.controller_armed:
                    if not payload.get('neutral_acquired',False):raise ValueError('Neutral acquisition required before arming')
                    self.controller_armed=True
                self.last_pilot_wall=time.monotonic()
                self._command(dict(payload.get('command',{}),mode='manual'))
                if payload.get('compact',False):
                    return dict(ok=True,controller_armed=self.controller_armed,
                                clock_owner=self.clock_owner,command=copy.deepcopy(self.engine.command))
                return self._snapshot()
            if endpoint=='/desktop/recording':
                return dict(version=DESKTOP_VERSION,units='SI',scope='COMPACT_TELEMETRY_AND_VISUAL_POSE',samples=copy.deepcopy(self.samples),
                            dropped_samples=self.dropped_samples,events=copy.deepcopy(self.events))
            if endpoint=='/desktop/features':
                return dict(desktop_version=DESKTOP_VERSION,rendering='native-godot',
                            browser_required=False,scientific_engine='UNCHANGED_ASTRA_PYTHON',
                            solvers=list(browser_bridge.SOLVERS),api_version='v1',
                            features=['spacecraft','aircraft','uav','advanced-science-13',
                            'python-gnc','external-clock','gamepad','hotas','calibration',
                            'staging','vehicle-design','model-import','telemetry-export',
                            'fault-injection','convergence','robustness','celestial-transfers',
                            'requirements','mission-replay','prebuilt-vehicles','camera-api','renderer-status','png-capture','free-flight','flight-details',
                            'orbital-sas','gioca-career','measured-career-missions','graphics-presets'])
            if endpoint=='/step':
                self.running=False;self.clock_owner='external'
                self.controller_armed=False;self.last_pilot_wall=None
                return self._step(float(payload.get('dt_s',.1)))
            if endpoint=='/command':return self._command(payload)
            if endpoint=='/reset':
                self.running=False;self._disarm('MISSION_RESET');self.revision+=1
                self.play_mode='mission'
                self.game_session=GameSession();self.game_awarded=False;initialize_game(self)
                self.samples=[];self.events=[];self.dropped_samples=0;self.next_sample=0.
            raw=json.dumps(dict(path=endpoint,payload=payload,method=method),allow_nan=False)
            result=json.loads(browser_bridge.route_raw(raw))
            if not result.get('ok'):raise ValueError(result.get('error','Engine request failed'))
            data=result['data']
            if endpoint=='/status':
                data.update(execution_mode='desktop-native',api='desktop-http-v1',
                            desktop_version=DESKTOP_VERSION,clock_owner=self.clock_owner,
                            browser_required=False,process_id=os.getpid())
            return data


def make_handler(runtime):
    class DesktopHandler(BaseHTTPRequestHandler):
        disable_nagle_algorithm=True
        def handle(self):
            try:super().handle()
            except (ConnectionResetError,BrokenPipeError):pass
        def do_GET(self):self.route()
        def do_POST(self):self.route()
        def log_message(self,*_):pass
        def route(self):
            try:
                path=urlsplit(self.path)
                if not path.path.startswith('/api/v1/'):
                    self.send_error(404);return
                endpoint=path.path.removeprefix('/api/v1')
                if path.query:endpoint+='?'+path.query
                count=int(self.headers.get('Content-Length','0'))
                if not 0<=count<=2_000_000:raise ValueError('Invalid body size')
                payload=json.loads(self.rfile.read(count) or b'{}')
                data=runtime.dispatch(endpoint,payload,self.command)
                body=json.dumps(data,allow_nan=False,separators=(',',':')).encode();status=200
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                body=json.dumps(dict(error=str(exc))).encode();status=400
            except Exception as exc:
                body=json.dumps(dict(error=str(exc))).encode();status=500
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
    return DesktopHandler


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8765);p.add_argument('--serve',action='store_true')
    p.add_argument('--renderer',type=Path);p.add_argument('--project',type=Path)
    p.add_argument('--assets',type=Path);p.add_argument('--quality',default='auto')
    p.add_argument('--self-test',action='store_true');p.add_argument('--smoke',type=Path)
    args=p.parse_args();root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
    if args.self_test:
        from astra.engine import SimulationEngine
        for vehicle,scenario in [('space','mission'),('space','orbital'),('space','planetary'),('aircraft','mission'),('drone','mission')]:
            e=SimulationEngine();e.reset(vehicle,scenario,advanced_models=True);e.launch();state=e.step(.1)
            assert len(state['science']['disciplines'])==13
            json.dumps(visual_frame(state),allow_nan=False)
        print('ASTRA DESKTOP SELF TEST PASS',flush=True);return 0
    runtime=DesktopRuntime()
    initial_quality=args.quality if args.quality in {'low','balanced','high','ultra','cinema'} else 'balanced'
    initial_scale={'low':.65,'balanced':.67,'high':1.0,'ultra':1.15,'cinema':1.5}[initial_quality]
    runtime.visuals.update({'quality':initial_quality,'resolution_scale':initial_scale})
    try:
        try:server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(runtime))
        except OSError:
            if args.port!=8765 or args.serve or args.smoke:raise
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(runtime))
    except OSError as exc:
        message=f'La porta API {args.port} è già occupata. Chiudi la precedente istanza ASTRA o usa --port 8766.\n{exc}'
        if sys.platform=='win32' and not args.serve:
            import ctypes;ctypes.windll.user32.MessageBoxW(0,message,'ASTRA Desktop',0x10)
        else:print(message,flush=True)
        return 1
    server.daemon_threads=True
    api=f'http://127.0.0.1:{server.server_port}'
    connection_file=None
    if not args.smoke:
        connection_file=Path(os.environ.get('LOCALAPPDATA',str(root)))/'ASTRA Desktop'/'connection.json'
        connection_file.parent.mkdir(parents=True,exist_ok=True)
        connection_file.write_text(json.dumps(dict(url=api,pid=os.getpid(),version=DESKTOP_VERSION)),encoding='utf-8')
    runtime.start();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    print('ASTRA DESKTOP API: '+api,flush=True)
    try:
        if args.serve:
            while True:time.sleep(.2)
        else:
            renderer=args.renderer or root/'ASTRA-Renderer.exe'
            command=[str(renderer)]
            if args.project:command+=['--path',str(args.project.resolve())]
            elif (root/'ASTRA.pck').exists():command+=['--main-pack',str(root/'ASTRA.pck')]
            command+=['--rendering-method','gl_compatibility' if args.quality=='low' else 'forward_plus']
            if args.smoke:command+=['--position','-10000,-10000','--resolution','1440x900','--log-file',str(args.smoke.resolve())+'.log']
            command+=['--','--api',api,'--assets',str((args.assets or root/'assets').resolve()),'--quality',args.quality]
            if args.smoke:command+=['--smoke',str(args.smoke.resolve())]
            child=start_renderer(command,root)
            return child.wait()
    except KeyboardInterrupt:return 0
    finally:
        server.shutdown();server.server_close();runtime.close()
        if connection_file and connection_file.exists():
            try:
                if json.loads(connection_file.read_text())['pid']==os.getpid():connection_file.unlink()
            except (OSError,ValueError,KeyError):pass


if __name__=='__main__':raise SystemExit(main())
