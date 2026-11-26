#!/usr/bin/env python3
"""Detect verified new sports events from successive FECAPA catalog snapshots.

Pure, read-only detector. No delivery, credentials, subscription data or
historical replay. Backend must enforce opt-in and persistent event idempotency.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
WINDOW = timedelta(minutes=165)
LIVE = {"EN JOC", "EN DIRECTE", "EN DIRECTO", "LIVE", "PLAYING",
        "IN PROGRESS", "PRIMERA PART", "SEGONA PART", "DESCANS",
        "PRIMERA PARTE", "SEGUNDA PARTE", "DESCANSO"}
FINAL = {"FINAL", "FINALITZAT", "FINALIZADO", "ACABAT", "ACABADO",
         "FINISHED", "FULL TIME"}

def norm(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFD",str(value or ""))
                            if unicodedata.category(c)!="Mn").upper().split())

def identity(row):
    fields=tuple(norm(row.get(k)) for k in ("iso","time","competition","home","away"))
    return fields if all(fields) else None

def valid_score(row):
    return all(type(row.get(k)) is int and row[k]>=0 for k in ("homeScore","awayScore"))

def observed(row):
    try:
        value=datetime.fromisoformat(str(row.get("lastDirecteAt") or row.get("directeUpdatedAt") or "").replace("Z","+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (ValueError,TypeError):
        return None

def detect(before, after, *, since, now):
    if since.tzinfo is None or now.tzinfo is None or since>now:
        raise ValueError("Invalid observation window")
    def rows(doc):
        if doc.get("schema")!="zonaok-partits-total-v1" or not isinstance(doc.get("matches"),list):
            raise ValueError("Invalid FECAPA catalog")
        return [r for r in doc["matches"] if isinstance(r,dict)]
    previous, current=rows(before),rows(after)
    if before.get("season")!=after.get("season"):
        return []
    old_counts=Counter(identity(r) for r in previous)
    new_counts=Counter(identity(r) for r in current)
    old={identity(r):r for r in previous if identity(r) and old_counts[identity(r)]==1}
    output=[]
    for r in current:
        key=identity(r)
        if not key or new_counts[key]!=1 or key not in old:
            continue
        p=old[key]
        if any(p.get(k) and r.get(k) and str(p[k])!=str(r[k]) for k in ("leagueId","matchId")):
            continue
        captured=observed(r)
        if not captured or not (since<captured<=now) or (observed(p) and captured<=observed(p)):
            continue
        try:
            start=datetime.strptime(r["iso"]+" "+r["time"],"%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
        except (ValueError,TypeError,KeyError):
            continue
        if not timedelta(0)<=now-start<=WINDOW:
            continue
        previous_status,status=norm(p.get("status")),norm(r.get("status"))
        if previous_status in FINAL:
            continue
        if status in FINAL and valid_score(r):
            event="finish"
        elif status in LIVE and previous_status not in LIVE:
            event="start"
        else:
            continue
        event_id=hashlib.sha256(json.dumps([after.get("season"),key,event],ensure_ascii=False).encode()).hexdigest()
        item={"eventId":event_id,"event":event,"source":"FECAPA","observedAt":captured.isoformat(),
              "fixture":{k:r.get(k,"") for k in ("iso","time","competition","home","away","leagueId","matchId","homeLogo","awayLogo","round")}}
        if event=="finish":
            item["fixture"].update(homeScore=r["homeScore"],awayScore=r["awayScore"])
        output.append(item)
    # Schedule changes match by stable FECAPA ids, not date/time. Require a
    # unique row on each side so duplicate catalog records cannot notify.
    def ids(rows):
        counts=Counter((str(r.get("leagueId") or ""),str(r.get("matchId") or "")) for r in rows)
        result={}
        for r in rows:
            key=(str(r.get("leagueId") or ""),str(r.get("matchId") or ""))
            if all(key) and counts[key]==1: result[key]=r
        return result
    old_ids,current_ids=ids(previous),ids(current)
    for key,r in current_ids.items():
        p=old_ids.get(key)
        if not p or (p.get("iso"),p.get("time"))==(r.get("iso"),r.get("time")):
            continue
        if any(norm(p.get(k))!=norm(r.get(k)) for k in ("competition","home","away")):
            continue
        captured=observed(r)
        if not captured or not (since<captured<=now) or (observed(p) and captured<=observed(p)):
            continue
        if norm(r.get("status")) in FINAL|LIVE:
            continue
        try:
            start=datetime.strptime(r["iso"]+" "+r["time"],"%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
            if start<=now.astimezone(MADRID):
                continue
        except (ValueError,TypeError,KeyError):
            continue
        event_id=hashlib.sha256(json.dumps([after.get("season"),key[0],key[1],"scheduleChange",p.get("iso"),p.get("time"),r.get("iso"),r.get("time")],ensure_ascii=False).encode()).hexdigest()
        item={"eventId":event_id,"event":"scheduleChange","source":"FECAPA","observedAt":captured.isoformat(),
              "fixture":{k:r.get(k,"") for k in ("iso","time","competition","home","away","leagueId","matchId","homeLogo","awayLogo","round")}}
        item["fixture"].update(previousIso=p.get("iso"),previousTime=p.get("time"))
        output.append(item)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before",type=Path,required=True)
    p.add_argument("--after",type=Path,required=True)
    p.add_argument("--since",required=True,help="ISO timestamp after activation or last successful observation")
    args=p.parse_args()
    since=datetime.fromisoformat(args.since.replace("Z","+00:00"))
    events=detect(json.loads(args.before.read_text()),json.loads(args.after.read_text()),since=since,now=datetime.now(timezone.utc))
    print(json.dumps({"dryRun":True,"events":events},ensure_ascii=False))
if __name__=="__main__":
    main()

