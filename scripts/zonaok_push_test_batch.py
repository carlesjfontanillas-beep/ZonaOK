#!/usr/bin/env python3
"""Build clearly marked fictional Barça NC notification batches for manual tests."""
import argparse
import hashlib
import json
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SEASON = "2026/2027"
MADRID = ZoneInfo("Europe/Madrid")
COMPETITION = "NACIONAL CATALANA MASCULINA"


def norm(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", str(value or ""))
                      if unicodedata.category(c) != "Mn").upper().split())


def event_id(fixture, event):
    if event == "scheduleChange":
        values = [SEASON, str(fixture["leagueId"]), str(fixture["matchId"]), event,
                  fixture["previousIso"], fixture["previousTime"], fixture["iso"], fixture["time"]]
        raw = "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in values) + "]"
    else:
        identity = [norm(fixture[k]) for k in ("iso", "time", "competition", "home", "away")]
        raw = ("[" + json.dumps(SEASON, ensure_ascii=False) + ", [" +
               ", ".join(json.dumps(v, ensure_ascii=False) for v in identity) + "], " +
               json.dumps(event, ensure_ascii=False) + "]")
    return hashlib.sha256(raw.encode()).hexdigest()


def incident_id(fixture, item):
    values = [SEASON, fixture["leagueId"], fixture["matchId"], item["event"],
              item["period"], item["matchClock"], item["team"], item["player"],
              item["score"], str(item["ordinal"])]
    raw = "|".join(norm(v).replace("|", "/") for v in values)
    return hashlib.sha256(raw.encode()).hexdigest()


def build_batches(run_id, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    observed = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    local_now = now.astimezone(MADRID)
    kickoff = (local_now - timedelta(minutes=2)).replace(second=0, microsecond=0)
    suffix = str(run_id)
    match_id = "TEST-NC-M-" + suffix
    fixture = {
        "iso": kickoff.date().isoformat(), "time": kickoff.strftime("%H:%M"),
        "competition": COMPETITION, "home": "BARÇA",
        "away": "EQUIP FICTICI PROVA " + suffix, "leagueId": "4774",
        "matchId": match_id, "homeScore": 1, "awayScore": 0,
    }
    events = []
    for kind in ("start", "finish"):
        events.append({"eventId": event_id(fixture, kind), "event": kind,
                       "source": "FECAPA", "observedAt": observed,
                       "fixture": fixture, "test": True})

    scheduled = {**fixture, "iso": (local_now + timedelta(days=3)).date().isoformat(),
                 "time": "19:00", "matchId": "TEST-NC-M-SCHEDULE-" + suffix,
                 "previousIso": (local_now + timedelta(days=3)).date().isoformat(),
                 "previousTime": "18:00"}
    events.append({"eventId": event_id(scheduled, "scheduleChange"),
                   "event": "scheduleChange", "source": "FECAPA",
                   "observedAt": observed, "fixture": scheduled, "test": True})

    incidents = []
    for kind, clock, score in (("goal", "01:00", "1-0"), ("card", "02:00", ""),
                               ("directFoul", "03:00", "")):
        item = {"event": kind, "period": "P1", "matchClock": clock,
                "team": "BARÇA", "player": "JUGADOR DE PROVA",
                "score": score, "ordinal": 1}
        item["eventId"] = incident_id(fixture, item)
        item["observedAt"] = observed
        incidents.append(item)
    event_batch = {"schema": "zonaok-push-event-batch-v1", "season": SEASON,
                   "events": events}
    incident_batch = {"schema": "zonaok-push-live-incidents-v1", "season": SEASON,
                      "matches": [{"fixture": fixture, "observedAt": observed,
                                   "startedNow": True, "test": True,
                                   "incidents": incidents}]}
    return event_batch, incident_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--incidents", type=Path, required=True)
    args = parser.parse_args()
    events, incidents = build_batches(args.run_id)
    args.events.write_text(json.dumps(events, ensure_ascii=False) + "\n", encoding="utf-8")
    args.incidents.write_text(json.dumps(incidents, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
