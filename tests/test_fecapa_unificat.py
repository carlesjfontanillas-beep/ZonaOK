import importlib.util, json, os, tempfile, unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'zonaok_fecapa_unificat.py'
spec=importlib.util.spec_from_file_location('zok_unificat',SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def packet(kind, rows, at='2026-11-23T18:00:00Z'):
    return {'schema':'zonaok-captura-v1','kind':kind,'season':'2026/2027','capturedAt':at,'rows':rows}


def row(mid='151001', league='4789', home='BARÇA', away='CP SANT CELONI'):
    return {'iso':'2026-11-22','time':'17:00','competition':'ALEVÍ OR 3','leagueId':league,
            'matchId':mid,'home':home,'away':away,'homeScore':None,'awayScore':None,
            'status':'','venue':'Pista A'}


class TestUnified(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=os.getcwd();os.chdir(self.tmp.name)
        self.empty={'schema':'zonaok-partits-total-v1','season':'2026/2027','sources':{},'matches':[]}
    def tearDown(self):os.chdir(self.old);self.tmp.cleanup()
    def test_agenda_adds_and_constructs_acta_url_without_claiming_available(self):
        got,stats=m.merge_unified(packet('agenda',[row()]),self.empty,'agenda')
        self.assertEqual(stats['new'],1);self.assertEqual(got['stats']['withActaLinks'],1)
        p=got['matches'][0]
        self.assertEqual(p['actaUrl'],'https://www.hoqueipatins.fecapa.cat/?liga=4789&vista=calendar&partido=151001')
        self.assertEqual(p['actaState'],'pending')
    def test_directe_only_updates_existing_and_preserves_other_rows(self):
        a,_=m.merge_unified(packet('agenda',[row(),row(mid='151002',home='CC VILANOVA')]),self.empty,'agenda')
        upd={**row(),'homeScore':3,'awayScore':1,'status':'FINAL'}
        ghost={**row(mid='199999',home='INVENTAT'),'homeScore':5,'awayScore':0}
        b,stats=m.merge_unified(packet('directe',[upd,ghost],at='2026-11-23T19:00:00Z'),a,'directe')
        self.assertEqual(stats['unmatched'],1)
        self.assertEqual(len(b['matches']),2)
        self.assertEqual(next(x for x in b['matches'] if x['matchId']=='151001')['homeScore'],3)
        self.assertIsNone(next(x for x in b['matches'] if x['matchId']=='151002')['homeScore'])
    def test_older_directe_does_not_replace_newer_result(self):
        a,_=m.merge_unified(packet('agenda',[row()]),self.empty,'agenda')
        new={**row(),'homeScore':4,'awayScore':2}
        b,_=m.merge_unified(packet('directe',[new],at='2026-11-23T19:00:00Z'),a,'directe')
        stale={**new,'homeScore':0,'awayScore':0}
        c,stats=m.merge_unified(packet('directe',[stale],at='2026-11-23T18:00:00Z'),b,'directe')
        self.assertEqual(c['matches'][0]['homeScore'],4);self.assertEqual(stats['unchanged'],1)
    def test_acta_pending_does_not_downgrade_verified(self):
        a,_=m.merge_unified(packet('agenda',[row()]),self.empty,'agenda')
        url=m.make_match_url('4789','151001')
        act={'leagueId':'4789','matchId':'151001','actaUrl':url,'actaState':'available','actaCheckedAt':'2026-11-23T20:00:00Z'}
        b,_=m.merge_unified(packet('actes',[act],at='2026-11-23T20:00:00Z'),a,'actes')
        act2={**act,'actaState':'pending','actaCheckedAt':'2026-11-23T21:00:00Z'}
        c,_=m.merge_unified(packet('actes',[act2],at='2026-11-23T21:00:00Z'),b,'actes')
        self.assertEqual(c['matches'][0]['actaState'],'available')
    def test_compat_app_schemas_and_fixtures(self):
        a,_=m.merge_unified(packet('agenda',[row()]),self.empty,'agenda')
        ret=m.write_compatibility(a)
        agenda=json.loads(Path('zonaok-tots-agenda.json').read_text())
        results=json.loads(Path('zonaok-tots-resultats-7dies.json').read_text())
        actes=json.loads(Path('zonaok-actes.json').read_text())
        self.assertEqual(agenda['schema'],'zonaok-all-v1')
        self.assertEqual(results['kind'],'resultats-7dies')
        self.assertEqual(results['agendaCount'],1)
        self.assertEqual(actes['fixtures'][0]['id'],'151001')
        self.assertEqual(actes['fixtures'][0]['actaUrl'],m.make_match_url('4789','151001'))
    def test_capture_empty_does_not_publish(self):
        with self.assertRaises(ValueError):m.merge_unified(packet('agenda',[]),self.empty,'agenda')
    def test_protect_existing_json_unknown_schema(self):
        Path('zonaok-tots-partits.json').write_text('{"schema":"unknown","matches":[]}')
        with self.assertRaises(ValueError):m.load_unified(Path('zonaok-tots-partits.json'))
    def test_reconcile_original_legacy_agenda(self):
        Path('zonaok-tots-agenda.json').write_text(json.dumps({'schema':'zonaok-all-v1','rows':[row()]}))
        x=m.load_unified(Path('zonaok-tots-partits.json'))
        self.assertEqual(len(x['matches']),1)

if __name__=='__main__':unittest.main()
