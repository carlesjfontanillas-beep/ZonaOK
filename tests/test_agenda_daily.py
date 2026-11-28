import sys,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_agenda_daily import merge
from zonaok_push_events import detect
from zonaok_schedule_gate import should_run
class DailyAgenda(unittest.TestCase):
    def row(self,iso='2026-11-27',home='A',away='B',**kw):
        return dict(iso=iso,time='17:00',competition='INFANTIL OR 10',home=home,away=away,homeScore=None,awayScore=None,status='',**kw)
    def run_merge(self,old,new):
        return merge({'schema':'zonaok-partits-total-v1','season':'2026/2027','matches':old},{'kind':'agenda-daily','season':'2026/2027','capturedAt':'2026-11-28T09:00:00Z','rows':new})
    def test_recover_yesterday_preserve_existing(self):
        a=self.row();b=self.row(home='C',away='D')
        b.update(homeScore=1,awayScore=2,lastDirecteAt='2026-11-27T18:00:00Z')
        out,report=self.run_merge([a,b],[dict(a,homeScore=4,awayScore=0),dict(b,homeScore=9,awayScore=9)])
        self.assertEqual(report['recoveredResultCount'],1)
        self.assertEqual(out['matches'][0]['status'],'FINAL')
        self.assertEqual(out['matches'][1]['homeScore'],1)
    def test_schedule_change_without_id_and_push(self):
        a=self.row(iso='2026-12-01')
        out,report=self.run_merge([a],[dict(a,time='19:00')])
        self.assertEqual(len(out['matches']),1)
        self.assertEqual(report['scheduleChangeCount'],1)
        before={'schema':'zonaok-partits-total-v1','season':'2026/2027','matches':[a]}
        events=detect(before,out,since=datetime(2026,11,27,9,tzinfo=timezone.utc),now=datetime(2026,11,28,9,1,tzinfo=timezone.utc),source='agenda')
        self.assertEqual([e['event'] for e in events],['scheduleChange'])
    def test_ambiguous_never_duplicate(self):
        a=self.row(iso='2026-12-01');b=dict(a,iso='2026-12-08')
        out,report=self.run_merge([a,b],[dict(a,time='19:00'),dict(b,time='20:00')])
        self.assertEqual(report['scheduleChangeCount'],0)
        self.assertEqual(len(out['matches']),2)
    def test_daily_madrid_dst(self):
        for month,utc_hour in [(1,9),(7,8)]:
            now=datetime(2026,month,10,utc_hour,12,tzinfo=timezone.utc)
            self.assertTrue(should_run('agenda',f'0 {utc_hour} * * *',now,Path('unused'))[0])
            self.assertFalse(should_run('agenda',f'0 {17-utc_hour} * * *',now,Path('unused'))[0])
if __name__=='__main__':unittest.main()
