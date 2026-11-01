"""Desktop presentation state. Deliberately independent of scientific state."""
import copy
import json
import math
from pathlib import Path
import secrets
import sys
import time


class NativeVisuals:
    def __init__(self):
        root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
        path=root/'desktop-vehicles.json' if getattr(sys,'frozen',False) else root/'desktop/vehicles.json'
        self.catalog=json.loads(path.read_text(encoding='utf-8'))
        self.ids={entry['id'] for entry in self.catalog['models']}
        self.settings=dict(model='auto',azimuth_deg=37.24,elevation_deg=14.32,distance_m=None,
                           show_ui=True,exposure=1.,nebula_strength=.9,resolution_scale=.67,quality='balanced',auto_exposure=False,depth_of_field=False,audio_enabled=True,audio_volume=.6,cinematic_effects=True,enhanced_materials=True,earthshine=True)
        self.revision=0;self.jobs={};self.renderer={};self.renderer_wall=None
        self.changed=list(self.settings)

    def view(self):return dict(revision=self.revision,settings=copy.deepcopy(self.settings),changed=list(self.changed))

    def update(self,payload):
        if not set(payload).issubset(self.settings):raise ValueError('Unknown presentation setting')
        settings=dict(self.settings,**payload)
        if settings['model'] not in self.ids|{'auto'}:raise ValueError('Choose a model ID from desktop/assets')
        if settings['quality'] not in {'low','balanced','high','ultra','cinema'}:raise ValueError('quality must be low, balanced, high, ultra or cinema')
        if any(not isinstance(settings[key],bool) for key in ('enhanced_materials','earthshine')):raise ValueError('Material and lighting controls must be boolean')
        if not isinstance(settings['show_ui'],bool):raise ValueError('show_ui must be boolean')
        if not isinstance(settings['audio_enabled'],bool):raise ValueError('audio_enabled must be boolean')
        if not isinstance(settings['cinematic_effects'],bool):raise ValueError('cinematic_effects must be boolean')
        if not isinstance(settings['auto_exposure'],bool) or not isinstance(settings['depth_of_field'],bool):raise ValueError('Camera effects must be boolean')
        ranges=dict(azimuth_deg=(-360,360),elevation_deg=(-45,80),distance_m=(.3,50000000),
                    exposure=(.1,5),nebula_strength=(0,2),resolution_scale=(.5,1.5),audio_volume=(0,1))
        for key,(low,high) in ranges.items():
            value=settings[key]
            if key=='distance_m' and value is None:continue
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
                raise ValueError(f'{key} must be finite, between {low} and {high}')
        self.settings=settings;self.changed=list(payload);self.revision+=1
        return self.view()

    def capture(self,payload):
        path=Path(str(payload.get('path',''))).expanduser()
        if not path.is_absolute() or path.suffix.lower()!='.png':raise ValueError('Capture path must be an absolute PNG filename')
        path=path.resolve()
        if not path.parent.is_dir():raise ValueError('Capture directory does not exist')
        if path.exists() and not payload.get('overwrite',False):raise ValueError('Capture file already exists; set overwrite explicitly')
        if not isinstance(payload.get('include_ui',False),bool):raise ValueError('include_ui must be boolean')
        if sum(j['status']=='PENDING' for j in self.jobs.values())>=4:raise ValueError('Capture queue is full')
        while len(self.jobs)>=32:
            old=next((key for key,value in self.jobs.items() if value['status']!='PENDING'),None)
            if old is None:break
            del self.jobs[old]
        job=dict(id=secrets.token_hex(12),path=str(path),include_ui=payload.get('include_ui',False),status='PENDING')
        self.jobs[job['id']]=job
        return copy.deepcopy(job)

    def pending(self):return [copy.deepcopy(j) for j in self.jobs.values() if j['status']=='PENDING']

    def complete(self,payload):
        job=self.jobs[payload['id']]
        if job['status']!='PENDING':return copy.deepcopy(job)
        error=str(payload.get('error',''))[:500]
        path=Path(job['path'])
        if not error and (not path.is_file() or path.stat().st_size<32):error='Renderer did not create a PNG file'
        job.update(status='ERROR' if error else 'CAPTURED',error=error)
        if not error:job.update(bytes=path.stat().st_size,width=int(payload.get('width',0)),height=int(payload.get('height',0)))
        return copy.deepcopy(job)

    def render_report(self,payload=None):
        if payload is not None:
            allowed={'backend','adapter','fps','draw_calls','primitives','objects','asset_id','asset_file',
                     'asset_error','asset_loaded','cache_loads','cache_hits','view_revision','resolution_scale','camera',
                     'input_revision','input_rtt_ms','frame_time_ms'}
            if not set(payload).issubset(allowed):raise ValueError('Unknown renderer report field')
            self.renderer=copy.deepcopy(payload);self.renderer_wall=time.monotonic()
        age=time.monotonic()-self.renderer_wall if self.renderer_wall else None
        return dict(connected=age is not None and age<5,age_s=age,**copy.deepcopy(self.renderer))
