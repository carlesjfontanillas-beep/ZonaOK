import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location('zok_'+name,ROOT/'scripts'/name)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

m=load('zonaok_fecapa_unificat.py')
c=load('zonaok_classificacions_auto.py')


def fixture(iso=None,mid='151001'):
    return {'iso':iso or m.local_today().isoformat(),'time':'16:00','home':'BARÇA','away':'CH MATARÓ',
            'competition':'ALEVÍ OR 3','leagueId':'4789','matchId':mid,
            'homeScore':1,'awayScore':2,'status':'FINAL','actaState':'available'}

def old_document(r):
    return {'schema':'zonaok-partits-total-v1','season':'2026/2027','sources':{},'matches':[r]}

def packet(mode,rows,at=None,scope='fast'):
    return {'schema':'zonaok-captura-v1','kind':mode,'season':'2026/2027',
            'capturedAt':at or datetime.now(timezone.utc).isoformat(),
            'scope':scope,'selection':{},'rows':rows}

def team(pos,name,played=4,points=10):
    return {'pos':str(pos),'team':name,'played':str(played),'points':str(points),
            'gf':'15','ga':'5','difference':'10',
            'stats':{'PTS':str(points),'PJ':str(played),'PG':'3','PE':'1','PP':'0','GF':'15','GC':'5','DIF':'10'}}

