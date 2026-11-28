import sys,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_watchdog import decide,retry_args,PUSH
NOW=datetime(2026,11,28,12,tzinfo=timezone.utc)
def run(i=1,status='completed',conclusion='failure',age=1000,title=''):
    return {'databaseId':i,'status':status,'conclusion':conclusion,'updatedAt':(NOW-timedelta(seconds=age)).isoformat(),'displayTitle':title}
class WatchdogTest(unittest.TestCase):
    def test_error_no_cap(self):
        for workflow in ('zonaok-auto-directe.yml','zonaok-actes-live.yml','zonaok-auto-agenda.yml','jugadors-public.yml',PUSH):
            args,_=decide(workflow,[run(i) for i in range(10)],NOW)
            self.assertIsNotNone(args)
    def test_no_duplicate_or_tight_loop(self):
        self.assertIsNone(decide('zonaok-auto-directe.yml',[run(status='in_progress')],NOW,True)[0])
        self.assertIsNone(decide('zonaok-actes-live.yml',[run(age=60)],NOW)[0])
        self.assertIsNone(decide('jugadors-public.yml',[run(conclusion='success')],NOW)[0])
        self.assertIsNotNone(decide('zonaok-auto-directe.yml',[run(conclusion='success')],NOW,True)[0])
    def test_push_production_and_no_test(self):
        title='ZonaOK Push production directe '+'a'*40+' '+'b'*40
        self.assertEqual(retry_args(PUSH,run(title=title)),['test_scenario=production','event_source=directe','before_sha='+'a'*40,'after_sha='+'b'*40])
        self.assertIsNone(decide(PUSH,[run(title='ZonaOK Push barca_nc directe')],NOW)[0])
        self.assertEqual(retry_args(PUSH,run()),['test_scenario=scheduled_now'])
if __name__=='__main__':unittest.main()
