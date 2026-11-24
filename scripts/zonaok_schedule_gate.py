#!/usr/bin/env python3
"""Gate temporal dels workflows FECAPA ZonaOK.

Les expressions de GitHub Actions són UTC. Aquest helper valida les dues
expressions de temporada (CET/CEST) i només obre consultes de partit dins
d'una finestra calculada a partir de l'hora de partit guardada a l'Agenda.
No infereix que un partit estigui en joc ni que una acta existeixi.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
DAILY_CRON = "2 6,7,18,19 * * *"
AGENDA_CRONS = {"0 12 * * *", "0 13 * * *"}
LIVE_CRON = "*/5 * * * *"
WINDOW = timedelta(minutes=150)


def scheduled_local_hour(cron: str, now: datetime) -> int | None:
    """Map one UTC cron slot to its Madrid wall-clock hour, validating DST."""
    if cron not in AGENDA_CRONS and cron != DAILY_CRON:
        return None
    utc_hour = {"0 12 * * *": 12, "0 13 * * *": 13}.get(cron)
    if cron == DAILY_CRON:
        # One expression represents four seasonal UTC slots.
        utc_hour = now.astimezone(ZoneInfo("UTC")).hour
        if utc_hour not in (6, 7, 18, 19):
            return None
    offset = now.astimezone(MADRID).utcoffset()
    if offset is None:
        return None
    hours = int(offset.total_seconds() // 3600)
    if hours not in (1, 2):
        return None
    return (utc_hour + hours) % 24


def expected_local_hours(cron: str, now: datetime) -> set[int]:
    hour = scheduled_local_hour(cron, now)
    if hour is None:
        return set()
    if cron in AGENDA_CRONS:
        return {14} if hour == 14 else set()
    return {8, 20} if hour in (8, 20) else set()


def fixture_window_count(path: Path, now: datetime) -> int:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    matches = doc.get("matches", []) if isinstance(doc, dict) else []
    count = 0
    local_now = now.astimezone(MADRID)
    for row in matches if isinstance(matches, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            start = datetime.strptime(
                f"{row.get('iso', '')} {row.get('time', '')}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=MADRID)
        except (TypeError, ValueError):
            continue
        if timedelta(0) <= local_now - start <= WINDOW:
            count += 1
    return count


def should_run(mode: str, cron: str, now: datetime, matches: Path) -> tuple[bool, str]:
    local = now.astimezone(MADRID)
    if mode == "agenda":
        expected = expected_local_hours(cron, now)
        if local.hour == 14 and 14 in expected:
            return True, "daily_agenda_14_madrid"
        return False, "not_the_14_madrid_slot"
    if cron == DAILY_CRON:
        expected = expected_local_hours(cron, now)
        if local.hour in expected:
            return True, "daily_rest_check"
        return False, "invalid_cet_cest_daily_slot"
    if cron != LIVE_CRON:
        return False, "unrecognized_schedule"
    count = fixture_window_count(matches, now)
    if count:
        return True, f"scheduled_match_window:{count}"
    return False, "no_fixture_in_scheduled_time_window"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("agenda", "directe", "actes", "classificacions"), required=True)
    parser.add_argument("--schedule", default=os.environ.get("GITHUB_EVENT_SCHEDULE", ""))
    parser.add_argument("--matches", type=Path, default=Path("zonaok-tots-partits.json"))
    args = parser.parse_args()
    decision, reason = should_run(args.mode, args.schedule, datetime.now(MADRID), args.matches)
    print(f"run={'true' if decision else 'false'}")
    print(f"reason={reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"run={'true' if decision else 'false'}\nreason={reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