class TestSmartSync(unittest.TestCase):
    def test_final_with_verified_acta_is_frozen_after_7_days(self):
        prior=fixture((m.local_today()-timedelta(days=14)).isoformat())
        row={**prior,'homeScore':9,'awayScore':9}
        doc,stats=m.merge_unified(packet('directe',[row]),old_document(prior),'directe')
        self.assertEqual((doc['matches'][0]['homeScore'],doc['matches'][0]['awayScore']),(1,2))
        self.assertEqual(stats['unchanged'],1)
    def test_recent_final_can_still_receive_corrections(self):
        prior=fixture((m.local_today()-timedelta(days=3)).isoformat())
        row={**prior,'homeScore':3,'awayScore':2}
        doc,stats=m.merge_unified(packet('directe',[row]),old_document(prior),'directe')
        self.assertEqual(doc['matches'][0]['homeScore'],3)
        self.assertEqual(stats['updated'],1)
    def test_pending_old_acta_is_not_frozen(self):
        prior=fixture((m.local_today()-timedelta(days=40)).isoformat())
        prior['actaState']='pending'
        self.assertFalse(m.archived_complete(prior))
    def test_checked_old_acta_waits_seven_days(self):
        prior=fixture((m.local_today()-timedelta(days=40)).isoformat())
        prior['actaState']='pending'
        prior['actaCheckedAt']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        self.assertFalse(m.eligible_acta(prior,'fast'))
        prior['actaCheckedAt']=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
        self.assertTrue(m.eligible_acta(prior,'fast'))
    def test_checked_verified_old_acta_never_checked(self):
        prior=fixture((m.local_today()-timedelta(days=40)).isoformat())
        self.assertFalse(m.eligible_acta(prior,'fast'))
        self.assertFalse(m.eligible_acta(prior,'full'))
    def test_empty_fast_capture_is_noop(self):
        prior=old_document(fixture())
        result,stats=m.merge_unified(packet('directe',[]),prior,'directe')
        self.assertEqual(prior,result)
        self.assertTrue(stats['skipEmpty'])
    def test_empty_full_capture_is_error(self):
        with self.assertRaises(ValueError):m.merge_unified(packet('agenda',[],scope='full'),old_document(fixture()),'agenda')
    def test_full_agenda_cursor_advances_in_batches(self):
        from types import SimpleNamespace
        d={'sources':{'agenda':{'nextFullOffset':20}},'matches':[]}
        diag={}
        ids=[str(x) for x in range(4774,4860)]
        got,meta=m.select_league_batch(ids,SimpleNamespace(scope='full',offset='auto',limit=20),d,diag)
        self.assertEqual(len(got),20)
        self.assertEqual(got[0],ids[20])
        self.assertEqual(meta['nextFullOffset'],40)
    def test_fast_agenda_prioritizes_favourites_and_rotates(self):
        from types import SimpleNamespace
        d={'sources':{'agenda':{'nextFastOffset':3}},'matches':[fixture()]}
        ids=[str(x) for x in range(4774,4820)]
        got,meta=m.select_league_batch(ids,SimpleNamespace(scope='fast',offset='auto',limit=20),d,{})
        self.assertIn('4789',got)
        self.assertEqual(len(got),20)
        self.assertNotEqual(meta['nextFastOffset'],3)
    def test_construct_acta_if_existing_field_empty(self):
        r=fixture();r['actaUrl']=''
        self.assertIn('partido=151001',m.canonicalize(r)['actaUrl'])
    def test_classifications_preserve_metadata_and_order(self):
        key='4789:alevi-or-3'
        before={'schema':'zonaok-classificacions-v2','capturedAt':'2026-11-23T00:00:00Z',
          'competitions':{key:{'name':'ALEVÍ OR 3','category':'ALEVÍ','competition':'ALEVÍ OR',
                                'leagueId':'4789','url':'https://www.hoqueipatins.fecapa.cat/antic',
                                'standingsAt':'2026-11-23T00:00:00Z',
                                'standings':[team(1,'BARÇA'),team(2,'CH MATARÓ')]}}}
        capture={'kind':'classificacions-total','source':'FECAPA-SAFARI',
                 'capturedAt':'2026-11-24T00:00:00Z',
                 'competitions':{key:{'name':'ALEVÍ OR 3','leagueId':'4789',
                  'rows':[team(2,'BARÇA',points=9),team(1,'CH MATARÓ',points=12)]}}}
        result,stats=c.merge_packet(capture,before)
        x=result['competitions'][key]
        self.assertEqual(x['url'],before['competitions'][key]['url'])
        self.assertEqual(x['category'],'ALEVÍ')
        self.assertEqual([r['team'] for r in x['standings']],['CH MATARÓ','BARÇA'])
        self.assertEqual(x['standings'][1]['points'],'9')
        self.assertEqual(stats['updatedGroups'],1)
    def test_classifications_preserve_old_unseen_groups(self):
        good={'name':'Aleví OR 3','category':'ALEVÍ','competition':'ALEVÍ OR','leagueId':'4789',
              'standings':[team(1,'BARÇA'),team(2,'CH MATARÓ')]}
        existing={'schema':'zonaok-classificacions-v2','competitions':{
            '4789:alevi-or-3':good,
            '4822:benjami-or-1':{**good,'leagueId':'4822'}}}
        packet={'source':'FECAPA-SAFARI','kind':'classificacions-total',
                'capturedAt':'2026-11-24T01:00:00Z',
                'competitions':{'4789:alevi-or-3':{**good,'rows':good['standings']}}}
        result,_=c.merge_packet(packet,existing)
        self.assertIn('4822:benjami-or-1',result['competitions'])

if __name__=='__main__':unittest.main()

class TestReconciliation(unittest.TestCase):
    def test_league_and_match_id_enrich_fixture_with_different_category_label(self):
        old=fixture();old['matchId']='';old['leagueId']='';old['competition']='ALEVÍ GRUP 3'
        incoming={**fixture(),'competition':'ALEVÍ OR 3'}
        doc,stats=m.merge_unified(packet('agenda',[incoming]),old_document(old),'agenda')
        self.assertEqual(stats['new'],0)
        self.assertEqual(doc['matches'][0]['matchId'],'151001')
        self.assertEqual(len(doc['matches']),1)
    def test_agenda_cannot_override_previous_live_result(self):
        old=fixture();old['homeScore']=6;old['awayScore']=1
        old['scoreSource']='En directe'
        old['directeUpdatedAt']='2026-11-23T15:00:00Z'
        incoming={**fixture(),'homeScore':0,'awayScore':0}
        doc,_=m.merge_unified(packet('agenda',[incoming]),old_document(old),'agenda')
        self.assertEqual((doc['matches'][0]['homeScore'],doc['matches'][0]['awayScore']),(6,1))
