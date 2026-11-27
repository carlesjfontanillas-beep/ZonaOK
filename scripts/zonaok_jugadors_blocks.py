#!/usr/bin/env python3
"""Bounded, resumable private player maintenance. Never print individual records."""
import argparse, asyncio, json, os, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from playwright.async_api import async_playwright
from zonaok_jugadors_incremental import candidates, closed_acta, merge_verified
from zonaok_jugadors_auto import collect, empty, enrich_names, load, now, save, verify_master
from zonaok_jugadors_total_master import read_catalog, link_memberships
from zonaok_actes_jugadors_probe import ingest_appearances
from zonaok_fecapa_players import chromium_context

STATS_REVISION = 4
LIMITS = {"acts":100, "rosters":10, "retry":20, "flash":20, "stats":100}
BLOCKS = ("stats","acts","rosters","retry")
def due(entry, hours, clock):
    try:
        return clock - datetime.fromisoformat(entry["checkedAt"]) >= timedelta(hours=hours)
    except (KeyError,TypeError,ValueError):
        return True

def plan_matches(rows, state, captured, phase, clock):
    result=[]
    for key,r in rows.items():
        old=state.get(key,{})
        same=old.get("fingerprint")==r["fingerprint"]
        if same and old.get("status")=="verified" and (phase!="flash" or old.get("statsRevision")==STATS_REVISION):
            continue
        retry=same and old.get("status")=="pending"
        if phase=="retry":
            if not retry or not due(old,6,clock):continue
        elif phase=="flash":
            if r["iso"] < (clock.date()-timedelta(days=7)).isoformat():continue
            if retry and not due(old,0.25,clock):continue
        elif retry:
            continue
        result.append((key,r))
    # Recent fixtures first, newest first; historical work keeps its resumable order.
    cutoff=(clock.date()-timedelta(days=7)).isoformat()
    recent=sorted((x for x in result if x[1]["iso"]>=cutoff),key=lambda x:(x[1]["iso"],x[0]),reverse=True)
    historical=sorted((x for x in result if x[1]["iso"]<cutoff),key=lambda x:(x[0] in captured,state.get(x[0],{}).get("checkedAt",""),x[1]["iso"],x[0]))
    return (recent+historical)[:LIMITS[phase]]

def plan_stats(rows, state, captured, clock):
    """Recheck existing appearances once with the new FECAPA stat reader.
    Keep existing facts and honour retry backoff; prioritize the regression case.
    """
    pending=[]
    for key,r in rows.items():
        if key not in captured:
            continue
        old=state.get(key,{})
        if old.get("statsRevision")==STATS_REVISION and old.get("status")=="verified" and old.get("fingerprint")==r["fingerprint"]:
            continue
        if old.get("status")=="pending" and old.get("fingerprint")==r["fingerprint"] and old.get("statsAttemptRevision")==STATS_REVISION and not due(old,6,clock):
            continue
        pending.append((key,r))
    cutoff=(clock.date()-timedelta(days=7)).isoformat()
    recent=sorted((x for x in pending if x[1]["iso"]>=cutoff),key=lambda x:(x[1]["iso"],x[0]),reverse=True)
    historical=sorted((x for x in pending if x[1]["iso"]<cutoff),key=lambda x:(x[0]!="4786|152375",state.get(x[0],{}).get("checkedAt",""),x[1]["iso"],x[0]))
    return (recent+historical)[:LIMITS["stats"]]

def plan_rosters(leagues,state,represented,clock):
    pending=[]
    for league in leagues:
        old=state.get(league,{})
        if old.get("status")=="verified" and not due(old,168,clock):continue
        if old.get("status")=="pending" and not due(old,6,clock):continue
        pending.append(league)
    return sorted(pending,key=lambda l:(l in represented,state.get(l,{}).get("checkedAt",""),int(l)))[:LIMITS["rosters"]]

async def run_matches(master,state,plan,deadline,report):
    if not plan:return
    old_by_match={}
    for k,v in master["matchAppearances"].items():
        old_by_match.setdefault(v["leagueId"]+"|"+v["matchId"],set()).add(k)
    async with async_playwright() as pw:
        browser,ctx=await chromium_context(pw)
        try:
            for key,r in plan:
                if time.monotonic()>=deadline:break
                l,m=r["leagueId"],r["matchId"]
                details={}
                try:
                    summary,official,error=await asyncio.wait_for(closed_acta(ctx,l,m,details),timeout=max(1,min(120,deadline-time.monotonic())))
                except asyncio.TimeoutError:
                    error="timeout"
                if error in ("http_403","http_429","http_503"):
                    report["blocked"]=True
                    break
                if not error:
                    candidate=empty("41")
                    result=ingest_appearances(candidate,l,m,summary,official,now())
                    if not result["stored"] or result["stored"]!=len(summary) or result["officialMatched"]!=len(summary) or result["conflicts"] or not old_by_match.get(key,set())<=set(candidate["matchAppearances"]):
                        error="incomplete_or_changed_roster"
                    else:
                        verify_master(candidate)
                        merge_verified(master,candidate)
                previous=state.get(key,{})
                state[key]={"status":"pending" if error else "verified","fingerprint":r["fingerprint"],"checkedAt":now(),"statsAttemptRevision":STATS_REVISION}
                if previous.get("details"):
                    state[key]["details"]=previous["details"]
                if not error and details.get("source")=="FECAPA":
                    old=state[key].get("details",{})
                    state[key]["details"]={**old,**details,"source":"FECAPA",
                        "fouls":{**old.get("fouls",{}),**details.get("fouls",{})},
                        "teamStats":{**old.get("teamStats",{}),**details.get("teamStats",{})},
                        "header":{**old.get("header",{}),**details.get("header",{})},
                        "staff":{side:details.get("staff",{}).get(side) or old.get("staff",{}).get(side,[]) for side in ("home","away")},
                        "periods":details.get("periods") or old.get("periods",[])}
                if not error:state[key]["statsRevision"]=STATS_REVISION
                report["attempted"]+=1
                report["pending" if error else "verified"]+=1
                if error:report["reasons"][error]=report["reasons"].get(error,0)+1
                if "matchDiagnostics" in report:
                    report["matchDiagnostics"][key]={"status":"pending" if error else "verified",
                        "reason":error or None,"checkedAt":state[key]["checkedAt"],
                        "staffSides":{side:len(state[key].get("details",{}).get("staff",{}).get(side) or [])
                                      for side in ("home","away")}}
                await asyncio.sleep(1.2)
        finally:
            await ctx.close();await browser.close()

