"""Browser-only HTTP-compatible dispatcher built from ASTRA 1.3 engine.

This runs INSIDE Pyodide's dedicated worker. It does not listen on network
ports and does not expose an external API endpoint.
"""
import json
from urllib.parse import urlsplit, parse_qs
from astra import __version__
from astra.engine import SimulationEngine, MODEL_CATALOG
from astra.engineering import SOLVERS, run_engineering_analysis
from astra.vehicle_design import vehicle_parts_catalog
from astra.celestial import celestial_catalog, transfer_plan, transfer_state
from astra.convergence import run_convergence_study
from astra.robustness import run_robustness_campaign
from astra.verification import verify_requirements
from astra.mission_context import run_live_study

engine = SimulationEngine()
transfer_cache = {}

def route_raw(raw):
    try:
        request = json.loads(raw)
        path = request.get('path', '')
        payload = request.get('payload') or {}
        if not isinstance(payload, dict):
            raise ValueError('Request body must be an object')
        parsed = urlsplit(path)
        endpoint = parsed.path
        query = parse_qs(parsed.query)
        if endpoint in ('/state', '/api/v1/state'):
            result = engine.state()
        elif endpoint == '/status':
            st = engine.state()
            result = {'name': 'ASTRA', 'version': __version__, 'api':'browser-worker',
                      'execution_mode': 'browser-pyodide',
                      'vehicle': engine.vehicle, 'model': st.get('model'),
                      'time_s':st.get('time_s'),
                      'sas':st.get('sas'),
                      'capabilities':['spacecraft','aircraft','uav','rk4','si-units',
                                      'browser-local-engine','gnc','engineering-studio']}
        elif endpoint == '/models':
            result = MODEL_CATALOG
        elif endpoint == '/engineering/live':
            result = run_live_study(engine, payload)
        elif endpoint == '/engineering' and request.get('method') == 'GET':
            result = {'solvers':list(SOLVERS), 'units':'SI',
                      'mode':'isolated-design-analysis','scope':'educational models'}
        elif endpoint == '/engineering':
            result = run_engineering_analysis(payload)
        elif endpoint == '/vehicle-parts':
            result = vehicle_parts_catalog()
        elif endpoint == '/celestial':
            result = celestial_catalog(query.get('date', [None])[0])
        elif endpoint in ('/transfer', '/transfer/state'):
            target = query.get('target',[''])[0]
            date = query.get('date',[None])[0]
            key = (target,date)
            if key not in transfer_cache:
                if len(transfer_cache)>12: transfer_cache.clear()
                transfer_cache[key] = transfer_plan(target,date)
            result = (transfer_cache[key] if endpoint == '/transfer' else
                      transfer_state(transfer_cache[key],float(query.get('elapsed_s',[''])[0])))
        elif endpoint == '/requirements/verify':
            result = verify_requirements(engine.state(),payload.get('requirements'))
        elif endpoint == '/convergence':
            result = run_convergence_study(payload)
        elif endpoint == '/robustness':
            result = run_robustness_campaign(payload)
        elif endpoint == '/reset':
            result = engine.reset(payload.get('vehicle','space'),
                                  payload.get('scenario','mission'),
                                  payload.get('model_id'),payload.get('custom_design'),
                                  payload.get('wind_ned_m_s'),payload.get('turbulence'),
                                  payload.get('wind_profile_ned_m_s'),
                                  payload.get('surface_layer_wind'),
                                  payload.get('advanced_models',False),
                                  payload.get('science_configuration'))
        elif endpoint == '/mission/route':
            if engine.vehicle != 'drone' or engine.mission_started:
                raise ValueError('Select a ready UAV mission before applying a route')
            plan = run_engineering_analysis(dict(payload, analysis='robotics_route'))
            result = engine.configure_route(plan)
        elif endpoint == '/systems/configure':
            result = engine.configure_systems(payload)
        elif endpoint == '/launch':
            result = engine.launch()
        elif endpoint == '/stage':
            result = engine.stage()
        elif endpoint == '/command':
            result = engine.set_command(payload)
        elif endpoint == '/step':
            result = engine.step(payload.get('dt_s',0.0))
        elif endpoint == '/fault':
            result = engine.inject_fault(payload)
        elif endpoint == '/fault/clear':
            result = engine.clear_faults()
        else:
            raise ValueError('Unsupported browser API path: '+endpoint)
        return json.dumps({'ok':True,'data':result},allow_nan=False,separators=(',',':'))
    except (ValueError,TypeError,KeyError,ArithmeticError) as error:
        return json.dumps({'ok':False,'error':str(error)},ensure_ascii=False)
