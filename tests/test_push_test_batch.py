import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from zonaok_push_events import detect
from zonaok_push_live_incidents import parse_incidents
from zonaok_push_test_batch import build_fixture_data


class PushTestBatchTests(unittest.TestCase):
    def test_entire_detector_and_incident_parser_path(self):
        now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
        before, live, final, acta = build_fixture_data("12345", now=now)
        since_before = datetime.fromisoformat(before["matches"][0]["lastDirecteAt"].replace("Z", "+00:00"))
        since_live = datetime.fromisoformat(live["matches"][0]["lastDirecteAt"].replace("Z", "+00:00"))
        start_events = detect(before, live, since=since_before, now=now)
        finish_events = detect(live, final, since=since_live, now=now.replace(second=2))
        self.assertEqual({event["event"] for event in start_events}, {"start", "scheduleChange"})
        self.assertEqual([event["event"] for event in finish_events], ["finish"])
        events = start_events + finish_events
        self.assertTrue(all(event["fixture"]["home"] == "BARÇA" for event in events))
        self.assertTrue(all(event["fixture"]["competition"] == "NACIONAL CATALANA MASCULINA" for event in events))
        self.assertEqual(len({event["eventId"] for event in events}), 3)

        incidents = parse_incidents(acta["text"], acta["fixture"], observed_at=acta["observedAt"])
        self.assertEqual([event["event"] for event in incidents], ["goal", "card", "directFoul"])
        self.assertTrue(all(len(event["eventId"]) == 64 for event in incidents))


if __name__ == "__main__":
    unittest.main()
