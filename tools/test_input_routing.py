"""Exercise real Godot GUI input events, recording the exact tested sources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    sources=['desktop/main.gd','desktop/native_input.gd','desktop/menu_window.gd','tools/test_input_pipeline.gd']
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources}
    env=dict(os.environ)
    for variable,relative in [('APPDATA','build/input-test-user'),('TEMP','build/godot-temp'),('TMP','build/godot-temp')]:
        path=ROOT/relative;path.mkdir(parents=True,exist_ok=True);env[variable]=str(path)
    result=subprocess.run([str(ROOT/'build/toolchain/godot/Godot_v4.7.2-stable_win64_console.exe'),'--headless',
        '--path',str(ROOT/'desktop'),'--script',str(ROOT/'tools/test_input_pipeline.gd')],
        capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,cwd=ROOT,timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW)
    output=result.stdout+result.stderr
    (ROOT/'test-results/input-routing.log').write_text(output,encoding='utf-8')
    if result.returncode or 'INPUT PIPELINE PASS:' not in output or 'SCRIPT ERROR:' in output or '\nERROR:' in output:
        raise AssertionError(output)
    assert hashes=={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources}
    report=dict(version=build['version'],result='PASS',test_backend='Godot headless with injected GUI events',
        source_sha256=hashes,sticks_do_not_navigate=True,child_window_values_unchanged=True,
        dpad_navigates=True,a_confirms=True,b_closes_panel=True,start_toggles_once=True,
        python_clock_exclusive=True,hotas_one_profile=True,hotas_one_button_routing=True,hotas_profile=True,hotas_absolute_throttle=True,hotas_button_routing=True,hotas_child_menu_isolation=True,physical_controller_test=False)
    (ROOT/'test-results/input-routing-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
