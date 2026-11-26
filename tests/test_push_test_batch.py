import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from zonaok_push_test_batch import build_batches


class PushTestBatchTests(unittest.TestCase):
    def test_builds_fictional_barca_nc_events_and_incidents(self):
        now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
        events, incidents = build_batches("12345", now=now)
        self.assertEqual([e["event"] for e in events["events"]], ["start", "finish", "scheduleChange"])
        self.assertTrue(all(e["test"] and e["fixture"]["home"] == "BARÇA" for e in events["events"]))
        self.assertEqual(events["events"][0]["fixture"]["competition"], "NACIONAL CATALANA MASCULINA")
        self.assertEqual([e["event"] for e in incidents["matches"][0]["incidents"]], ["goal", "card", "directFoul"])
        self.assertTrue(incidents["matches"][0]["test"])
        self.assertEqual(len({e["eventId"] for e in events["events"]}), 3)


if __name__ == "__main__":
    unittest.main()
