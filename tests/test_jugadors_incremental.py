import json,sys,tempfile,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_jugadors_incremental import candidates,select,merge_verified
class TestMaintenance(unittest.TestCase):
    def test_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=dict(leagueId="1",iso="2026-11-24",homeScore=2,awayScore=1,actaState="available")
            rows=[dict(base,matchId="2",status="Finalitzat"),dict(base,matchId="3",status="En joc"),dict(base,matchId="4",iso="2026-11-26"),dict(base,matchId="5",homeScore=None),dict(base,matchId="6",iso="2026-09-01")]
            (root/"zonaok-tots-partits.json").write_text(json.dumps(dict(schema="zonaok-partits-total-v1",matches=rows)))
            found=candidates(root,"2026-11-25")
            self.assertEqual(set(found),{"1|2","1|6"})
            self.assertEqual(len(select(found,{},"incremental",date(2026,11,25))),1)
            self.assertEqual(len(select(found,{},"weekly",date(2026,11,25))),2)
            state={"1|2":{"status":"verified","fingerprint":found["1|2"]["fingerprint"]}}
            self.assertEqual(len(select(found,state,"incremental",date(2026,11,25))),0)
            state["1|2"]["fingerprint"]="old"
            self.assertEqual(len(select(found,state,"incremental",date(2026,11,25))),1)
    def test_merge_keeps_optional_and_updates_explicit(self):
        master={"players":{},"matchAppearances":{"k":{"stats":{"goals":1,"assists":2},"shirtNumber":4}}}
        candidate={"players":{},"matchAppearances":{"k":{"stats":{"goals":3},"shirtNumber":5}}}
        merge_verified(master,candidate)
        self.assertEqual(master["matchAppearances"]["k"]["stats"],{"goals":3,"assists":2})
        self.assertEqual(master["matchAppearances"]["k"]["shirtNumber"],5)
