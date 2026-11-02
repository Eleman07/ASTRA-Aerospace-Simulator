"""Publish the verified 2.5.3 upgrade using configured Git credentials."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(args,**kw):return subprocess.run(args,cwd=ROOT,check=True,**kw)
def main():
 build=json.loads((ROOT/'dist/desktop-build.json').read_text())
 installer=json.loads((ROOT/'dist/desktop-installer.json').read_text())
 package=json.loads((ROOT/'test-results/desktop-package-validation.json').read_text())
 assert build['version']==installer['version']=='2.5.3'
 assert installer['installer_test']==installer['uninstaller_test']=='PASS'
 for key,source in [('host_sha256','executable_sha256'),('renderer_sha256','renderer_sha256'),('sdk_sha256','sdk_sha256')]:assert package[key]==build[source]
 for path in ['docs/validation/missions.json','docs/validation/mission-flight-witnesses.json','docs/validation/mission-manual-flight-witnesses.json']:
  assert json.loads((ROOT/path).read_text())['passed']
 files=[ROOT/'dist'/installer['installer'],ROOT/'dist'/build['sdk']]
 assert hashlib.sha256(files[0].read_bytes()).hexdigest()==installer['sha256']
 assert hashlib.sha256(files[1].read_bytes()).hexdigest()==build['sdk_sha256']
 env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
 r=run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=env)
 fields=dict(x.split('=',1) for x in r.stdout.splitlines() if '=' in x)
 token=fields.get('password');assert token,'No configured GitHub credential'
 env['GH_TOKEN']=token
 tag='v2.5.3-desktop';repo='Eleman07/ASTRA-Aerospace-Simulator'
 probe=subprocess.run(['gh','release','view',tag,'--repo',repo],env=env,cwd=ROOT,capture_output=True)
 assert probe.returncode!=0,'Release already exists; inspect before changing it'
 run(['git','push','origin','HEAD:main'],env=env)
 run(['gh','release','create',tag,*map(str,files),'--repo',repo,'--target',subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'--title','ASTRA Desktop 2.5.3 — SAS e missioni GIOCA','--notes-file',str(ROOT/'docs/RELEASE-2.5.3.md')],env=env)
 result=run(['gh','release','view',tag,'--repo',repo,'--json','url,assets,tagName,isDraft'],env=env,capture_output=True,text=True)
 receipt=json.loads(result.stdout);assert not receipt['isDraft'] and len(receipt['assets'])==2
 (ROOT/'dist/desktop-github-release.json').write_text(json.dumps(receipt,indent=2))
 print(receipt['url'])
if __name__=='__main__':main()
