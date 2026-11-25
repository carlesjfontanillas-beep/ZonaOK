#!/usr/bin/env python3
"""Auditoria i fusio conservadora de duplicats del cataleg oficial ZonaOK."""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from zonaok_fecapa_unificat import (
    clean, norm, check_iso, check_time, check_when, make_match_url,
    official_match_url, score_tuple, utc_now, local_today, load_unified, write_compatibility,
)

TIMES = {"lastAgendaAt", "lastDirecteAt", "directeUpdatedAt", "scoreUpdatedAt",
         "actaCheckedAt", "updatedAt", "capturedAt", "checkedAt"}
TEXT = {"home", "away", "competition", "venue", "round", "status"}

def present(v):
    return v is not None and v != ""

def identity(row):
    return (clean(row.get("leagueId") or row.get("league")),
            clean(row.get("matchId") or row.get("id")))

def official_id(row):
    a, b = identity(row)
    return (a,b) if make_match_url(a,b) else None

def fixture(row):
    if not check_iso(row.get("iso")) or not check_time(row.get("time")):
        return None
    k = (row["iso"], row["time"], norm(row.get("competition")),
         norm(row.get("home")), norm(row.get("away")))
    return k if all(k) and k[3] != k[4] else None

def minute(row):
    h,m=map(int,row["time"].split(":"))
    return h*60+m

def day_fixture(row):
    k=fixture(row)
    return (k[0],*k[2:]) if k else None

LIVE_OR_INVALID = re.compile(r"\\b(EN JOC|EN DIRECTE|PLAYING|LIVE|IN PROGRESS|AJORNAT|APLAZADO|SUSPES|SUSPENDIDO|CANCEL LAT|CANCELADO|CANCELLED)\\b")
FINAL = re.compile(r"\\b(FINAL|FINALITZAT|FINALIZADO|ACABAT|TERMINADO|TANCAT|CERRADO|FINISHED|COMPLETED)\\b")

def finished_score(row):
    status=norm(row.get("status"))
    return score_tuple(row) and not LIVE_OR_INVALID.search(status) and (
        bool(FINAL.search(status)) or row["iso"] < local_today().isoformat())

def blank_score(row):
    status=norm(row.get("status"))
    return row.get("homeScore") is None and row.get("awayScore") is None and not (
        LIVE_OR_INVALID.search(status) or FINAL.search(status))

def merge_group(group, scored_reference=None):
    """No perdre cap camp significatiu ni resoldre conflictes esportius a cegues."""
    if any(not isinstance(r, dict) for r in group):
        return None, "invalid_row"
    for r in group:
        a,b=identity(r)
        if any(present(r.get(x)) and present(r.get(y)) and clean(r[x])!=clean(r[y])
               for x,y in (("leagueId","league"),("matchId","id"))):
            return None, "contradictory_alias"
        if r.get("actaUrl") and not official_match_url(r["actaUrl"],a,b):
            return None, "invalid_acta_url"
        if (r.get("homeScore") is None) != (r.get("awayScore") is None):
            return None, "partial_score"
        if r.get("homeScore") is not None and not score_tuple(r):
            return None, "invalid_score"
    for i in (0,1):
        if len({identity(r)[i] for r in group if identity(r)[i]})>1:
            return None, "different_official_ids"
    base = scored_reference if scored_reference is not None else max(group, key=lambda r:(bool(official_id(r)),r.get("actaState")=="available",
                                   score_tuple(r),sum(present(v) for v in r.values())))
    out=dict(base)
    for field in sorted(set().union(*(r.keys() for r in group))):
        if scored_reference is not None and field in {"time","status","scoreSource","scoreUpdatedAt","lastDirecteAt","directeUpdatedAt"}:
            if field in scored_reference:
                out[field]=scored_reference[field]
            continue
        vals=[r[field] for r in group if field in r and present(r[field])]
        if not vals:
            if field not in out:
                out[field]=next(r[field] for r in group if field in r)
            continue
        if all(type(v)==type(vals[0]) and v==vals[0] for v in vals):
            out[field]=vals[0];continue
        if field in TEXT and all(isinstance(v,str) for v in vals) and len({norm(v) for v in vals})==1:
            out[field]=base.get(field) or vals[0];continue
        if field in {"leagueId","matchId","league","id"} and len({clean(v) for v in vals})==1:
            out[field]=clean(vals[0]);continue
        if field in TIMES:
            try:
                out[field]=max(vals,key=check_when);continue
            except (TypeError,ValueError):
                return None,"invalid_timestamp:"+field
        if field=="actaState" and set(vals)<= {"pending","available"}:
            out[field]="available" if "available" in vals else "pending";continue
        if field=="scoreSource" and all(isinstance(v,str) for v in vals):
            if {norm(v) for v in vals} <= {"AGENDA","EN DIRECTE","DIRECTE"}:
                out[field]="En directe" if any(norm(v) in {"EN DIRECTE","DIRECTE"} for v in vals) else vals[0]
                continue
        if field=="actaUrl":
            a=next((identity(r)[0] for r in group if identity(r)[0]),"")
            b=next((identity(r)[1] for r in group if identity(r)[1]),"")
            if make_match_url(a,b) and all(official_match_url(v,a,b) for v in vals):
                out[field]=make_match_url(a,b);continue
        return None,"conflict:"+field
    a,b=identity(out)
    if make_match_url(a,b):
        out["leagueId"],out["matchId"]=a,b
        if not out.get("actaUrl"):
            out["actaUrl"]=make_match_url(a,b)
            out.setdefault("actaState","pending")
    return out,None

