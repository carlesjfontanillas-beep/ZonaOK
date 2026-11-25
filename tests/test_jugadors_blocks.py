import sys,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_jugadors_blocks import plan_matches,plan_rosters,plan_stats,STATS_REVISION,LIMITS

class TestBlocks(unittest.TestCase):
    def setUp(self):
        self.clock=datetime(2026,11,25,12,tzinfo=timezone.utc)
        self.rows={f"1|{i}":{"iso":"2026-09-01","fingerprint":"v1"} for i in range(1,151)}
    def test_historical_limit_and_resume(self):
        p=plan_matches(self.rows,{},set(),"acts",self.clock)
        self.assertEqual(len(p),100)
        state={k:{"status":"verified","fingerprint":"v1"} for k,_ in p}
        self.assertEqual(len(plan_matches(self.rows,state,set(),"acts",self.clock)),50)
    def test_existing_data_last_not_assumed_complete(self):
        p=plan_matches(self.rows,{},{"1|1"},"acts",self.clock)
        self.assertNotIn("1|1",[k for k,_ in p])
    def test_retries_separate_and_bounded(self):
        state={k:{"status":"pending","fingerprint":"v1","checkedAt":"2026-11-24T12:00:00+00:00"} for k in self.rows}
        self.assertEqual(plan_matches(self.rows,state,set(),"acts",self.clock),[])
        self.assertEqual(len(plan_matches(self.rows,state,set(),"retry",self.clock)),20)
        for v in state.values():v["checkedAt"]=self.clock.isoformat()
        self.assertEqual(plan_matches(self.rows,state,set(),"retry",self.clock),[])
    def test_changed_fingerprint_is_new_work(self):
        r={"1|1":self.rows["1|1"]}
        state={"1|1":{"status":"verified","fingerprint":"v0"}}
        self.assertEqual(len(plan_matches(r,state,set(),"acts",self.clock)),1)
    def test_rosters_resume_and_refresh(self):
        leagues=[str(i) for i in range(1,13)]
        p=plan_rosters(leagues,{},set(),self.clock)
        self.assertEqual(len(p),10)
        state={k:{"status":"verified","checkedAt":self.clock.isoformat()} for k in p}
        self.assertEqual(len(plan_rosters(leagues,state,set(),self.clock)),2)
    def test_stats_backfill_includes_old_verified_and_resumes(self):
        rows={"4786|152375":{"iso":"2026-10-18","fingerprint":"v1"},**self.rows}
        captured=set(rows)
        state={k:{"status":"verified","fingerprint":"v1"} for k in rows}
        first=plan_stats(rows,state,captured,self.clock)
        self.assertEqual(len(first),100)
        self.assertEqual(first[0][0],"4786|152375")
        for k,_ in first:state[k]["statsRevision"]=STATS_REVISION
        self.assertEqual(len(plan_stats(rows,state,captured,self.clock)),51)
    def test_stats_backfill_respects_retry_delay(self):
        key="1|1"
        state={key:{"status":"pending","fingerprint":"v1","statsAttemptRevision":STATS_REVISION,"checkedAt":self.clock.isoformat()}}
        self.assertEqual(plan_stats(self.rows,state,{key},self.clock),[])
    def test_flash_only_recent(self):
        rows={"1|1":{"iso":"2026-11-25","fingerprint":"v1"},**self.rows}
        rows["1|1"]={"iso":"2026-11-25","fingerprint":"v1"}
        self.assertEqual([k for k,_ in plan_matches(rows,{},set(),"flash",self.clock)],["1|1"])

if __name__=="__main__":unittest.main()
