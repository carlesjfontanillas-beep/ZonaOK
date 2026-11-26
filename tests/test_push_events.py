import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_push_events import detect

def catalog(*rows):
    return {"schema":"zonaok-partits-total-v1","season":"2026/2027","matches":list(rows)}

class PushEventsTests(unittest.TestCase):
    def setUp(self):
        self.before=dict(iso="2026-11-25",time="21:00",competition="OK LIGA IBERDROLA",home="CPF",away="BIR",status="SENSE COMENÇAR")
        self.after=dict(self.before,status="FINAL",homeScore=8,awayScore=1,lastDirecteAt="2026-11-25T21:30:00Z")
        self.since=datetime(2026,11,25,20,0,tzinfo=timezone.utc)
        self.now=datetime(2026,11,25,21,35,tzinfo=timezone.utc)
    def events(self,b,a):
        return detect(catalog(*b),catalog(*a),since=self.since,now=self.now)
    def test_finish_and_stable_id(self):
        events=self.events([self.before],[self.after])
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["event"],"finish")
        self.assertEqual(events[0]["fixture"]["homeScore"],8)
        self.assertEqual(events,self.events([self.before],[self.after]))
        self.assertEqual(self.events([self.after],[self.after]),[])
    def test_live_not_provisional(self):
        self.assertEqual(self.events([self.before],[dict(self.after,status="SENSE COMENÇAR")]),[])
        self.assertEqual(self.events([self.before],[dict(self.after,status="EN JOC")])[0]["event"],"start")
        self.assertEqual(self.events([dict(self.before,status="EN JOC")],[dict(self.after,status="EN JOC")]),[])
    def test_schedule_change_matches_stable_fecapa_id_and_is_not_replayed(self):
        old=dict(self.before,leagueId="4774",matchId="146394")
        new=dict(old,iso="2026-11-27",time="20:15",lastDirecteAt="2026-11-25T21:30:00Z")
        events=self.events([old],[new])
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["event"],"scheduleChange")
        self.assertEqual(events[0]["fixture"]["previousTime"],"21:00")
        self.assertEqual(events,self.events([old],[new]))
        self.assertEqual(self.events([old],[new,dict(new)]),[])
        self.assertEqual(self.events([old],[dict(new,home="Other team")]),[])
        self.since=datetime(2026,11,25,21,31,tzinfo=timezone.utc)
        self.assertEqual(self.events([old],[new]),[])
    def test_no_historical_ambiguous_or_missing_baseline(self):
        self.assertEqual(self.events([], [self.after]),[])
        self.assertEqual(self.events([self.before,self.before],[self.after]),[])
        self.assertEqual(self.events([self.before],[self.after,self.after]),[])
        self.assertEqual(self.events([self.before],[dict(self.after,homeScore=None)]),[])
        self.now=datetime(2026,11,26,9,0,tzinfo=timezone.utc)
        self.assertEqual(self.events([self.before],[self.after]),[])
if __name__=="__main__":
    unittest.main()

