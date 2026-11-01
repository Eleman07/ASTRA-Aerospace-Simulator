"""ASTRA Python SDK: legacy HTTP and native desktop share scientific API v1.

Desktop step() acquires the external simulation clock: no double integration
when the native renderer is open. No third-party runtime dependencies.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen

CLIENT_VERSION='2.5.0'

class AstraClient:
    def __init__(self,base_url=None,timeout_s=30):
        if base_url is None:base_url=self.discover_desktop()
        self.base_url=base_url.rstrip('/')
        self.timeout_s=timeout_s
        if 'github.io' in self.base_url.lower():
            raise ValueError('GitHub Pages runs a browser-local Pyodide engine, not an HTTP API')
    @staticmethod
    def discover_desktop():
        override=os.environ.get('ASTRA_API_URL')
        if override:return override
        pointer=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'ASTRA Desktop'/'connection.json'
        try:
            from urllib.parse import urlsplit
            data=json.loads(pointer.read_text(encoding='utf-8'));url=data['url'];parsed=urlsplit(url)
            if parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port:return url
        except (OSError,ValueError,KeyError,TypeError):pass
        return 'http://127.0.0.1:8765'
    def _request(self,endpoint,payload=None):
        data=None if payload is None else json.dumps(payload,allow_nan=False).encode()
        req=Request(self.base_url+endpoint,data=data,method='POST' if data is not None else 'GET',headers={'Content-Type':'application/json','Accept':'application/json'})
        try:
            with urlopen(req,timeout=self.timeout_s) as response:return json.load(response)
        except HTTPError as err:
            raise RuntimeError(f'ASTRA HTTP {err.code}: {err.read().decode("utf-8",errors="replace")}') from err
        except URLError as err:
            raise ConnectionError(f'ASTRA non disponibile a {self.base_url}. Avvia ASTRA Desktop.exe oppure il server ASTRA legacy.') from err
    @staticmethod
    def client_info():
        import sys
        return dict(client_version=CLIENT_VERSION,client_module=__file__,python_executable=sys.executable)
    def status(self):
        return dict(self._request('/api/v1/status'),**self.client_info())
    def models(self):return self._request('/api/v1/models')
    def state(self):return self._request('/api/v1/state')
    def reset(self,vehicle='space',scenario='mission',**kwargs):
        return self._request('/api/v1/reset',{'vehicle':vehicle,'scenario':scenario,**kwargs})
    def launch(self):return self._request('/api/v1/launch',{})
    def step(self,dt_s=0.1):return self._request('/api/v1/step',{'dt_s':dt_s})
    def command(self,**kwargs):return self._request('/api/v1/command',kwargs)
    def orbital_attitude(self,sas_mode='manual',torque_body_fraction=None,**kwargs):
        """Set the orbital SAS mode and optional normalized body-axis input."""
        payload={'mode':'manual','attitude_sas_mode':sas_mode,**kwargs}
        if torque_body_fraction is not None:
            payload['attitude_torque_body_fraction']=torque_body_fraction
        return self.command(**payload)
    def sas_enable(self,enabled=True):
        """Engage current inertial attitude hold, or release the SAS actuator.

        Available in orbital flight. Enabling hands attitude to the pilot/SAS;
        ``command(mode='auto')`` explicitly returns authority to the GNC.
        """
        if not isinstance(enabled,bool):raise ValueError('enabled must be boolean')
        return self.command(mode='manual',sas_enabled=enabled)
    def sas_mode(self,mode='stability_assist',**kwargs):
        """Select/enable a contextual SAS preset; see state()['sas'] for modes.

        Manual body torque temporarily overrides directional guidance. All
        presets use the same bounded reaction wheels as orbital_attitude().
        """
        kwargs.setdefault('sas_enabled',mode!='manual')
        return self.orbital_attitude(mode,**kwargs)
    def stage(self):return self._request('/api/v1/stage',{})
    def engineering(self,analysis,**kwargs):return self._request('/api/v1/engineering',{'analysis':analysis,**kwargs})
    def engineering_live(self,analysis,**kwargs):return self._request('/api/v1/engineering/live',{'analysis':analysis,**kwargs})
    def engineering_solvers(self):return self._request('/api/v1/engineering')
    def vehicle_parts(self):return self._request('/api/v1/vehicle-parts')
    def inject_fault(self,**kwargs):return self._request('/api/v1/fault',kwargs)
    def clear_faults(self):return self._request('/api/v1/fault/clear',{})
    def snapshot(self):return self._request('/api/v1/desktop/snapshot')
    def desktop_features(self):return self._request('/api/v1/desktop/features')
    def visual_models(self):return self._request('/api/v1/desktop/assets')
    def view(self):return self._request('/api/v1/desktop/view')
    def set_view(self,**settings):return self._request('/api/v1/desktop/view',settings)
    def set_camera(self,azimuth_deg=37.24,elevation_deg=14.32,distance_m=None):
        return self.set_view(azimuth_deg=azimuth_deg,elevation_deg=elevation_deg,distance_m=distance_m)
    def renderer_status(self):return self._request('/api/v1/desktop/render')
    def capture(self,path,include_ui=False,overwrite=False,timeout_s=30):
        """Save a real PNG from the desktop renderer; does not advance physics."""
        job=self._request('/api/v1/desktop/capture',dict(path=str(Path(path).resolve()),include_ui=include_ui,overwrite=overwrite))
        deadline=time.monotonic()+timeout_s
        while time.monotonic()<deadline:
            reply=self._request('/api/v1/desktop/capture?'+urlencode({'id':job['id']}))
            if reply['status']=='CAPTURED':return reply
            if reply['status']=='ERROR':raise RuntimeError(reply['error'])
            time.sleep(.05)
        raise TimeoutError('PNG capture timed out. Keep the ASTRA desktop renderer open.')
    def telemetry(self,samples=None,interval_s=.1):
        """Read snapshots at a wall-clock interval, without integrating time."""
        if interval_s<=0:raise ValueError('interval_s must be positive')
        index=0
        while samples is None or index<samples:
            yield self.state();index+=1
            if samples is None or index<samples:time.sleep(interval_s)
    def play(self):return self._request('/api/v1/desktop/play',{})
    def free_flight(self,vehicle='space',scenario='mission',**kwargs):
        """Reset into free flight, paused and manual; play() starts the clock."""
        return self._request('/api/v1/desktop/free',dict(vehicle=vehicle,scenario=scenario,**kwargs))
    def game_catalog(self,vehicle=None,**filters):
        """Legacy story catalog; source='all' adds paged procedural Gioca contracts.

        Optional filters: language, query, difficulty, family, max_duration_s,
        source, sort, offset, limit. Existing positional calls are unchanged.
        """
        return self._request('/api/v1/desktop/game/catalog',dict(filters,**({} if vehicle is None else {'vehicle':vehicle})))
    def start_game_mission(self,mission_id,**options):
        """Load a Gioca career mission paused; call play() to begin its clock."""
        return self._request('/api/v1/desktop/game/start',dict(options,mission_id=mission_id))
    def retry_game_mission(self):return self._request('/api/v1/desktop/game/retry',{})
    def next_game_mission(self):return self._request('/api/v1/desktop/game/next',{})
    def game_checkpoint(self,restore=False):
        return self._request('/api/v1/desktop/game/checkpoint',{'action':'restore' if restore else 'save'})
    def favorite_game_mission(self,mission_id,favorite=True):
        return self._request('/api/v1/desktop/game/favorite',{'mission_id':mission_id,'favorite':favorite})
    def game_state(self):return self._request('/api/v1/desktop/game/state')
    def game_career(self):return self._request('/api/v1/desktop/game/career')
    def upgrade_facility(self,facility):
        return self._request('/api/v1/desktop/game/career/upgrade',{'facility':facility})
    def unlock_technology(self,technology):
        return self._request('/api/v1/desktop/game/career/unlock',{'technology':technology})
    def flight_details(self):return self._request('/api/v1/desktop/flight-details')
    def pause(self):return self._request('/api/v1/desktop/pause',{})
    def set_speed(self,speed=1):return self._request('/api/v1/desktop/speed',{'speed':speed})
    def acquire_clock(self,owner='external'):
        return self._request('/api/v1/desktop/clock',{'owner':owner})
    def recording(self):return self._request('/api/v1/desktop/recording')
    def configure_systems(self,**kwargs):return self._request('/api/v1/systems/configure',kwargs)
    def configure_route(self,**kwargs):return self._request('/api/v1/mission/route',kwargs)
    def robustness(self,**kwargs):return self._request('/api/v1/robustness',kwargs)
    def convergence(self,**kwargs):return self._request('/api/v1/convergence',kwargs)
    def verify_requirements(self,requirements):
        return self._request('/api/v1/requirements/verify',{'requirements':requirements})
    def celestial(self,date=None):
        return self._request('/api/v1/celestial'+('?' + urlencode({'date':date}) if date else ''))
    def transfer(self,target,date=None,elapsed_s=None):
        query={'target':target}
        if date:query['date']=date
        if elapsed_s is not None:query['elapsed_s']=elapsed_s
        return self._request('/api/v1/transfer'+('/state' if elapsed_s is not None else '')+'?'+urlencode(query))
    @classmethod
    def launch_desktop(cls,executable,port=8765,quality='auto',timeout_s=45):
        """Explicitly start a local desktop instance, then connect to its API."""
        executable=Path(executable).expanduser().resolve()
        if not executable.is_file():raise FileNotFoundError(executable)
        process=subprocess.Popen([str(executable),'--port',str(port),'--quality',quality],
            cwd=executable.parent,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        deadline=time.monotonic()+timeout_s
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError('ASTRA Desktop terminated during startup')
            try:
                client=cls(timeout_s=5)
                status=client.status()
                if status.get('process_id')==process.pid:
                    client.desktop_process=process;return client
            except (ConnectionError,RuntimeError):pass
            time.sleep(.1)
        raise TimeoutError('Desktop API startup timeout; inspect ASTRA logs')
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def close(self):
        # Closing the SDK does not terminate a user's interactive application.
        pass
