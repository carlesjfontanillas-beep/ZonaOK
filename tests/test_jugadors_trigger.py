import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from zonaok_jugadors_trigger import changed_finished_count, fingerprint


class TriggerTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc)
        self.final = {
            "leagueId": "100", "matchId": "200", "iso": "2026-11-25",
            "homeScore": 3, "awayScore": 1, "status": "Finalitzat",
            "actaState": "available",
        }
        self.live = dict(self.final, status="En joc")

    def doc(self, row):
        return {"matches": [row]}

    def test_new_final_match_triggers(self):
        self.assertEqual(
            changed_finished_count(self.doc(self.final), self.doc(self.live), {}, self.now),
            1,
        )

    def test_unchanged_final_does_not_trigger(self):
        self.assertEqual(
            changed_finished_count(self.doc(self.final), self.doc(self.final), {}, self.now),
            0,
        )

    def test_acta_becoming_available_triggers(self):
        earlier = dict(self.final, actaState="pending")
        self.assertEqual(
            changed_finished_count(self.doc(self.final), self.doc(earlier), {}, self.now),
            1,
        )

    def test_verified_fingerprint_does_not_trigger_again(self):
        state = {"matches": {"100|200": {
            "status": "verified", "fingerprint": fingerprint(self.final),
        }}}
        self.assertEqual(
            changed_finished_count(self.doc(self.final), self.doc(self.live), state, self.now),
            0,
        )

    def test_pending_retry_waits_fifteen_minutes(self):
        state = {"matches": {"100|200": {
            "status": "pending", "fingerprint": fingerprint(self.final),
            "checkedAt": "2026-11-25T17:50:00+00:00",
        }}}
        self.assertEqual(
            changed_finished_count(self.doc(self.final), self.doc(self.live), state, self.now),
            0,
        )
        state["matches"]["100|200"]["checkedAt"] = "2026-11-25T17:40:00+00:00"
        self.assertEqual(
            changed_finished_count(self.doc(self.final), self.doc(self.live), state, self.now),
            1,
        )

    def test_live_or_unscored_match_does_not_trigger(self):
        self.assertEqual(changed_finished_count(self.doc(self.live), {}, {}, self.now), 0)
        unscored = dict(self.final, homeScore=None)
        self.assertEqual(changed_finished_count(self.doc(unscored), {}, {}, self.now), 0)


if __name__ == "__main__":
    unittest.main()
