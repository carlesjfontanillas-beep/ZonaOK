import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_jugadors_auto import empty, merge, merge_profile, verify_master
class ProfilesTest(unittest.TestCase):
    def test_merge_details_without_full_birth_date(self):
        d=empty("41")
        r={"id":"999999","name":"Jugador Exemple","league":"4789","team":"11173","season":"41"}
        merge(d,"4789","11173",[r],"EQUIP EXEMPLE","2026-11-24T00:00:00Z")
        result={"ready":True,"fields":{"birthYear":2000,"birthDate":"2000-01-01","position":"goalkeeper","number":1,"goals":0},"matches":[{"matchId":"123","leagueId":"4789","source":"FECAPA:fitxa_partits_jugats"}]}
        merge_profile(d,"4789","11173","999999",result)
        merge_profile(d,"4789","11173","999999",result)
        p=d["players"]["999999"];m=d["memberships"]["41|4789|11173|999999"]
        self.assertEqual(p["birthYear"],2000)
        self.assertNotIn("birthDate",p)
        self.assertEqual(m["position"],"goalkeeper")
        self.assertEqual(m["profileStats"]["number"],1)
        self.assertEqual(len(m["matches"]),1)
        self.assertTrue(verify_master(d))
