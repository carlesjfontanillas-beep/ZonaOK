import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_agenda_reparacio_confirmats import repair
class Confirmed(unittest.TestCase):
    def test_merge_and_id_conflict(self):
        a=dict(competition='INFANTIL OR 10',home='A',away='B',iso='2026-11-28',time='13:00',leagueId='4786',matchId='12345',homeScore=None,awayScore=None)
        b=dict(a,iso='2026-11-27',time='21:00',matchId='',homeScore=4,awayScore=2,status='FINAL')
        s=dict(b,oldIso=a['iso'],oldTime=a['time'])
        m=dict(season='2026/2027',sourceRun=1,capturedAt='2026-11-28T08:40:05Z',fixtures=[s])
        d=dict(season='2026/2027',matches=[a,b])
        out,r=repair(d,m)
        self.assertEqual(r['removed'],1);self.assertEqual(out['matches'][0]['matchId'],'12345');self.assertEqual(out['matches'][0]['homeScore'],4)
        self.assertEqual(repair(out,m)[1]['alreadyCorrect'],1)
        out,r=repair(dict(d,matches=[a,dict(b,matchId='67890')]),m)
        self.assertEqual(r['review'],1);self.assertEqual(len(out['matches']),2)
if __name__=='__main__':unittest.main()
