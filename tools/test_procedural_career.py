"""Measured Gioca progression, save compatibility and seed validation."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from astra.procedural_missions import generate_mission
from desktop_runtime import DesktopRuntime
from tools.validate_missions import validate

class ProceduralCareerTests(unittest.TestCase):
 def test_distinct_physical_catalog_and_bounds(self):
  result=validate(100)
  self.assertTrue(result['passed'])
  self.assertTrue(all(v>=300 for v in result['physically_distinct_contracts'].values()))
 def test_seed_and_language_are_deterministic(self):
  a=generate_mission('space_lunar_precision',0)
  self.assertEqual(a,generate_mission('space_lunar_precision',0))
  b=generate_mission('space_lunar_precision',0,'en')
  self.assertEqual(a['setup'],b['setup']);self.assertNotEqual(a['briefing'],b['briefing'])
 def test_runtime_checkpoint_retry_and_legacy_save(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
   path=Path(folder)/'career.json';path.write_text(json.dumps({'credits':12345,'completed_missions':['space_skyward']}))
   with patch.object(DesktopRuntime,'_career_file',staticmethod(lambda:path)):
    r=DesktopRuntime();self.assertEqual(r.career['credits'],12345)
    rows=r.dispatch('/desktop/game/catalog',{'vehicle':'drone','source':'contracts','limit':10},'POST')
    self.assertEqual(len(rows['drone']),10);self.assertEqual(rows['_meta']['total'],384)
    r.dispatch('/desktop/game/start',{'mission_id':'proc1:space_lunar_precision:0'},'POST')
    identity=id(r.engine);before=r.engine.state()
    r.dispatch('/desktop/game/checkpoint',{'action':'save'},'POST')
    r.engine.launch();r._step(.5)
    r.dispatch('/desktop/game/checkpoint',{'action':'restore'},'POST')
    self.assertEqual(id(r.engine),identity);self.assertEqual(r.engine.state(),before)
    r.dispatch('/desktop/game/retry',{},'POST');self.assertEqual(r.engine.t,0)
    saved=json.loads(path.read_text());self.assertNotIn('briefing',json.dumps(saved))
 def test_invalid_filters_do_not_advance_engine(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
   with patch.object(DesktopRuntime,'_career_file',staticmethod(lambda:Path(folder)/'career.json')):
    r=DesktopRuntime();before=r.engine.state()
    for payload in [{'source':'nope'},{'difficulty':True},{'limit':0},{'max_duration_s':float('nan')}]:
     with self.assertRaises(ValueError):r.dispatch('/desktop/game/catalog',payload,'POST')
    self.assertEqual(before,r.engine.state())

if __name__=='__main__':unittest.main()

