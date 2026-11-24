import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'zonaok_fecapa_unificat.py'
spec=importlib.util.spec_from_file_location('zonaok_fecapa_unificat',SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def sample(i, league='4775'):
    mid=str(160000+i)
    return {'iso':'2026-11-22','time':'18:00','competition':'LLIGA TEST',
            'home':f'LOCAL {i}','away':f'VISITANT {i}',
            'leagueId':league,'matchId':mid,'actaUrl':m.make_match_url(league,mid),
            'actaState':'pending','homeScore':None,'awayScore':None}

class TestActesCompatOver1200(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.prev=os.getcwd()
        os.chdir(self.tmp.name)
    def tearDown(self):
        os.chdir(self.prev)
        self.tmp.cleanup()
    def doc(self,count=1479):
        return {'schema':'zonaok-partits-total-v1','season':'2026/2027',
                'matches':[sample(i) for i in range(count)], 'sources':{}}
    def test_rebuild_1479_actes_without_truncating(self):
        result=m.write_compatibility(self.doc())
        packet=json.loads(Path('zonaok-actes.json').read_text(encoding='utf-8'))
        self.assertEqual(result['legacyActes'],1479)
        self.assertEqual(packet['version'],1)
        self.assertEqual(len(packet['fixtures']),1479)
        self.assertEqual(len({(r['league'],r['id']) for r in packet['fixtures']}),1479)
        self.assertTrue(Path('zonaok-tots-agenda.json').exists())
        self.assertTrue(Path('zonaok-tots-resultats-7dies.json').exists())
    def test_keeps_old_not_present_in_new_snapshot(self):
        old={'version':1,'fixtures':[{'league':'4789','id':'999999',
              'iso':'2026-11-20','time':'17:00','home':'BARÇA',
              'away':'CPS','actaUrl':m.make_match_url('4789','999999')}]}
        Path('zonaok-actes.json').write_text(json.dumps(old),encoding='utf-8')
        result=m.write_compatibility(self.doc())
        packet=json.loads(Path('zonaok-actes.json').read_text(encoding='utf-8'))
        self.assertEqual(result['legacyActes'],1480)
        self.assertIn(('4789','999999'),{(r['league'],r['id']) for r in packet['fixtures']})
    def test_unknown_schema_does_not_overwrite_old_actes(self):
        old='{"schema":"do-not-touch"}'
        Path('zonaok-actes.json').write_text(old,encoding='utf-8')
        report=m.write_compatibility(self.doc(2))
        self.assertEqual(Path('zonaok-actes.json').read_text(),old)
        self.assertIn('Esquema antic desconegut',report['legacyActes'])
    def test_size_guard_still_preserves_existing_file(self):
        original_max=m.MAX_LEGACY_ACTA_FIXTURES
        try:
            m.MAX_LEGACY_ACTA_FIXTURES=2
            old='{"version":1,"fixtures":[]}'
            Path('zonaok-actes.json').write_text(old,encoding='utf-8')
            result=m.write_compatibility(self.doc(3))
            self.assertEqual(Path('zonaok-actes.json').read_text(encoding='utf-8'),old)
            self.assertIn('Conservat',result['legacyActes'])
        finally:
            m.MAX_LEGACY_ACTA_FIXTURES=original_max
    def test_old_results_and_acta_status_unchanged(self):
        d=self.doc(3)
        d['matches'][0]['homeScore']=3
        d['matches'][0]['awayScore']=1
        d['matches'][0]['actaState']='available'
        before=json.dumps(d,sort_keys=True)
        m.write_compatibility(d)
        self.assertEqual(json.dumps(d,sort_keys=True),before)

if __name__=='__main__':
    unittest.main()
