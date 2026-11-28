import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_agenda_baixes import remove,key
from zonaok_fecapa_unificat import invalid_fixture_team
class Withdrawn(unittest.TestCase):
    def test_remove_only_approved_and_preserve_scores(self):
        bad=dict(competition='PREBENJAMI PLATA GIRONA',home='CP CALDES C',away='Pavelló Municipal Caldes de Malavella',iso='2026-11-22',time='10:00',homeScore=None,awayScore=None)
        good=dict(bad,away='CH FIGUERES')
        scored=dict(bad,time='11:00',homeScore=2,awayScore=1)
        d=dict(season='2026/2027',matches=[bad,good,scored])
        m=dict(season=d['season'],sourceRun=1,fixtures=[list(key(bad)),list(key(scored))])
        out,r=remove(d,m)
        self.assertEqual(out['matches'],[good,scored]);self.assertEqual(r['removedNow'],1);self.assertEqual(len(r['review']),1)
        self.assertEqual(remove(out,m,r)[1]['removedTotal'],1)
        self.assertTrue(invalid_fixture_team(dict(bad,away='')))
        self.assertTrue(invalid_fixture_team(dict(bad,away='Municipal d’Esports i Lleure d’Olot')))
        self.assertFalse(invalid_fixture_team(good))
        self.assertFalse(invalid_fixture_team(dict(good,home="CLUB D'ESPORTS VENDRELL",venue='CLUB D ESPORTS VENDRELL')))
        self.assertFalse(invalid_fixture_team(dict(good,home='CH MATARÓ',venue='CH MATARÓ')))
    def test_confirmed_absent_named_fixture(self):
        a=dict(competition='VETERANS GIRONA',home='CLUB PATÍ MALGRAT GRUP ESCOBAR A',away='CH LLORET',iso='2027-01-05',time='22:15',homeScore=None,awayScore=None)
        b=dict(a,iso='2027-02-02')
        d=dict(season='2026/2027',matches=[a,b])
        m=dict(season=d['season'],sourceRun=1,fixtures=[],confirmedAbsentFixtures=[list(key(a))])
        out,r=remove(d,m)
        self.assertEqual(out['matches'],[b])
        self.assertEqual(r['removedNow'],1)
        for protected in (dict(a,homeScore=2,awayScore=1),dict(a,actaState='available')):
            out,r=remove(dict(d,matches=[protected,b]),m)
            self.assertEqual(out['matches'],[protected,b])
            self.assertEqual(len(r['review']),1)
if __name__=='__main__':unittest.main()
