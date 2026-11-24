import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_jugadors_auto import empty,merge,verify_master,persistence_probe,BASE
class TestActaContract(unittest.TestCase):
    def candidate(self):
        d=empty("41")
        merge(d,"1","2",[dict(id="123",name="Persona fictícia",league="1",team="2",season="41")],"Equip fictici","t")
        a=dict(seasonId="41",leagueId="1",matchId="3",side="home",playerId="123",teamFilterId="2",shirtNumber=5,position="goalkeeper",captain=True,participation="listed",stats={"goals":0},actaUrl=BASE+"?liga=1&vista=calendar&partido=3",source="FECAPA:acta_resum",checkedAt="t")
        d["matchAppearances"]["41|1|3|home|123"]=a
        return d
    def test_contract_and_roundtrip(self):
        d=self.candidate()
        self.assertTrue(verify_master(d))
        self.assertTrue(persistence_probe(d)["reimportNoDuplicates"])
    def test_invalid_key(self):
        d=self.candidate();d["matchAppearances"]["41|1|4|home|123"]=d["matchAppearances"].pop("41|1|3|home|123")
        with self.assertRaises(ValueError):verify_master(d)
    def test_invalid_membership(self):
        d=self.candidate();d["matchAppearances"]["41|1|3|home|123"]["teamFilterId"]="99"
        with self.assertRaises(ValueError):verify_master(d)
    def test_optional_unknown_fields(self):
        d=self.candidate();a=d["matchAppearances"]["41|1|3|home|123"]
        for k in ("captain","position","shirtNumber","stats","teamFilterId"):a.pop(k)
        self.assertTrue(verify_master(d))
