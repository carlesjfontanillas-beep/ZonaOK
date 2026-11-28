#!/usr/bin/env python3
"""Replay a captured acta delta on the latest main, failing closed on conflicts."""
import gzip
import json
import re
import sys
from pathlib import Path
from collections import Counter

MISSING = object()
IDENTITY = ("iso", "time", "competition", "home", "away")
SCORES = ("homeScore", "awayScore")
FIELDS = frozenset(("leagueId", "matchId", "actaUrl", "actaState", "actaCheckedAt",
                    "homeScore", "awayScore", "scoreSource", "scoreUpdatedAt"))
CATALOG = "zonaok-tots-partits.json"
MASTER = "imports/jugadors-master.json.gz"
STATE = "imports/jugadors-maintenance-state.json"
CONTROL = "imports/actes-live-state.json"

class Conflict(ValueError):
    pass

def merge(base, captured, current, *, master=False, key=""):
    if captured == base:
        return current
    if current == captured or current == base:
        return captured
    if isinstance(captured, dict) and isinstance(current, dict) and (base is MISSING or isinstance(base, dict)):
        old = {} if base is MISSING else base
        result = dict(current)
        for k in old.keys() | captured.keys():
            b, a, c = old.get(k, MISSING), captured.get(k, MISSING), current.get(k, MISSING)
            if master and a is MISSING:
                continue  # Never remove existing player records or optional facts.
            value = merge(b, a, c, master=master, key=k)
            if value is MISSING:
                result.pop(k, None)
            else:
                result[k] = value
        return result
    if master and key == "nameVariants" and isinstance(captured, list) and isinstance(current, list):
        if all(isinstance(v, str) for v in captured + current):
            return sorted(set(captured + current))
    if master and key in ("firstSeenAt", "lastSeenAt") and all(isinstance(v, str) for v in (captured, current)):
        # Both producers use ISO UTC timestamps.
        if all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)", v) for v in (captured, current)):
            from datetime import datetime
            return (min if key == "firstSeenAt" else max)((captured, current), key=lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")))
    raise Conflict("overlapping edits in captured data")

def fixture_key(row):
    return tuple(row.get(k) for k in IDENTITY)

def merge_catalog(base, captured, current):
    before, after, latest = base["matches"], captured["matches"], current["matches"]
    if len(before) != len(after):
        raise Conflict("capture changed fixture count")
    result = list(latest)
    counts = Counter(fixture_key(r) for r in before)
    current_counts = Counter(fixture_key(r) for r in latest)
    index = {fixture_key(r): i for i, r in enumerate(latest)}
    official = Counter((str(r.get("leagueId") or ""), str(r.get("matchId") or "")) for r in latest)
    changed = 0
    for b, a in zip(before, after):
        if b == a:
            continue
        k = fixture_key(b)
        if fixture_key(a) != k or counts[k] != 1 or current_counts[k] != 1:
            raise Conflict("fixture identity changed or ambiguous")
        i = index[k]
        c = result[i]
        delta = {f for f in b.keys() | a.keys() if b.get(f, MISSING) != a.get(f, MISSING)}
        if not delta <= FIELDS:
            raise Conflict("capture modified unrelated fixture fields")
        if tuple(c.get(f) for f in SCORES) not in (tuple(b.get(f) for f in SCORES), tuple(a.get(f) for f in SCORES)):
            raise Conflict("concurrent score correction")
        if re.search(r"AJORN|APLAZ|SUSP|CANCEL|ANUL", str(c.get("status", "")), re.I):
            raise Conflict("fixture no longer eligible")
        for f in ("leagueId", "matchId"):
            if c.get(f) and a.get(f) and str(c[f]) != str(a[f]):
                raise Conflict("official fixture ID changed")
        row = dict(c)
        for f in delta:
            value = merge(b.get(f, MISSING), a.get(f, MISSING), c.get(f, MISSING))
            if value is MISSING:
                raise Conflict("capture removed fixture field")
            row[f] = value
        if c.get("actaState") == "available" and row.get("actaState") != "available":
            raise Conflict("verified acta would be lost")
        oldid = (str(c.get("leagueId") or ""), str(c.get("matchId") or ""))
        newid = (str(row.get("leagueId") or ""), str(row.get("matchId") or ""))
        if newid != oldid:
            if all(newid) and official[newid]:
                raise Conflict("duplicate official fixture ID")
            official[oldid] -= 1
            official[newid] += 1
        result[i] = row
        changed += 1
    return {**current, "matches": result}, changed

def read(root, name):
    p = root / name
    if name == CONTROL and not p.exists():
        return {}
    if name.endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(p.read_text(encoding="utf-8"))

def write(root, name, value):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":") if name.endswith(".gz") else None)
    if name.endswith(".gz"):
        p.write_bytes(gzip.compress(raw.encode("utf-8"), mtime=0))
    else:
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main(base, captured, current):
    from zonaok_fecapa_unificat import score_tuple, utc_now, write_compatibility
    from zonaok_jugadors_auto import verify_master
    catalog, changed = merge_catalog(*(read(root, CATALOG) for root in (base, captured, current)))
    master = merge(*(read(root, MASTER) for root in (base, captured, current)), master=True)
    # Maintenance match snapshots are atomic: do not mix two different
    # fingerprints, statuses or statistic revisions of the same official acta.
    states = [read(root, STATE) for root in (base, captured, current)]
    b, a, c = states
    state = merge({k:v for k,v in b.items() if k != "matches"},
                  {k:v for k,v in a.items() if k != "matches"},
                  {k:v for k,v in c.items() if k != "matches"})
    bm, am, cm = (d.get("matches", {}) for d in states)
    matches = dict(cm)
    for k in bm.keys() | am.keys():
        old, new, latest = bm.get(k, MISSING), am.get(k, MISSING), cm.get(k, MISSING)
        if new == old:
            continue
        if new is MISSING or (latest != old and latest != new):
            raise Conflict("concurrent change in same acta statistics")
        matches[k] = new
    state["matches"] = matches
    control = merge(*(read(root, CONTROL) for root in (base, captured, current)))
    verify_master(master)
    latest_master = read(current, MASTER)
    for section in ("players", "memberships", "matchAppearances"):
        if not latest_master[section].keys() <= master[section].keys():
            raise Conflict("player records would be lost")
    if len(master["players"]) == 0 or len(master["matchAppearances"]) == 0:
        raise Conflict("empty player master")
    catalog["updatedAt"] = utc_now()
    rows = catalog["matches"]
    catalog["stats"] = {**catalog.get("stats", {}), "total": len(rows),
        "withScores": sum(bool(score_tuple(r)) for r in rows),
        "withActaLinks": sum(bool(r.get("actaUrl")) for r in rows),
        "verifiedActes": sum(r.get("actaState") == "available" for r in rows)}
    write(current, CATALOG, catalog)
    write(current, MASTER, master)
    write(current, STATE, state)
    write(current, CONTROL, control)
    write_compatibility(catalog)
    print("Actes live: captura reutilitzada; partits modificats:", changed)

if __name__ == "__main__":
    try:
        main(*(Path(p) for p in sys.argv[1:]))
    except Conflict as exc:
        sys.exit("Publicació conservadora: " + str(exc))
