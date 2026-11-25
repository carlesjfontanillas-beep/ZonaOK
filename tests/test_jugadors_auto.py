import sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_jugadors_auto import empty,merge,save,load,url
class TestPlayers(unittest.TestCase):
    def row(self,league,team,pid="123",name="Persona fictícia"):
        return dict(id=pid,name=name,league=league,team=team,season="41")
    def test_multi_team(self):
        d=empty("41")
        merge(d,"1","2",[self.row("1","2")],"Club fictici A", "t1")
        merge(d,"3","4",[self.row("3","4")],"Club fictici B", "t2")
        self.assertEqual(len(d["players"]),1)
        self.assertEqual(len(d["memberships"]),2)
    def test_duplicate_and_missing(self):
        d=empty("41");r=self.row("1","2")
        self.assertEqual(merge(d,"1","2",[r,r],None,"t1"),1)
        merge(d,"1","2",[],None,"t2")
        self.assertEqual(len(d["memberships"]),1)
    def test_wrong_context(self):
        d=empty("41");self.assertEqual(merge(d,"1","2",[self.row("3","2")],None,"t1"),0)
    def test_same_name_distinct_ids(self):
        d=empty("41");merge(d,"1","2",[self.row("1","2"),self.row("1","2","124")],None,"t")
        self.assertEqual(len(d["players"]),2)
    def test_roundtrip(self):
        d=empty("41")
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"master.json";save(p,d)
            self.assertEqual(load(p,"41"),d)
            with self.assertRaises(ValueError):load(p,"42")
    def test_profile(self):
        self.assertIn("jugador=123",url("1","41","2","123"))
if __name__=="__main__":unittest.main()
