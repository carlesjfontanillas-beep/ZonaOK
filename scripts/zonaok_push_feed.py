#!/usr/bin/env python3
"""Maintain a short-lived public feed of newly detected FECAPA events."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEASON = "2026/2027"
TTL = timedelta(minutes=165)


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def build_feed(new_data, existing_data, *, now):
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if new_data.get("dryRun") is not True or not isinstance(new_data.get("events"), list):
        raise ValueError("invalid detector output")
    if existing_data and (existing_data.get("schema") != "zonaok-push-events-v1"
                          or existing_data.get("season") != SEASON
                          or not isinstance(existing_data.get("events"), list)):
        raise ValueError("invalid existing feed")

    cutoff = now.astimezone(timezone.utc) - TTL
    by_id = {}
    for item in (existing_data or {}).get("events", []) + new_data["events"]:
        if not isinstance(item, dict) or item.get("event") not in ("start", "finish"):
            continue
        event_id = item.get("eventId")
        if not isinstance(event_id, str) or len(event_id) != 64:
            continue
        created = timestamp(item.get("createdAt")) or now.astimezone(timezone.utc)
        if cutoff < created <= now.astimezone(timezone.utc) + timedelta(minutes=1):
            by_id[event_id] = {**item, "createdAt": created.isoformat().replace("+00:00", "Z")}

    events = sorted(by_id.values(), key=lambda item: (item["createdAt"], item["eventId"]))[-500:]
    return {
        "schema": "zonaok-push-events-v1",
        "season": SEASON,
        "updatedAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "events": events,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    new_data = json.loads(args.new.read_text(encoding="utf-8"))
    existing = json.loads(args.existing.read_text(encoding="utf-8")) if args.existing.exists() else None
    now = datetime.now(timezone.utc)
    feed = build_feed(new_data, existing, now=now)
    args.output.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