def deduplicate(rows):
    active={i:r for i,r in enumerate(rows)}
    report={"before":len(rows),"merged":[],"review":[]}
    protected=set()
    for kind,keyfn in (("official_id",official_id),("exact_fixture",fixture)):
        groups=defaultdict(list)
        for i,r in active.items():
            if isinstance(r,dict):
                k=keyfn(r)
                if k:groups[k].append(i)
        for k,ids in groups.items():
            if len(ids)<2:continue
            group=[active[i] for i in ids]
            if any(i in protected for i in ids):
                report["review"].append({"kind":kind,"key":k,"reason":"previous_conflict","rows":group})
                protected.update(ids);continue
            references=[r for r in group if score_tuple(r)]
            reference=references[0] if (len(references)==1 and day_fixture(references[0]) and finished_score(references[0])
                and all(r is references[0] or (blank_score(r) and day_fixture(r)==day_fixture(references[0])
                        and abs(minute(r)-minute(references[0]))<=90) for r in group)
                and day_fixture(references[0])) else None
            merged,reason=merge_group(group,scored_reference=reference)
            if reason:
                report["review"].append({"kind":kind,"key":k,"reason":reason,"rows":group})
                protected.update(ids);continue
            report["merged"].append({"kind":kind,"key":k,"removed":len(ids)-1,
                                     "originalRows":group,"result":merged})
            active[ids[0]]=merged
            for i in ids[1:]:del active[i]
    # Agenda general i calendari de lliga poden conservar hores diferents del
    # mateix partit. Només fusionar amb una referència amb marcador final,
    # equips/categoria/data iguals i cap altre partit amb marcador al grup.
    groups=defaultdict(list)
    for i,r in active.items():
        k=day_fixture(r)
        if k:groups[k].append(i)
    for k,ids in groups.items():
        if len(ids)<2:continue
        scored=[i for i in ids if score_tuple(active[i])]
        if len(scored)!=1 or not finished_score(active[scored[0]]):continue
        keep=scored[0]
        ref=active[keep]
        candidates=[i for i in ids if i!=keep and blank_score(active[i]) and
                    abs(minute(active[i])-minute(ref))<=90]
        if not candidates:continue
        chosen=[keep,*candidates]
        group=[active[i] for i in chosen]
        if any(i in protected for i in chosen):
            report["review"].append({"kind":"changed_time","key":k,"reason":"previous_conflict","rows":group})
            continue
        merged,reason=merge_group(group,scored_reference=ref)
        if reason:
            report["review"].append({"kind":"changed_time","key":k,"reason":reason,"rows":group})
            continue
        report["merged"].append({"kind":"changed_time","key":k,"removed":len(candidates),
                                 "originalRows":group,"result":merged})
        active[keep]=merged
        for i in candidates:del active[i]
    # Un equip no hauria de tenir dos partits simultanis dins la mateixa
    # competició. Si el rival és diferent, auditar sense inventar quin és fals.
    slots=defaultdict(list)
    for i,r in active.items():
        k=fixture(r)
        if not k:continue
        for team in (k[3],k[4]):slots[(k[0],k[1],k[2],team)].append(i)
    overlaps=set()
    for k,ids in slots.items():
        if len(ids)<2:continue
        signature=tuple(sorted(ids))
        if signature in overlaps:continue
        overlaps.add(signature)
        group=[active[i] for i in ids]
        if len({day_fixture(r) for r in group})>1:
            report["review"].append({"kind":"same_team_same_time","key":k,
                                     "reason":"different_opponents_or_home_away","rows":group})
    result=list(active.values())
    report.update(after=len(result),removed=len(rows)-len(result),
                  reviewGroups=len(report["review"]),mergedGroups=len(report["merged"]))
    assert report["removed"]==sum(g["removed"] for g in report["merged"])
    assert {official_id(r) for r in rows if official_id(r)} == {official_id(r) for r in result if official_id(r)}
    return result,report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--report",default="diagnostic-duplicats.json")
    args=p.parse_args()
    path=Path("zonaok-tots-partits.json")
    doc=load_unified(path)
    rows,report=deduplicate(doc["matches"])
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if args.apply and report["removed"]:
        doc["matches"]=rows
        doc["updatedAt"]=utc_now()
        doc["stats"]={**doc.get("stats",{}),"total":len(rows),
                      "withScores":sum(score_tuple(r) for r in rows),
                      "withActaLinks":sum(bool(r.get("actaUrl")) for r in rows),
                      "verifiedActes":sum(r.get("actaState")=="available" for r in rows)}
        path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        write_compatibility(doc)
    print(json.dumps({k:v for k,v in report.items() if k not in ("merged","review")},ensure_ascii=False))
    for g in report["merged"][:30]:
        print("FUSIO",json.dumps({"kind":g["kind"],"key":g["key"],
             "times":[r.get("time") for r in g["originalRows"]],
             "kept":g["result"].get("time"),"score":[g["result"].get("homeScore"),g["result"].get("awayScore")]},ensure_ascii=False))
    for g in report["review"][:30]:
        print("REVISAR",json.dumps({"kind":g["kind"],"key":g["key"],"reason":g["reason"],
              "rows":[{k:r.get(k) for k in ("time","home","away","homeScore","awayScore","leagueId","matchId","round")} for r in g["rows"]]},ensure_ascii=False))

if __name__=="__main__":
    main()
