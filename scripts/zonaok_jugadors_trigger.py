#!/usr/bin/env python3
"""Dispatch the player importer only for newly completed, changed fixtures."""
import argparse
import json
import os
import re
import subprocess
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

FINAL = re.compile(
    r"\b(final|finalitzat|finalitzada|finalizado|finalizada|acabat|acabada|"
    r"terminado|terminada|tancat|tancada|cerrado|cerrada|partit finalitzat|"
    r"partido finalizado|acta tancada|acta cerrada|finished|completed)\b"
)
ID = re.compile(r"^[1-9][0-9]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MADRID = ZoneInfo("Europe/Madrid")


def norm(value):
    value = "".join(
        c for c in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(c)
    )
    return " ".join(value.lower().split())


def key(row):
    league = str(row.get("leagueId") or "")
    match = str(row.get("matchId") or row.get("id") or "")
    return f"{league}|{match}" if ID.fullmatch(league) and ID.fullmatch(match) else None


def fingerprint(row):
    return json.dumps(
        [row.get("homeScore"), row.get("awayScore"), norm(row.get("status")),
         row.get("actaState"), row.get("actaUrl")],
        ensure_ascii=False, separators=(",", ":"),
    )


def match_map(doc):
    rows = doc.get("matches", []) if isinstance(doc, dict) else []
    result = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_key = key(row)
        if item_key:
            result[item_key] = row
    return result


def eligible_final(row, today):
    iso = str(row.get("iso") or "")
    scores = (row.get("homeScore"), row.get("awayScore"))
    return (
        bool(DATE.fullmatch(iso))
        and iso <= today
        and all(type(value) is int and value >= 0 for value in scores)
        and bool(FINAL.search(norm(row.get("status"))))
    )


def pending_cooldown(entry, now):
    if entry.get("status") != "pending":
        return False
    try:
        checked = datetime.fromisoformat(str(entry["checkedAt"]).replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return now - checked < timedelta(minutes=15)
    except (KeyError, TypeError, ValueError):
        return False


def changed_finished_count(current, previous, state, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(MADRID).date().isoformat()
    current_rows = match_map(current)
    previous_rows = match_map(previous)
    checked = state.get("matches", {}) if isinstance(state, dict) else {}
    if not isinstance(checked, dict):
        checked = {}
    changed = 0
    for item_key, row in current_rows.items():
        if not eligible_final(row, today):
            continue
        stamp = fingerprint(row)
        prior = previous_rows.get(item_key)
        if prior is not None and fingerprint(prior) == stamp:
            continue
        entry = checked.get(item_key, {})
        if not isinstance(entry, dict):
            entry = {}
        if entry.get("status") == "verified" and entry.get("fingerprint") == stamp:
            continue
        if entry.get("fingerprint") == stamp and pending_cooldown(entry, now):
            continue
        changed += 1
    return changed


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def previous_commit(ref, path):
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--previous-ref", required=True)
    args = parser.parse_args()

    current = load_json(args.catalog)
    previous = previous_commit(args.previous_ref, str(args.catalog))
    count = changed_finished_count(current, previous, load_json(args.state))
    should_run = count > 0
    print(f"run={'true' if should_run else 'false'}")
    print(f"newFinishedFixtures={count}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"run={'true' if should_run else 'false'}\n")
            stream.write(f"newFinishedFixtures={count}\n")


if __name__ == "__main__":
    main()
