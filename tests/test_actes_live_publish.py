import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from zonaok_actes_live_publish import merge, merge_catalog, Conflict

def row(**kw):
    return {"iso":"2026-11-28","time":"10:00","competition":"INFANTIL OR",
            "home":"A","away":"B","homeScore":2,"awayScore":1,
            "status":"FINAL", **kw}

class LivePublishTest(unittest.TestCase):
    def test_unrelated_player_and_timestamp_updates(self):
        b={"players":{"1":{"lastSeenAt":"2026-11-28T11:00:00Z","nameVariants":["A"]}}}
        a={"players":{"1":{"lastSeenAt":"2026-11-28T12:00:00Z","nameVariants":["A","B"]},"2":{"name":"X"}}}
        c={"players":{"1":{"lastSeenAt":"2026-11-28T13:00:00Z","nameVariants":["A","C"]},"3":{"name":"Y"}}}
        d=merge(b,a,c,master=True)
        self.assertEqual(set(d["players"]),{"1","2","3"})
        self.assertEqual(d["players"]["1"]["nameVariants"],["A","B","C"])
        self.assertEqual(d["players"]["1"]["lastSeenAt"],"2026-11-28T13:00:00Z")
    def test_preserve_live_updates_and_new_fixtures(self):
        b=row()
        a={**b,"leagueId":"4781","matchId":"123456","actaState":"available"}
        c={**b,"directeUpdatedAt":"now"}
        new=row(home="C")
        d,n=merge_catalog({"matches":[b]},{"matches":[a]},{"matches":[new,c],"sources":{"directe":1}})
        self.assertEqual(n,1)
        self.assertEqual(d["matches"],[new,{**c,"leagueId":"4781","matchId":"123456","actaState":"available"}])
        self.assertEqual(d["sources"],{"directe":1})
    def test_reject_score_conflict(self):
        b=row()
        a={**b,"actaState":"available"}
        with self.assertRaises(Conflict):
            merge_catalog({"matches":[b]},{"matches":[a]},{"matches":[row(homeScore=3)]})
    def test_reject_ambiguous_fixture(self):
        b=row()
        with self.assertRaises(Conflict):
            merge_catalog({"matches":[b]},{"matches":[{**b,"actaState":"available"}]},{"matches":[b,b]})
    def test_reject_conflicting_statistics(self):
        with self.assertRaises(Conflict):
            merge({"goals":1},{"goals":2},{"goals":3},master=True)
    def test_reject_duplicate_id(self):
        b=row()
        a={**b,"leagueId":"4781","matchId":"123456"}
        with self.assertRaises(Conflict):
            merge_catalog({"matches":[b]},{"matches":[a]},{"matches":[b,row(home="C",leagueId="4781",matchId="123456")]})
