import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_deduplicar_partits import deduplicate

class DedupTest(unittest.TestCase):
    def setUp(self):
        self.row={"iso":"2026-11-21","time":"12:00","competition":"ALEVI OR 3",
                  "home":"BARÇA","away":"SANT CELONI"}
        self.identified=dict(self.row,leagueId="4789",matchId="12345")
    def test_exact_duplicate(self):
        rows,rep=deduplicate([self.row,self.row])
        self.assertEqual((len(rows),rep["removed"]),(1,1))
    def test_complementary(self):
        rows,rep=deduplicate([dict(self.row,venue="Pista"),
             dict(self.identified,homeScore=3,awayScore=1,actaState="available")])
        self.assertEqual(rep["removed"],1)
        self.assertEqual((rows[0]["venue"],rows[0]["homeScore"],rows[0]["actaState"]),("Pista",3,"available"))
    def test_different_ids(self):
        rows,rep=deduplicate([self.identified,dict(self.identified,matchId="54321")])
        self.assertEqual((len(rows),rep["removed"],rep["reviewGroups"]),(2,0,1))
    def test_score_conflict(self):
        rows,rep=deduplicate([dict(self.identified,homeScore=1,awayScore=2),
                              dict(self.identified,homeScore=3,awayScore=2)])
        self.assertEqual(len(rows),2)
        self.assertTrue(rep["review"])
    def test_different_categories(self):
        rows,rep=deduplicate([self.row,dict(self.row,competition="INFANTIL OR 3")])
        self.assertEqual(len(rows),2)
    def test_verified_preserved(self):
        rows,rep=deduplicate([dict(self.identified,actaState="available"),
                              dict(self.identified,actaState="pending")])
        self.assertEqual(rows[0]["actaState"],"available")
    def test_unknown_conflict(self):
        rows,rep=deduplicate([dict(self.row,extra=1),dict(self.row,extra=2)])
        self.assertEqual(len(rows),2)
    def test_repeat_is_idempotent(self):
        rows,rep=deduplicate([self.row,self.identified,self.row])
        again,rep2=deduplicate(rows)
        self.assertEqual(rep2["removed"],0)
        self.assertEqual(rows,again)

    def test_changed_time_calafell_canet(self):
        a=dict(self.row,iso="2026-11-23",competition="LCV GRUP B",home="CLUB PATI CALAFELL",away="CLUB HOQUEI CANET",time="21:30")
        b=dict(a,time="22:00",homeScore=8,awayScore=3,status="FINAL")
        rows,rep=deduplicate([a,b])
        self.assertEqual((rep["removed"],rows[0]["time"],rows[0]["homeScore"],rows[0]["awayScore"]),(1,"22:00",8,3))
    def test_changed_time_mollet_preserves_id(self):
        a=dict(self.identified,time="21:30")
        b=dict(self.row,time="21:00",homeScore=2,awayScore=11,status="FINAL")
        rows,rep=deduplicate([a,b])
        self.assertEqual((rep["removed"],rows[0]["time"],rows[0]["matchId"],rows[0]["awayScore"]),(1,"21:00","12345",11))
    def test_same_id_changed_time(self):
        a=dict(self.identified,time="21:30")
        b=dict(a,time="22:00",homeScore=8,awayScore=3,status="FINAL")
        rows,rep=deduplicate([a,b])
        self.assertEqual((rep["removed"],rows[0]["time"]),(1,"22:00"))
    def test_different_official_ids_changed_time(self):
        a=dict(self.identified,time="21:30")
        b=dict(a,time="22:00",matchId="54321",homeScore=8,awayScore=3,status="FINAL")
        rows,rep=deduplicate([a,b])
        self.assertEqual((len(rows),rep["removed"]),(2,0))
        self.assertTrue(rep["review"])
    def test_two_scores_not_merged(self):
        a=dict(self.row,time="21:30",homeScore=1,awayScore=2,status="FINAL")
        rows,rep=deduplicate([a,dict(a,time="22:00",homeScore=3)])
        self.assertEqual(len(rows),2)
    def test_same_team_different_opponent_flagged(self):
        a=dict(self.row,time="21:30",homeScore=1,awayScore=2,status="FINAL")
        b=dict(self.row,time="21:30",away="MOLLET")
        rows,rep=deduplicate([a,b])
        self.assertEqual(len(rows),2)
        self.assertEqual(rep["review"][0]["kind"],"same_team_same_time")
    def test_far_apart_not_merged(self):
        a=dict(self.row,time="09:00")
        b=dict(a,time="18:00",homeScore=8,awayScore=3,status="FINAL")
        self.assertEqual(len(deduplicate([a,b])[0]),2)
    def test_not_merge_live(self):
        a=dict(self.row,time="21:30")
        b=dict(a,time="22:00",homeScore=8,awayScore=3,status="EN JOC")
        self.assertEqual(len(deduplicate([a,b])[0]),2)
    def test_not_merge_different_rounds(self):
        a=dict(self.row,time="21:30",round="1")
        b=dict(a,time="22:00",round="2",homeScore=8,awayScore=3,status="FINAL")
        self.assertEqual(len(deduplicate([a,b])[0]),2)

class WorkflowIntegrationTest(unittest.TestCase):
    def test_all_canonical_imports_check_duplicates_before_publishing(self):
        root=Path(__file__).resolve().parents[1]
        for mode in ("agenda","directe","actes"):
            with self.subTest(mode=mode):
                text=(root/".github"/"workflows"/f"zonaok-auto-{mode}.yml").read_text(encoding="utf-8")
                check=f"python scripts/zonaok_deduplicar_partits.py {'' if mode=='actes' else '--apply '}--report diagnostic-duplicats-{mode}.json"
                self.assertIn(check,text)
                self.assertLess(text.index("python scripts/zonaok_fecapa_unificat.py validate"),text.index(check))
                self.assertLess(text.index(check),text.index("git add -- zonaok-tots-partits.json" if mode=="actes" else "git add zonaok-tots-partits.json"))
                if mode=="actes":
                    self.assertNotIn("zonaok_deduplicar_partits.py --apply",text)
                    self.assertEqual(text.count(check),2)

if __name__=="__main__":
    unittest.main()
