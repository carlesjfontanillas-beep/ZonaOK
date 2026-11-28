import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from zonaok_push_live_incidents import candidates, parse_incidents

FIXTURE = {"iso":"2026-11-21","time":"19:45","competition":"NACIONAL CATALANA MASCULINA","home":"HOQUEI CLUB CASTELLAR","away":"UEH BARBERÀ","leagueId":"4774","matchId":"146394"}

class LiveIncidentTests(unittest.TestCase):
    def test_parses_goals_cards_and_direct_free_hits_only(self):
        text = """INCIDÈNCIES
PERÍODE 2
P2 01:58
Image
FALTA DIRECTA PER A UEH BARBERÀ
Al llançament...
#10 SERRA ASENSIO, MARC
P1 10:56
2 - 0
Image
GOL HOQUEI CLUB CASTELLAR
#9 CURTIELLAS PEREA, PAU
P1 20:34
Image
TARGETA GROGA UEH BARBERÀ
#22 LOPEZ GARCIA, IGNASI
P1 23:00
Image
FALTA UEH BARBERÀ
"""
        got = parse_incidents(text, FIXTURE, observed_at="2026-11-21T20:00:00Z")
        self.assertEqual([x["event"] for x in got], ["directFoul", "goal", "card"])
        self.assertEqual(got[0]["team"], "UEH BARBERÀ")
        self.assertEqual(got[1]["score"], "2-0")
        self.assertEqual(got[2]["matchClock"], "20:34")
        self.assertTrue(all(len(x["eventId"]) == 64 for x in got))
        self.assertEqual(got, parse_incidents(text, FIXTURE, observed_at="2026-11-21T20:00:00Z"))

    def test_only_live_senior_nacional_matches_are_candidates(self):
        now = datetime(2026, 11, 21, 19, 55, tzinfo=timezone.utc)
        missing_id = dict(FIXTURE, iso="2026-11-21", home="CLUB PATÍ SENSE ID", away="VISITANT", leagueId="", matchId="", status="EN JOC")
        rows = [dict(FIXTURE, status="EN JOC"), dict(FIXTURE, matchId="2", competition="OK LIGA IBERDROLA", status="EN JOC"), dict(FIXTURE, matchId="146395", away="CP SANT CELONI", status="FINAL"), missing_id]
        doc = {"schema":"zonaok-partits-total-v1", "season":"2026/2027", "matches":rows}
        selected = candidates(doc, now=now)
        self.assertEqual([m["fixture"]["matchId"] for m in selected], ["146394", ""])
        self.assertTrue(selected[1]["fixture"]["internalId"].startswith("zonaok:"))
        with self.assertRaises(ValueError): candidates({"matches":[]}, now=now)
        duplicate = dict(missing_id)
        self.assertEqual(candidates({"schema":"zonaok-partits-total-v1", "season":"2026/2027", "matches":[missing_id, duplicate]}, now=now), [])

if __name__ == "__main__": unittest.main()
