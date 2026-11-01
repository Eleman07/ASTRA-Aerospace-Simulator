"""Build native Godot + unchanged Python engine and dependency-free SDK wheel."""
from __future__ import annotations
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='2.5.2'
SDK_VERSION='2.5.2'
TOOLCHAIN=ROOT/'build/toolchain/godot'
PAYLOAD=ROOT/f'dist/ASTRA-Desktop-{VERSION}'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build_sdk():
    """Standard wheel layout with RECORD hashes; no packaging downloads needed."""
    name='astra_simulator_client';meta=f'{name}-{SDK_VERSION}.dist-info'
    files={'astra/__init__.py':(ROOT/'astra/__init__.py').read_bytes(),
           'astra/client.py':(ROOT/'astra/client.py').read_bytes(),
           'astra_sdk/__init__.py':(ROOT/'astra_sdk/__init__.py').read_bytes(),
           'astra_sdk/client.py':(ROOT/'astra_sdk/client.py').read_bytes(),
           'astra_desktop_client/__init__.py':b'from astra_sdk import AstraClient, CLIENT_VERSION\n__all__=["AstraClient","CLIENT_VERSION"]\n',
           meta+'/WHEEL':b'Wheel-Version: 1.0\nGenerator: ASTRA Desktop Builder\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
           meta+'/licenses/LICENSE':(ROOT/'LICENSE').read_bytes(),
           meta+'/METADATA':f'Metadata-Version: 2.4\nName: astra-simulator-client\nVersion: {SDK_VERSION}\nSummary: ASTRA native desktop and legacy HTTP Python SDK\nRequires-Python: >=3.10\nLicense-Expression: MIT\nLicense-File: licenses/LICENSE\n\nConnect to ASTRA Desktop; scientific API v1 compatibility retained.\n'.encode()}
    rows=[]
    for path,data in files.items():
        encoded=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        rows.append([path,'sha256='+encoded,str(len(data))])
    rows.append([meta+'/RECORD','',''])
    out=io.StringIO(newline='');csv.writer(out,lineterminator='\n').writerows(rows)
    files[meta+'/RECORD']=out.getvalue().encode()
    wheel=ROOT/'dist'/f'{name}-{SDK_VERSION}-py3-none-any.whl'
    with zipfile.ZipFile(wheel,'w',zipfile.ZIP_DEFLATED) as archive:
        for path,data in files.items():
            info=zipfile.ZipInfo(path,date_time=(2026,10,28,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            archive.writestr(info,data)
    return wheel


def main():
    if sys.platform!='win32':raise SystemExit('Build the Windows desktop distribution on Windows')
    (ROOT/'dist').mkdir(exist_ok=True);PAYLOAD.mkdir(parents=True,exist_ok=True)
    editor=TOOLCHAIN/'Godot_v4.7.2-stable_win64_console.exe'
    template=TOOLCHAIN/'windows_release_x86_64.exe'
    if not editor.exists() or not template.exists():raise SystemExit('Verified Godot toolchain missing')
    godot_env=os.environ.copy()
    godot_data=ROOT/'build/godot-build-user';godot_data.mkdir(parents=True,exist_ok=True)
    godot_env['APPDATA']=str(godot_data)
    godot_temp=ROOT/'build/godot-temp';godot_temp.mkdir(parents=True,exist_ok=True)
    godot_env['TEMP']=str(godot_temp);godot_env['TMP']=str(godot_temp)
    shutil.copy2(ROOT/'icon.svg',ROOT/'desktop/icon.svg')
    icon_script=ROOT/'build/desktop-icon.gd'
    icon_script.write_text('''extends SceneTree
func _initialize():
    var image=Image.new()
    var source=FileAccess.get_file_as_string("res://icon.svg")
    var result=image.load_svg_from_string(source)
    if result!=OK:quit(1);return
    image.resize(256,256,Image.INTERPOLATE_LANCZOS)
    image.save_png("'''+str((ROOT/'build/desktop-icon.png').resolve()).replace('\\','/')+'''")
    quit()
''')
    subprocess.run([str(editor),'--headless','--path',str(ROOT/'desktop'),'--script',str(icon_script)],check=True,cwd=ROOT,env=godot_env)
    png=(ROOT/'build/desktop-icon.png').read_bytes()
    icon=ROOT/'build/desktop-icon.ico'
    icon.write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22)+png)
    preset=ROOT/'desktop/export_presets.cfg'
    preset.write_text('''[preset.0]
name="Windows Desktop"
platform="Windows Desktop"
runnable=true
export_filter="all_resources"
include_filter="*.json"
exclude_filter=""
export_path=""
script_export_mode=2

[preset.0.options]
custom_template/debug=""
custom_template/release="'''+str(template).replace('\\','/')+'''"
binary_format/embed_pck=true
binary_format/architecture="x86_64"
application/modify_resources=false
''',encoding='utf-8')
    subprocess.run([str(editor),'--headless','--editor','--path',str(ROOT/'desktop'),'--import','--quit'],check=True,cwd=ROOT,env=godot_env)
    exported=PAYLOAD/'ASTRA-Renderer.exe'
    subprocess.run([str(editor),'--headless','--path',str(ROOT/'desktop'),'--export-release','Windows Desktop',str(exported)],check=True,cwd=ROOT,env=godot_env)
    check_script=ROOT/'build/check-embedded-project.gd'
    check_script.write_text('''extends SceneTree
func _initialize():
    var paths=OS.get_cmdline_user_args()
    if paths.is_empty() or not ProjectSettings.load_resource_pack(paths[0],true):quit(1);return
    var file=FileAccess.open("res://project.binary",FileAccess.READ)
    if file==null or file.get_buffer(4).get_string_from_ascii()!="ECFG":quit(1);return
    print("EMBEDDED PROJECT PASS")
    quit()
''',encoding='utf-8')
    subprocess.run([str(editor),'--headless','--path',str(ROOT/'desktop'),'--script',str(check_script),'--',str(exported)],check=True,cwd=ROOT,env=godot_env)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','ASTRA',
             '--icon',str(icon),'--collect-submodules','astra','--collect-data','astra','--distpath',str(ROOT/'dist/native-desktop'),
             '--workpath',str(ROOT/'build/native-desktop'),'--specpath',str(ROOT/'build'),str(ROOT/'desktop_runtime.py')]
    subprocess.run(command,check=True,cwd=ROOT)
    shutil.copytree(ROOT/'dist/native-desktop/ASTRA',PAYLOAD,dirs_exist_ok=True)
    shutil.copytree(ROOT/'assets',PAYLOAD/'assets',dirs_exist_ok=True)
    shutil.copy2(ROOT/'desktop/vehicles.json',PAYLOAD/'desktop-vehicles.json')
    for name in ['LICENSE.txt','COPYRIGHT.txt']:
        shutil.copy2(TOOLCHAIN/name,PAYLOAD/('GODOT-'+name))
    shutil.copy2(ROOT/'ASSET-CREDITS.md',PAYLOAD/'ASSET-CREDITS.txt')
    shutil.copy2(ROOT/'LICENSE',PAYLOAD/'ASTRA-LICENSE.txt')
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file():shutil.copy2(python_license,PAYLOAD/'PYTHON-LICENSE.txt')
    shutil.copy2(ROOT/'astra-client.py',PAYLOAD/'astra-client.py')
    wheel=build_sdk();shutil.copy2(wheel,PAYLOAD/wheel.name)
    if (ROOT/'docs/DESKTOP_NATIVE_IT.md').exists():shutil.copy2(ROOT/'docs/DESKTOP_NATIVE_IT.md',PAYLOAD/'GUIDA-DESKTOP.txt')
    subprocess.run([str(PAYLOAD/'ASTRA.exe'),'--self-test'],check=True,cwd=ROOT)
    science={path.relative_to(ROOT).as_posix():digest(path) for path in sorted((ROOT/'astra').glob('*.py')) if path.name!='client.py'}
    report=dict(version=VERSION,native=True,browser_required=False,renderer='Godot 4.7.2',
                payload=str(PAYLOAD),runtime_self_test='PASS',sdk=wheel.name,sdk_sha256=digest(wheel),
                science_sources= science,renderer_bytes=exported.stat().st_size,
                executable_sha256=digest(PAYLOAD/'ASTRA.exe'),renderer_sha256=digest(exported))
    (ROOT/'dist/desktop-build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='science_sources'},indent=2))


if __name__=='__main__':main()
