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

if __name__=="__main__":
    unittest.main()
