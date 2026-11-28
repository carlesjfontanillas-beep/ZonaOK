#!/usr/bin/env python3
"""Create isolated fictional catalog snapshots and a mock FECAPA acta."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SEASON = "2026/2027"
MADRID = ZoneInfo("Europe/Madrid")
COMPETITION = "NACIONAL CATALANA MASCULINA"


def build_fixture_data(run_id, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    local_now = now.astimezone(MADRID)
    kickoff = (local_now - timedelta(minutes=3)).replace(second=0, microsecond=0)
    suffix = str(run_id)
    live = {
        "iso": kickoff.date().isoformat(), "time": kickoff.strftime("%H:%M"),
        "competition": COMPETITION, "home": "BARÇA",
        "away": "EQUIP FICTICI PROVA " + suffix, "leagueId": "4774",
        "matchId": "TEST-NC-M-" + suffix, "status": "EN JOC",
        "homeScore": 0, "awayScore": 0,
    }
    before_time = (now - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    live_time = (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    final_time = now.isoformat().replace("+00:00", "Z")
    initial = {**live, "status": "PROGRAMAT", "lastDirecteAt": before_time}
    current = {**live, "lastDirecteAt": live_time}
    final = {**live, "status": "FINAL", "homeScore": 1, "awayScore": 0,
             "lastDirecteAt": final_time}

    new_day = (local_now + timedelta(days=3)).date().isoformat()
    schedule_before = {
        "iso": new_day, "time": "18:00", "competition": COMPETITION,
        "home": "BARÇA", "away": "ALTRE EQUIP FICTICI " + suffix,
        "leagueId": "4774", "matchId": "TEST-NC-M-SCHEDULE-" + suffix,
        "status": "PROGRAMAT", "lastAgendaAt": before_time,
    }
    schedule_after = {**schedule_before, "time": "19:00", "lastAgendaAt": live_time}

    def catalog(matches):
        return {"schema": "zonaok-partits-total-v1", "season": SEASON,
                "sources": {"directe": {"capturedAt": live_time}}, "matches": matches}

    before = catalog([initial, schedule_before])
    current_catalog = catalog([current, schedule_after])
    final_catalog = catalog([final, schedule_after])
    acta = {
        "fixture": {k: live[k] for k in ("iso", "time", "competition", "home", "away", "leagueId", "matchId")},
        "observedAt": final_time,
        "text": """INCIDÈNCIES
P1 01:00
1 - 0
GOL BARÇA
#99 JUGADOR DE PROVA
P1 02:00
TARGETA GROGA BARÇA
#99 JUGADOR DE PROVA
P1 03:00
FALTA DIRECTA PER A BARÇA
#99 JUGADOR DE PROVA
""",
    }
    return before, current_catalog, final_catalog, acta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument("--acta", type=Path, required=True)
    args = parser.parse_args()
    docs = build_fixture_data(args.run_id)
    for path, doc in zip((args.before, args.live, args.final, args.acta), docs):
        path.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