async def run_rosters(master,state,plan,deadline,report):
    args=SimpleNamespace(seed=[],only_seed=False,season="41",max_teams=None,inspect_profiles=False,profiles_per_team=1)
    for league in plan:
        if time.monotonic()>=deadline:break
        details={"leagues":[],"rosterErrors":[]}
        ok=False
        try:
            await asyncio.wait_for(collect(args,[league],master,details),timeout=max(1,min(240,deadline-time.monotonic())))
            lr=details["leagues"][0]
            ok=bool(lr["teamsSelected"] and lr["teamsObserved"]==lr["teamsSelected"] and not lr["errors"] and not lr.get("conflictingSportsFields"))
        except Exception:
            pass
        state[league]={"status":"verified" if ok else "pending","checkedAt":now()}
        report["attempted"]+=1
        report["verified" if ok else "pending"]+=1

async def run(a):
    root=a.private_dir
    if not root.is_absolute() or not root.is_dir() or root.stat().st_mode&0o077:raise ValueError("private_directory_required")
    target=root/"jugadors-master.json"
    if not target.is_file():raise ValueError("master_required")
    master=load(target,"41");verify_master(master)
    state_path=root/"jugadors-maintenance-state.json"
    state=json.loads(state_path.read_text()) if state_path.exists() else {"matches":{}}
    matches=state.setdefault("matches",{});rosters=state.setdefault("rosters",{})
    if not isinstance(matches,dict) or not isinstance(rosters,dict):raise ValueError("invalid_state")
    rows=candidates(a.catalog)
    inventory,leagues,errors=read_catalog(a.catalog)
    clock=datetime.now(timezone.utc)
    captured={v["leagueId"]+"|"+v["matchId"] for v in master["matchAppearances"].values()}
    represented={v["leagueId"] for v in master["memberships"].values()}
    plans={p:plan_matches(rows,matches,captured,p,clock) for p in ("acts","retry","flash")}
    plans["rosters"]=plan_rosters(leagues,rosters,represented,clock)
    plans["stats"]=plan_stats(rows,matches,captured,clock)
    # One bounded block per execution. Rotate historical acts, rosters and
    # retries so failures cannot starve other work. FLASH is separately selectable.
    phase=a.mode
    if phase=="auto":
        cursor=int(state.get("blockCursor",0))%len(BLOCKS)
        ordered=[BLOCKS[(cursor+i)%len(BLOCKS)] for i in range(len(BLOCKS))]
        phase=next((p for p in ordered if plans[p]),None)
    if not phase or not plans[phase]:
        return {"mode":a.mode,"selected":0,"noChanges":True,"eligibleActs":len(rows),"inventoryActs":len(inventory),"inventoryLeagues":len(leagues),"catalogErrors":len(errors)}
    report={"mode":phase,"selected":len(plans[phase]),"attempted":0,"verified":0,"pending":0,"reasons":{}}
    deadline=time.monotonic()+a.budget_minutes*60
    if phase=="rosters":await run_rosters(master,rosters,plans[phase],deadline,report)
    else:await run_matches(master,matches,plans[phase],deadline,report)
    if phase in BLOCKS:state["blockCursor"]=(BLOCKS.index(phase)+1)%len(BLOCKS)
    enrich_names(master,a.catalog);link_memberships(master)
    master.update(updatedAt=now(),coverageVerified=False)
    verify_master(master);save(target,master)
    if load(target,"41")!=master:raise ValueError("roundtrip_mismatch")
    save(state_path,state)
    report.update(statsRevision=STATS_REVISION,statCoverage={k:sum(k in v.get("stats",{}) for v in master["matchAppearances"].values()) for k in ("goals","assists","yellowCards","blueCards","redCards")},statsRemaining=len([k for k in captured if k in rows and matches.get(k,{}).get("statsRevision")!=STATS_REVISION]),players=len(master["players"]),memberships=len(master["memberships"]),appearances=len(master["matchAppearances"]),unprocessed=report["selected"]-report["attempted"],eligibleActs=len(rows),inventoryActs=len(inventory),inventoryLeagues=len(leagues),catalogErrors=len(errors),verifiedActs=sum(v.get("status")=="verified" and v.get("fingerprint")==rows[k]["fingerprint"] for k,v in matches.items() if k in rows),verifiedLeagues=sum(v.get("status")=="verified" for k,v in rosters.items() if k in leagues))
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",type=Path,required=True)
    p.add_argument("--private-dir",type=Path,required=True)
    p.add_argument("--mode",choices=["auto",*LIMITS],default="auto")
    p.add_argument("--budget-minutes",type=int,default=20)
    a=p.parse_args()
    if not 1<=a.budget_minutes<=30:p.error("invalid_budget")
    try:
        report=asyncio.run(run(a));print(json.dumps(report),flush=True)
        return 0
    except Exception as e:
        print(json.dumps({"fatalError":type(e).__name__}),flush=True);return 2

if __name__=="__main__":raise SystemExit(main())
