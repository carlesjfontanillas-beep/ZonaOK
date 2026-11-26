import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from zonaok_push_feed import build_feed


class PushFeedTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
        self.event = {"eventId": "a" * 64, "event": "finish", "source": "FECAPA",
                      "observedAt": "2026-11-26T11:55:00Z", "fixture": {}}

    def test_only_new_start_and_finish_events_are_kept(self):
        data = {"dryRun": True, "events": [self.event,
                {**self.event, "eventId": "b" * 64, "event": "goal"}]}
        feed = build_feed(data, None, now=self.now)
        self.assertEqual([item["event"] for item in feed["events"]], ["finish"])
        self.assertEqual(feed["events"][0]["createdAt"], "2026-11-26T12:00:00Z")

    def test_preserves_recent_events_and_deduplicates_ids(self):
        old = {"schema": "zonaok-push-events-v1", "season": "2026/2027",
               "events": [{**self.event, "createdAt": "2026-11-26T11:50:00Z"}]}
        feed = build_feed({"dryRun": True, "events": [self.event]}, old, now=self.now)
        self.assertEqual(len(feed["events"]), 1)
        self.assertEqual(feed["events"][0]["createdAt"], "2026-11-26T12:00:00Z")

    def test_drops_expired_events(self):
        old = {"schema": "zonaok-push-events-v1", "season": "2026/2027",
               "events": [{**self.event, "createdAt": (self.now-timedelta(minutes=166)).isoformat()}]}
        feed = build_feed({"dryRun": True, "events": []}, old, now=self.now)
        self.assertEqual(feed["events"], [])

    def test_rejects_malformed_detector_output(self):
        with self.assertRaises(ValueError):
            build_feed({"events": []}, None, now=self.now)


if __name__ == "__main__":
    unittest.main()
