#!/usr/bin/env python3
"""Proves de seguretat de fusió: no esborra ni altres lligues ni Agenda."""
import copy
import importlib.util
from pathlib import Path
import unittest

FILE=Path(__file__).resolve().parents[1]/'scripts'/'zonaok_v27_import.py'
spec=importlib.util.spec_from_file_location('zonaok_v27_import', FILE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def match(i='146875',date='2026-11-18',tm='18:00',home='FC Barcelona Aleví',away='Club X',h=None,a=None):
    return {'id':i,'iso':date,'time':tm,'competition':'ALEVÍ OR 3','home':home,'away':away,'homeScore':h,'awayScore':a,'venue':'Pavelló A','actaUrl':'https://www.hoqueipatins.fecapa.cat/...'}

def repo():
    return {'zonaok-data.json':{'version':3,'publishedAt':'2026-11-18T10:00:00Z','data':{
        'agenda':{'capturedAt':'2026-11-18T10:00:00Z','rows':[match(),match('146876',home='CP Sant Celoni B',away='Club Y')]},
        'live':{'rows':[{'id':'x'}]}, '4789':{'standings':[{'team':'antic'}],'standingsAt':'2026-11-18T09:00:00Z'},
        '4786':{'standings':[{'team':'antic infantil'}],'standingsAt':'2026-11-18T09:00:00Z'},
        '4784':{'standings':[{'team':'antic juvenil'}],'standingsAt':'2026-11-18T09:00:00Z'},
        'seasons':{'4789':{'rows':[match()] }},'actaIndex':{'4789':{'rows':[match()]}}}},
        'zonaok-classificacio-4789.json':None,
        'zonaok-classificacio-4786.json':None,
        'zonaok-classificacio-4784.json':None}


class TestV27(unittest.TestCase):
    def setUp(self):
        self.files=repo()
    def apply(self,p):
        name,obj,diagnostics=m.apply(p,lambda filename:copy.deepcopy(self.files.get(filename)))
        self.files[name]=copy.deepcopy(obj)
        return name,obj,diagnostics
    def pack(self,kind,rows,league=None,at='2026-11-20T10:00:00Z'):
        out={'source':'FECAPA-SAFARI','kind':kind,'capturedAt':at,'rows':rows}
        if league:out['league']=league
        return out
    def standing(self,league,pt='4',at='2026-11-20T10:00:00Z'):
        return self.pack('standings',[{'pos':'1','team':'Barça','points':pt,'played':'2','stats':{'PJ':'2','PTS':pt}},
                                     {'pos':'2','team':'Rival','points':'2','played':'2','stats':{'PJ':'2','PTS':'2'}}],league,at)
    def test_independent_leagues(self):
        for league in ('4789','4786','4784'):self.apply(self.standing(league))
        self.assertEqual(self.files['zonaok-classificacio-4786.json']['standings'][0]['points'],'4')
        before=copy.deepcopy(self.files['zonaok-classificacio-4786.json'])
        self.apply(self.standing('4789','7',at='2026-11-20T12:00:00Z'))
        self.assertEqual(self.files['zonaok-classificacio-4786.json'],before)
        self.assertEqual(self.files['zonaok-data.json'],repo()['zonaok-data.json'])
    def test_old_standing_is_ignored(self):
        self.apply(self.standing('4789','7','2026-11-20T12:00:00Z'))
        name,obj,diag=self.apply(self.standing('4789','1','2026-11-20T09:00:00Z'))
        self.assertEqual(obj['standings'][0]['points'],'7')
        self.assertIn('conservada',str(diag))
    def test_cross_league_malformed_rejected(self):
        self.files['zonaok-classificacio-4789.json']={'schema':'zonaok-classificacio-v1','league':'4786','standings':[]}
        with self.assertRaises(ValueError):self.apply(self.standing('4789'))
    def test_agenda_packet_rejected(self):
        with self.assertRaises(ValueError):self.apply(self.pack('agenda-season',[match()]))
    def test_empty_standings_rejected(self):
        with self.assertRaises(ValueError):self.apply(self.pack('standings',[],'4789'))
    def test_duplicate_teams_rejected(self):
        with self.assertRaises(ValueError):self.apply(self.pack('standings', [{'team':'FCB'}, {'team':'FCB'}],'4789'))
    def test_unknown_league_rejected(self):
        with self.assertRaises(ValueError):self.apply(self.standing('0000'))
    def test_scores_only_one_match(self):
        orig=copy.deepcopy(self.files['zonaok-data.json'])
        name,obj,report=self.apply(self.pack('resultats-v27',[match(h=0,a=0)]))
        self.assertEqual(name,'zonaok-data.json');self.assertEqual(report['marcadors_actualitzats'],1)
        self.assertEqual(obj['data']['agenda']['rows'][0]['homeScore'],0)
        self.assertEqual(obj['data']['agenda']['rows'][0]['scoreSource'],'En directe')
        self.assertEqual(obj['data']['agenda']['rows'][1],orig['data']['agenda']['rows'][1])
        self.assertEqual(obj['data']['seasons'],orig['data']['seasons'])
        self.assertEqual(obj['data']['4786'],orig['data']['4786'])
        self.assertEqual(obj['data']['actaIndex'],orig['data']['actaIndex'])
        self.assertEqual(obj['data']['agenda']['rows'][0]['venue'],'Pavelló A')
    def test_new_result_wins_after_agenda_capture(self):
        self.files['zonaok-data.json']['data']['agenda']['rows'][0]['capturedAt']='2026-11-20T10:05:00Z'
        name,obj,report=self.apply(self.pack('resultats-v27',[match(h=2,a=1)],at='2026-11-20T10:00:00Z'))
        self.assertEqual(report['marcadors_actualitzats'],1)
        self.assertEqual(obj['data']['agenda']['rows'][0]['homeScore'],2)
    def test_id_preferred_across_date_change(self):
        name,obj,report=self.apply(self.pack('resultats-v27',[match(date='2026-11-19',h=2,a=1)]))
        self.assertEqual(report['marcadors_actualitzats'],1)
        self.assertEqual(obj['data']['agenda']['rows'][0]['iso'],'2026-11-18')
    def test_never_apply_different_id(self):
        with self.assertRaisesRegex(ValueError,'Cap marcador'):
            self.apply(self.pack('resultats-v27',[match(i='no-other',h=2,a=1)]))
    def test_no_created_missing_fixture(self):
        with self.assertRaises(ValueError):self.apply(self.pack('resultats-v27',[match('nonexisting',h=5,a=2)]))
        self.assertEqual(len(self.files['zonaok-data.json']['data']['agenda']['rows']),2)
    def test_no_scores_rejected(self):
        with self.assertRaises(ValueError):self.apply(self.pack('resultats-v27',[match()]))
    def test_older_score_rejected(self):
        self.apply(self.pack('resultats-v27',[match(h=5,a=2)],at='2026-11-20T10:00:00Z'))
        name,obj,report=self.apply(self.pack('resultats-v27',[match(h=1,a=0)],at='2026-11-20T09:00:00Z'))
        self.assertEqual(report['ignorats_antics'],1)
        self.assertEqual(obj['data']['agenda']['rows'][0]['homeScore'],5)
    def test_source_guard(self):
        p=self.standing('4789');p['source']='something-else'
        with self.assertRaises(ValueError):self.apply(p)
    def test_no_agenda_never_created(self):
        del self.files['zonaok-data.json']
        with self.assertRaises(ValueError):self.apply(self.pack('resultats-v27',[match(h=1,a=0)]))

if __name__=='__main__':unittest.main()
