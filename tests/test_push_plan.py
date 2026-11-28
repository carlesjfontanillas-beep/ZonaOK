import sys,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_push_plan import build_plan
from zonaok_push_events import scheduled_starts
def row(iso,time,**kw):
    return dict(iso=iso,time=time,competition='ALEVI OR 3',home='BARCA',away='VIC',**kw)
def cat(*rows):
    return {'schema':'zonaok-partits-total-v1','season':'2026/2027','matches':list(rows)}
class PlanTest(unittest.TestCase):
    def test_window_and_live(self):
        c=cat(row('2026-11-28','09:59'),row('2026-11-28','10:00'),row('2026-11-29','09:59'),row('2026-11-29','10:00'),row('2026-11-28','17:00',status='AJORNAT'),dict(row('2026-11-28','18:00'),competition='NACIONAL CATALANA MASCULINA'))
        p=build_plan(c,datetime(2026,11,28,9,10,tzinfo=timezone.utc))
        self.assertEqual(p['eventCount'],3)
        self.assertEqual(p['scheduledCount'],2)
        self.assertEqual(p['liveConfirmationCount'],1)
        self.assertEqual(p['from'],'2026-11-28T10:00:00+01:00')
        self.assertEqual(p['until'],'2026-11-29T10:00:00+01:00')
        due=scheduled_starts(c,now=datetime(2026,11,28,9,5,tzinfo=timezone.utc),plan=p)
        self.assertEqual(len(due),2)
        self.assertEqual({e['fixture']['time'] for e in due},{'09:59','10:00'})
        self.assertEqual(due[0]['eventId'],p['events'][0]['eventId'])
        self.assertEqual(scheduled_starts(cat(row('2026-11-28','10:00',status='AJORNAT')),now=datetime(2026,11,28,9,5,tzinfo=timezone.utc),plan=p),[])
    def test_dst(self):
        p=build_plan(cat(),datetime(2027,3,27,9,1,tzinfo=timezone.utc))
        self.assertEqual(p['until'],'2027-03-28T10:00:00+02:00')
if __name__=='__main__':unittest.main()
