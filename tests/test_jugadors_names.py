import sys, tempfile, unittest, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_jugadors_auto import enrich_names, empty

class NameTest(unittest.TestCase):
    def test_exact_names_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"favorits.js").write_text('const CLUB_NAMES_BY_CREST = {"234":"BARÇA","232_1":"CE ARENYS DE MUNT"};',encoding="utf-8")
            (root/"zonaok-classificacions.json").write_text(json.dumps({"competitions":{"a":{"leagueId":"4789","competition":"ALEVÍ","name":"ALEVÍ OR 3","standings":[{"team":"BARÇA"}]},"b":{"leagueId":"4789","competition":"ALEVÍ","name":"ALEVÍ OR 4","standings":[{"team":"EQUIP X"}]},"c":{"leagueId":"4789","competition":"ALEVÍ","name":"ALEVÍ OR 5","standings":[{"team":"EQUIP X"}]}}}),encoding="utf-8")
            d=empty("41")
            d["memberships"]={"a":{"leagueId":"4789","seasonId":"41","teamName":"BARÇA","clubId":"234"},"b":{"leagueId":"4789","seasonId":"41","teamName":"EQUIP X","clubCrestId":"232_1"}}
            result=enrich_names(d,root)
            self.assertEqual(d["memberships"]["a"]["groupName"],"ALEVÍ OR 3")
            self.assertEqual(d["memberships"]["a"]["leagueName"],"ALEVÍ")
            self.assertEqual(d["memberships"]["a"]["clubName"],"BARÇA")
            self.assertEqual(d["memberships"]["b"]["clubName"],"CE ARENYS DE MUNT")
            self.assertIsNone(d["memberships"]["b"]["groupName"])
            self.assertEqual(result["resolved"]["ambiguousGroup"],1)
