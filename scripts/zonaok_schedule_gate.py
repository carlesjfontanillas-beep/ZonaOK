#!/usr/bin/env python3
"""Gate temporal dels workflows FECAPA ZonaOK.

Les expressions de GitHub Actions són UTC. Aquest helper valida CET/CEST,
obre lectures de partit dins la finestra horària indicada a l'Agenda, i només
tracta un resultat com a final quan FECAPA n'aporta un estat final explícit.
La manca d'IDP deixa el partit pendent; no prova que l'acta existeixi.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
DAILY_CRON = "2 6,7,18,19 * * *"
AGENDA_CRONS = {"0 8 * * *", "0 9 * * *"}
LIVE_CRONS = {
    "agenda": "1,6,11,16,21,26,31,36,41,46,51,56 * * * *",
    "directe": "2,7,12,17,22,27,32,37,42,47,52,57 * * * *",
    "actes": "3,8,13,18,23,28,33,38,43,48,53,58 * * * *",
    "classificacions": "4,9,14,19,24,29,34,39,44,49,54,59 * * * *",
}
LEGACY_LIVE_CRON = "1-59/5 * * * *"
WINDOW = timedelta(minutes=150)
# La cua de GitHub pot executar el torn de les 23:30 uns minuts més tard.
DIRECTE_LEAD = timedelta(minutes=30)
DIRECTE_GRACE = timedelta(minutes=15)
FINAL_STATUS = re.compile(r"\b(FINAL|FINALITZAT|FINALIZADO|ACABAT|ACABADO|FINISHED|FULL TIME)\b", re.I)


def scheduled_local_hour(cron: str, now: datetime) -> int | None:
    """Map one UTC cron slot to its Madrid wall-clock hour, validating DST."""
    if cron not in AGENDA_CRONS and cron != DAILY_CRON:
        return None
    utc_hour = {"0 8 * * *": 8, "0 9 * * *": 9}.get(cron)
    if cron == DAILY_CRON:
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
        return {10} if hour == 10 else set()
    return {8, 20} if hour in (8, 20) else set()


def read_matches(path: Path) -> list[dict]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    matches = doc.get("matches", []) if isinstance(doc, dict) else []
    return [row for row in matches if isinstance(row, dict)] if isinstance(matches, list) else []


def has_idp(row: dict) -> bool:
    return bool(str(row.get("matchId") or row.get("idp") or row.get("id") or "").strip())


def has_score(row: dict) -> bool:
    values = (row.get("homeScore"), row.get("awayScore"))
    return all(isinstance(value, int) and not isinstance(value, bool) for value in values)


def finished_with_score(row: dict, local_date: str) -> bool:
    if str(row.get("iso") or "") > local_date or not has_score(row):
        return False
    status=str(row.get("status") or "")
    if FINAL_STATUS.search(status):return True
    # Agenda FECAPA sovint publica un marcador històric sense text FINAL.
    return (str(row.get("iso") or "") < local_date
            and row.get("scoreSource") in ("Agenda","En directe")
            and bool(row.get("scoreUpdatedAt"))
            and not re.search(r"EN JOC|EN DIRECTE|LIVE|PLAYING|AJORNAT|SUSPES|CANCEL",status,re.I))


def pending_acta_count(path: Path, now: datetime) -> int:
    today = now.astimezone(MADRID).date().isoformat()
    return sum(1 for row in read_matches(path)
               if finished_with_score(row, today)
               and (not has_idp(row) or row.get("actaState") != "available"))


def pending_idp_count(path: Path, now: datetime) -> int:
    today = now.astimezone(MADRID).date().isoformat()
    return sum(1 for row in read_matches(path)
               if finished_with_score(row, today) and not has_idp(row)
               and re.fullmatch(r"\d{4,6}", str(row.get("leagueId") or "")))


def fixture_window_count(path: Path, now: datetime, *, lead: timedelta = timedelta(0), grace: timedelta = timedelta(0)) -> int:
    count = 0
    local_now = now.astimezone(MADRID)
    for row in read_matches(path):
        status = str(row.get("status") or "")
        if FINAL_STATUS.search(status) and has_score(row):
            continue
        if re.search(r"AJORNAT|APLAZADO|SUSP[EÈ]S|SUSPENDIDO|CANCEL", status, re.I):
            continue
        try:
            start = datetime.strptime(
                f"{row.get('iso', '')} {row.get('time', '')}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=MADRID)
        except (TypeError, ValueError):
            continue
        if -lead <= local_now - start <= WINDOW + grace:
            count += 1
    return count


def directe_followup_count(path: Path, now: datetime) -> int:
    """Bound the five-minute fallback to active or immediately upcoming matches."""
    local=now.astimezone(MADRID)
    horizon=local+timedelta(minutes=5)
    count=0
    for row in read_matches(path):
        status=str(row.get('status') or '')
        if FINAL_STATUS.search(status) and has_score(row):continue
        if re.search(r'AJORN|APLAZ|SUSP[EÈ]|SUSPEND|CANCEL|ANUL',status,re.I):continue
        try:start=datetime.strptime(f"{row.get('iso','')} {row.get('time','')}",'%Y-%m-%d %H:%M').replace(tzinfo=MADRID)
        except (ValueError,TypeError):continue
        if start.date()!=local.date() and not (start.date()==local.date()-timedelta(days=1) and start.hour>=20 and local.hour<4):continue
        nc=str(row.get('competition','')).upper() in ('NACIONAL CATALANA MASCULINA','NACIONAL CATALANA FEMENINA')
        earliest=start+(-DIRECTE_LEAD if nc else timedelta(minutes=40))
        latest=start+WINDOW+DIRECTE_GRACE
        if earliest<=horizon and local<=latest:count+=1
    return count


def should_run(mode: str, cron: str, now: datetime, matches: Path) -> tuple[bool, str]:
    local = now.astimezone(MADRID)
    if mode == "agenda":
        expected = expected_local_hours(cron, now)
        # Match the intended slot, not the actual minute: delayed jobs still run.
        return (True,"daily_agenda_10_madrid") if 10 in expected else (False,"not_the_10_madrid_slot")
    if cron == DAILY_CRON:
        if mode != "directe":
            return False, "daily_rest_check_only_for_directe"
        expected = expected_local_hours(cron, now)
        if local.hour in expected:
            return True, "daily_rest_check"
        return False, "invalid_cet_cest_daily_slot"
    # Accept both the original and staggered En directe fallback schedule.
    valid_crons={LIVE_CRONS[mode], LEGACY_LIVE_CRON}
    if mode=="directe":valid_crons.add("2,12,22,32,42,52 * * * *")
    if cron not in valid_crons:
        return False, "unrecognized_schedule"
    if mode=="directe":
        # No lectura històrica ni repàs matí/vespre.
        count=0
        for row in read_matches(matches):
            status=str(row.get('status') or '')
            if FINAL_STATUS.search(status) and has_score(row):continue
            if re.search(r'AJORN|APLAZ|SUSP[EÈ]|SUSPEND|CANCEL|ANUL',status,re.I):continue
            try:start=datetime.strptime(f"{row.get('iso','')} {row.get('time','')}",'%Y-%m-%d %H:%M').replace(tzinfo=MADRID)
            except (TypeError,ValueError):continue
            if start.date()!=local.date() and not (start.date()==local.date()-timedelta(days=1) and start.hour>=20 and local.hour<4):continue
            nc=str(row.get('competition','')).upper() in ('NACIONAL CATALANA MASCULINA','NACIONAL CATALANA FEMENINA')
            if local-start>=(-DIRECTE_LEAD if nc else timedelta(minutes=40)):count+=1
        return bool(count),f'live_day_candidates:{count}'
    in_window = fixture_window_count(matches, now)
    if mode in ("actes", "classificacions"):
        pending = pending_acta_count(matches, now)
        if pending:
            return True, f"finished_pending_acta:{pending}"
    if in_window:
        return True, f"scheduled_match_window:{in_window}"
    return False, "no_fixture_window_or_pending_acta"


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
