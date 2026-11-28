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
NC = {"NACIONAL CATALANA MASCULINA","NACIONAL CATALANA FEMENINA"}
EXCLUDED = re.compile(r"AJORN|APLAZ|SUSP[EÈ]|SUSPEND|CANCEL|ANUL", re.I)
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

def observed(row, source='directe'):
    try:
        raw=row.get('lastAgendaAt') if source=='agenda' else row.get('lastDirecteAt') or row.get('directeUpdatedAt')
        value=datetime.fromisoformat(str(raw or '').replace('Z','+00:00'))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (ValueError,TypeError):
        return None

def fixture_payload(r):
    return {k:r.get(k,"") for k in ("iso","time","competition","home","away","leagueId","matchId","homeLogo","awayLogo","round")}

def scheduled_candidates(catalog):
    if catalog.get("schema")!="zonaok-partits-total-v1":raise ValueError("Invalid FECAPA catalog")
    rows=[r for r in catalog.get("matches",[]) if isinstance(r,dict)]
    counts=Counter(identity(r) for r in rows)
    ids=Counter((str(r.get("leagueId") or ""),str(r.get("matchId") or "")) for r in rows)
    output=[]
    for r in rows:
        key=identity(r)
        if not key or counts[key]!=1 or EXCLUDED.search(norm(r.get("status"))) or norm(r.get("status")) in FINAL:continue
        try:start=datetime.strptime(r["iso"]+" "+r["time"],"%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
        except (ValueError,TypeError,KeyError):continue
        stable=(str(r.get("leagueId") or ""),str(r.get("matchId") or ""))
        if all(stable) and ids[stable]!=1:continue
        event_id=hashlib.sha256(json.dumps([catalog.get("season"),stable if all(stable) else key,"scheduledStart"],ensure_ascii=False).encode()).hexdigest()
        fixture=fixture_payload(r)
        output.append((start,event_id,fixture,norm(r.get("competition")) in NC))
    return output

def scheduled_starts(catalog, *, now, plan=None):
    """Use the current catalogue to confirm every planned start before delivery.
    Newly rescheduled fixtures can still be sent if absent from the morning plan.
    """
    local=now.astimezone(MADRID)
    planned={x['eventId'] for x in (plan or {}).get('events',[]) if x.get('mode')=='scheduled'} if (plan or {}).get('season')==catalog.get('season') else set()
    output=[]
    for start,event_id,fixture,nc in scheduled_candidates(catalog):
        if nc or start.date()!=local.date() or not timedelta(0)<=local-start<=timedelta(minutes=10):continue
        fixture["startSource"]="Agenda"
        output.append({"eventId":event_id,"event":"start","source":"FECAPA","observedAt":now.isoformat(),"fixture":fixture,"startSource":"Agenda"})
    return sorted(output,key=lambda e:(e['eventId'] not in planned,e['fixture']['iso'],e['fixture']['time'],e['eventId']))

def detect(before, after, *, since, now, source='both'):
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
    for r in current if source in ('both','directe') else []:
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
        local=now.astimezone(MADRID)
        if now<start or (start.date()!=local.date() and not (start.date()==local.date()-timedelta(days=1) and start.hour>=20 and local.hour<4)):
            continue
        previous_status,status=norm(p.get("status")),norm(r.get("status"))
        if previous_status in FINAL:
            continue
        if status in FINAL and valid_score(r):
            event="finish"
        elif norm(r.get("competition")) in NC and status in LIVE and previous_status not in LIVE:
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
    for key,r in current_ids.items() if source in ('both','agenda') else []:
        p=old_ids.get(key)
        if not p or (p.get("iso"),p.get("time"))==(r.get("iso"),r.get("time")):
            continue
        if any(norm(p.get(k))!=norm(r.get(k)) for k in ("competition","home","away")):
            continue
        captured=observed(r,'agenda')
        if not captured or not (since<captured<=now) or (observed(p,'agenda') and captured<=observed(p,'agenda')):
            continue
        if norm(r.get('status')) in FINAL|LIVE or EXCLUDED.search(norm(r.get('status'))):
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
    # General Agenda has no IDP. The daily merge records a mutually unique
    # season-wide pairing. Verify the prior exact fixture before notifying.
    if source in ('both','agenda'):
        for r in current:
            if all(str(r.get(k) or '') for k in ('leagueId','matchId')):continue
            meta=r.get('agendaScheduleChange') or {}
            captured=observed(r,'agenda')
            if not captured or not (since<captured<=now) or meta.get('capturedAt')!=r.get('lastAgendaAt') or meta.get('proof') not in ('exact','unique-season-pair'):continue
            if norm(r.get('status')) in FINAL|LIVE or EXCLUDED.search(norm(r.get('status'))):continue
            old_key=tuple(norm(v) for v in (meta.get('previousIso'),meta.get('previousTime'),r.get('competition'),r.get('home'),r.get('away')))
            prior=old.get(old_key)
            if not prior or new_counts[identity(r)]!=1 or old_counts[old_key]!=1:continue
            if (prior.get('iso'),prior.get('time'))==(r.get('iso'),r.get('time')):continue
            try:
                kickoff=datetime.strptime(r['iso']+' '+r['time'],'%Y-%m-%d %H:%M').replace(tzinfo=MADRID)
            except (KeyError,ValueError,TypeError):continue
            if kickoff<=now.astimezone(MADRID):continue
            eid=hashlib.sha256(json.dumps([after.get('season'),old_key,identity(r),'scheduleChange'],ensure_ascii=False).encode()).hexdigest()
            fixture=fixture_payload(r);fixture.update(previousIso=prior['iso'],previousTime=prior['time'])
            output.append({'eventId':eid,'event':'scheduleChange','source':'FECAPA','observedAt':captured.isoformat(),'fixture':fixture})
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before",type=Path)
    p.add_argument("--after",type=Path,required=True)
    p.add_argument("--since")
    p.add_argument("--source",choices=['both','directe','agenda'],default='both')
    p.add_argument("--scheduled",action='store_true')
    p.add_argument("--include-scheduled",action='store_true')
    p.add_argument("--plan",type=Path)
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    after=json.loads(args.after.read_text())
    plan=json.loads(args.plan.read_text()) if args.plan and args.plan.exists() else None
    if args.scheduled:events=scheduled_starts(after,now=now,plan=plan)
    else:
        if not args.before or not args.since:p.error('--before and --since are required')
        since=datetime.fromisoformat(args.since.replace("Z","+00:00"))
        events=detect(json.loads(args.before.read_text()),after,since=since,now=now,source=args.source)
    if args.include_scheduled and not args.scheduled:
        events=list({e["eventId"]:e for e in events+scheduled_starts(after,now=now,plan=plan)}.values())
    print(json.dumps({"dryRun":True,"events":events},ensure_ascii=False))
if __name__=="__main__":
    main()

