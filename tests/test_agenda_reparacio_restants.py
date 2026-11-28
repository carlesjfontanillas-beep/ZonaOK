import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_agenda_reparacio_restants import correct
class Remaining(unittest.TestCase):
    def test_latest_and_reverse(self):
        a=dict(competition='FEM 11 PLATA',home='A',away='B',iso='2026-10-31',time='12:30',homeScore=None,awayScore=None)
        b=dict(a,iso='2026-11-28',time='13:00')
        c=dict(a,iso='2026-12-05',time='17:30')
        spec=dict(c,oldIso=b['iso'],oldTime=b['time'],approvedSlots=[[a['iso'],a['time']]])
        x=dict(a,competition='VETERANS TARRAGONA',home='C',away='D',iso='2026-11-27',time='21:15',venue='Pista')
        y=dict(x,home='D',away='C')
        m=dict(season='2026/2027',sourceRun=1,capturedAt='2026-11-28T08:40:05Z',fixtures=[spec],reversed=[dict(x,homeScore=3,awayScore=0)])
        doc=dict(season='2026/2027',matches=[a,b,c,x,y])
        out,report=correct(doc,m)
        self.assertEqual(report['removed'],3);self.assertEqual(report['resolved'],2)
        self.assertEqual(len(out['matches']),2)
        self.assertEqual(out['matches'][0]['homeScore'],3)
        self.assertEqual(out['matches'][1]['iso'],'2026-12-05')
        self.assertEqual(correct(out,m)[1]['removed'],0)
if __name__=='__main__':unittest.main()
