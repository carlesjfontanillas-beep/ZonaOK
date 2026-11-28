import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_agenda_girona_figueres import correct,OLD,TARGET
from zonaok_fecapa_unificat import check_iso
class Girona(unittest.TestCase):
    def test_official_outside_season(self):
        self.assertTrue(check_iso(TARGET[0]))
        self.assertFalse(check_iso('2027-10-09'))
    def test_deduplicate_without_removing_reverse_fixture(self):
        a=dict(competition='3 CATALANA GRUP D',home='GIRONA CLUB HOQUEI B',away='CH FIGUERES',iso=OLD[0],time=OLD[1],homeScore=None,awayScore=None)
        b=dict(a,iso=TARGET[0])
        reverse=dict(a,home=a['away'],away=a['home'],iso='2027-01-30')
        doc=dict(season='2026/2027',matches=[a,b,reverse])
        out,r=correct(doc)
        self.assertEqual(r['removed'],1);self.assertEqual(r['remaining'],1)
        self.assertIn(reverse,out['matches'])
        self.assertEqual(correct(out)[1]['status'],'already_correct')
        out,r=correct(dict(doc,matches=[a]))
        self.assertEqual(r['status'],'rescheduled')
        self.assertEqual(out['matches'][0]['iso'],TARGET[0])
if __name__=='__main__':unittest.main()
