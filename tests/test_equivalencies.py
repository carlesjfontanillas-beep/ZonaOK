import importlib.util
import unittest
from pathlib import Path

p=Path(__file__).resolve().parents[1]/'scripts'/'zonaok_equivalencies.py'
s=importlib.util.spec_from_file_location('zok_equivalencies',p)
m=importlib.util.module_from_spec(s)
s.loader.exec_module(m)

class TestEquivalencies(unittest.TestCase):
    def test_seed_catalog(self):
        c=m.load_catalog()
        self.assertTrue(any(x['team']=='CP SANT CELONI B' and 'CPSCB' in x['shortTeams'] for x in c['manualAliases']))
    def test_distinct_scoped_pairs_only_and_preserve_collisions(self):
        def group(lid,team,short):
            return {'leagueId':lid,'name':'GRUP '+lid,'standings':[{'team':team,'shortTeam':short,'shortTeamSource':m.SOURCE}]}
        c={'teamAliases':[]}
        doc={'competitions':{'a':group('4789','NOM COMPLET A','ABC'),'b':group('4786','NOM COMPLET B','ABC'),'c':group('4784','MATEIX','MATEIX')}}
        got=m.merge_catalog(c,doc)
        self.assertEqual(len(got['teamAliases']),2)
        self.assertEqual({x['leagueId'] for x in got['teamAliases']},{'4789','4786'})
        self.assertEqual(m.merge_catalog(got,{'competitions':{}}),got)

if __name__=='__main__':unittest.main()
