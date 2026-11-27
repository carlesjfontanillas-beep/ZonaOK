#!/usr/bin/env python3
"""Single-writer FECAPA acta recovery: recover official IDs, then closed acta content."""
import asyncio, json, re, time, sys, copy, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from types import SimpleNamespace
from playwright.async_api import async_playwright
from zonaok_fecapa_unificat import (CANONICAL, ROOT, JS_CALENDAR, league_ids_from_files,
    verified_league_rows, make_match_url, match_index, clean, write_compatibility, local_today,
    score_tuple, utc_now, chromium_context)
from zonaok_jugadors_incremental import candidates, norm
from zonaok_jugadors_blocks import run_matches, STATS_REVISION
from zonaok_jugadors_auto import load, save, verify_master, enrich_names
from zonaok_jugadors_total_master import link_memberships

# Keep each historical interval's audit cursor and summary independent.
WINDOWS={
    "recent":("2026-11-12","2026-11-26","imports/actes-recovery-state.json"),
    "early":("2026-11-01","2026-11-12","imports/actes-recovery-20261101-12.json"),
}
WINDOW_NAME=os.environ.get("ZONAOK_ACTES_WINDOW","recent")
if WINDOW_NAME not in WINDOWS:raise ValueError("invalid_recovery_window")
START, END, state_file=WINDOWS[WINDOW_NAME]
STATE=Path(state_file)
WINDOW = START+"|"+END
def read(p,default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
def write(p,doc):
    p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def ids(r):
    return (clean(r.get("leagueId") or r.get("league")),clean(r.get("matchId") or r.get("id")))
def valid(r):
    return bool(make_match_url(*ids(r)))
def url_ids(row):
    u=urlparse(str(row.get("actaUrl") or ""))
    if u.scheme!="https" or u.hostname not in {"www.hoqueipatins.fecapa.cat","hoqueipatins.fecapa.cat"}:return None
    q=parse_qs(u.query)
    l,m=q.get("liga",[]),q.get("partido",[])
    if len(l)==len(m)==1 and make_match_url(l[0],m[0]):return l[0],m[0]
    return None
def attach(rows,r):
    l,m=ids(r)
    if not make_match_url(l,m):return False
    r={**r,"leagueId":l,"matchId":m}
    i=match_index(rows,r,"agenda")
    if i is None or not requires_acta(rows[i]) or valid(rows[i]):return False
    if any(ids(x)==(l,m) for x in rows):return False
    rows[i].update(leagueId=l,matchId=m,actaUrl=make_match_url(l,m))
    return True
def historical(r):
    return bool(r.get("iso") and START<=r["iso"]<=END and not re.search(
        r"ajorn|aplaz|susp|cancel|anul",str(r.get("status","")),re.I))
def state_league(r):
    name=norm(r.get("competition")).replace("-"," ")
    name=" ".join(name.split())
    return name in {"ok liga","ok liga masculina","ok liga plata norte","ok liga plata sur","ok liga iberdrola","ok liga femenina"}

def requires_acta(r):
    return historical(r) and not state_league(r)

def summarize(doc):
    rows=doc["matches"]; window=[r for r in rows if historical(r)]
    past=[r for r in window if requires_acta(r)]
    national=[r for r in window if state_league(r)]
    return dict(window={"from":START,"to":END},total=len(window),catalogTotal=len(rows),identified=sum(valid(r) for r in past),
        actaRequired=len(past),nationalScoreOnly=len(national),nationalWithScore=sum(score_tuple(r) for r in national),nationalMissingScore=sum(not score_tuple(r) for r in national),
        allWindowMissingScores=sum(not score_tuple(r) for r in window),
        missingHistoricalIDs=sum(not valid(r) for r in past),
        missingHistoricalScores=sum(not score_tuple(r) for r in past),
        historical=len(past),verified=sum(r.get("actaState")=="available" for r in past),
        historicalUnverified=sum(r.get("actaState")!="available" for r in past),
        pendingWithID=sum(valid(r) and r.get("actaState")!="available" for r in past))
def persist(doc, before):
    if len(doc["matches"])!=len(before["matches"]):raise ValueError("fixture_count_changed")
    for a,b in zip(before["matches"],doc["matches"]):
        if not requires_acta(a) and a!=b:raise ValueError("outside_acta_scope_changed")
        if any(a.get(k)!=b.get(k) for k in ("iso","time","competition","home","away")) or (score_tuple(a) and (a.get("homeScore"),a.get("awayScore"))!=(b.get("homeScore"),b.get("awayScore"))):
            raise ValueError("fixture_or_score_changed")
        if valid(a) and ids(a)!=ids(b):raise ValueError("existing_id_changed")
        if a.get("actaState")=="available" and b.get("actaState")!="available":raise ValueError("verified_acta_lost")
    doc["updatedAt"]=utc_now()
    doc["stats"]={**doc.get("stats",{}),"total":len(doc["matches"]),
        "withScores":sum(bool(score_tuple(x)) for x in doc["matches"]),
        "withActaLinks":sum(bool(x.get("actaUrl")) for x in doc["matches"]),
        "verifiedActes":sum(x.get("actaState")=="available" for x in doc["matches"])}
    write(CANONICAL,doc);write_compatibility(doc)
async def discover(doc,state):
    rows=doc["matches"]; added=0
    for r in rows:
        if not requires_acta(r):continue
        if valid(r):
            if not r.get("actaUrl"):r["actaUrl"]=make_match_url(*ids(r))
            continue
        pair=url_ids(r)
        if pair and all(not old or old==new for old,new in zip(ids(r),pair)) and not any(ids(x)==pair for x in rows):
            r.update(leagueId=pair[0],matchId=pair[1]);added+=1
    for name,key in [("zonaok-actes.json","fixtures"),("zonaok-tots-actes.json","rows")]:
        for raw in read(Path(name),{}).get(key,[]):
            if not isinstance(raw,dict):continue
            raw=dict(raw)
            if isinstance(raw.get("key"),str):
                parts=raw["key"].split("|")
                if len(parts)==5:raw.update(zip(("iso","time","competition","home","away"),parts))
            if requires_acta(raw):added+=attach(rows,raw)
    pending=[r for r in rows if requires_acta(r) and not valid(r)]
    league_ids=league_ids_from_files()
    # Every unresolved fixture remains eligible on every run. No time-based
    # exclusion. Use known competition-to-league links to prioritise, and
    # oldest-attempt-first rotation so a failing league cannot starve others.
    by_comp={}
    for r in rows:
        l=ids(r)[0]
        if valid(r) and l in league_ids:
            by_comp.setdefault(norm(r.get("competition")),set()).add(l)
    priority={}
    for r in pending:
        related=set(by_comp.get(norm(r.get("competition")),set()))
        if ids(r)[0] in league_ids:related.add(ids(r)[0])
        for l in related:priority[l]=priority.get(l,0)+1
    checks=state.setdefault("windowLeagueChecks",{})
    selected=sorted(league_ids,key=lambda l:(checks.get(l,""),-priority.get(l,0),int(l)))[:8] if pending else []
    report={"legacyIDs":added,"calendarIDs":0,"checks":[],"untriedLeagues":sum(l not in checks for l in league_ids) if pending else 0}
    if not selected:return report
    async with async_playwright() as pw:
        browser,ctx=await chromium_context(pw)
        try:
            page=await ctx.new_page()
            for l in selected:
                try:
                    res=await page.goto(ROOT+f"?liga={l}&vista=calendar",wait_until="domcontentloaded",timeout=35000)
                    if res and res.status in (403,429,503):
                        report["blocked"]=res.status;break
                    await page.wait_for_selector("tr.sidgad-calendario-partido:visible",timeout=22000)
                    data=await page.evaluate(JS_CALENDAR,l)
                    accepted,meta=verified_league_rows(l,data["rows"],[])
                    n=sum(attach(rows,r) for r in accepted if requires_acta(r))
                    report["calendarIDs"]+=n
                    report["checks"].append({"league":l,"ids":n,"status":meta["status"],"accepted":len(accepted)})
                except Exception as exc:
                    report["checks"].append({"league":l,"error":type(exc).__name__})
                checks[l]=utc_now()
                await asyncio.sleep(1.5)
            await page.close()
        finally:await ctx.close();await browser.close()
    report["untriedLeagues"]=sum(l not in checks for l in league_ids) if any(requires_acta(r) and not valid(r) for r in rows) else 0
    return report
def all_candidates(doc):
    rows={}
    # Closed official acts can exist even if the cached fixture has no score.
    for r in doc["matches"]:
        if not requires_acta(r) or not valid(r):continue
        l,m=ids(r);key=l+"|"+m
        if key in rows:continue
        rows[key]={"leagueId":l,"matchId":m,"iso":r["iso"],"fingerprint":json.dumps([r.get("homeScore"),r.get("awayScore"),norm(r.get("status")),r.get("actaState"),r.get("actaUrl")],ensure_ascii=False,separators=(",",":"))}
    return rows
def coverage(master,matches,byid):
    fields=("Núm.","P","C","5i","G","As","PEN","FD","F→","F←","TA","TB","TR")  # Cat is retained when available, but is optional for acta completeness.
    appearances={}
    for a in master["matchAppearances"].values():
        k=a["leagueId"]+"|"+a["matchId"]
        if k in byid:appearances.setdefault(k,[]).append(a)
    result={}; counts={f:{"present":0,"missing":0} for f in fields}
    for k,r in byid.items():
        if not requires_acta(r) or r.get("actaState")!="available":continue
        detail=matches.get(k,{}).get("details",{}); people=appearances.get(k,[])
        missing=[]
        for f in fields:
            present=sum(any(f in block for block in (a.get("fecapaFields") or {}).values() if isinstance(block,dict)) for a in people)
            counts[f]["present"]+=present;counts[f]["missing"]+=len(people)-present
            if not people or present<len(people):missing.append("player:"+f)
        for f in ("header","teamStats","periods"):
            if not detail.get(f):missing.append(f)
        if not all(side in detail.get("fouls",{}) for side in ("home","away")):missing.append("fouls")
        # Staff is optional: preserve imported entries, but an absent staff list
        # does not make an otherwise complete official acta incomplete.
        if not score_tuple(r):missing.append("score")
        result[k]=missing
    return result,counts

async def acts(doc,root,control):
    path=root/"jugadors-master.json"; statepath=root/"jugadors-maintenance-state.json"
    master=load(path,"41");verify_master(master)
    state=read(statepath,{"matches":{},"rosters":{}})
    matches=state.setdefault("matches",{})
    rows=all_candidates(doc)
    byid={ "|".join(ids(r)):r for r in doc["matches"] if valid(r)}
    # Previous closed-acta evidence can be reused only with an identical fingerprint.
    def verified(k,r):
        v=matches.get(k,{})
        return v.get("status")=="verified" and v.get("statsRevision")==STATS_REVISION and v.get("fingerprint")==r["fingerprint"]
    def promote(k):
        row=byid[k]; row["actaState"]="available";row["actaUrl"]=make_match_url(*ids(row))
        row["actaCheckedAt"]=matches[k].get("checkedAt") or utc_now()
    promoted=0
    for k,r in rows.items():
        if k in byid and verified(k,r) and byid[k].get("actaState")!="available":
            promote(k);promoted+=1
    missing_before,_=coverage(master,matches,byid)
    audits=control.setdefault("windowFieldAudits",{})
    attempts=control.setdefault("windowActAttempts",{})
    # Complete verified acts are final. Incomplete verified acts and acts
    # without verification remain eligible; no cooldown or one-audit cap.
    pending=[(k,r) for k,r in rows.items() if not verified(k,r)]
    audit_pending=[(k,r) for k,r in rows.items() if verified(k,r) and missing_before.get(k)]
    clock=datetime.now(timezone.utc)
    work=pending+audit_pending
    plan=sorted(work,key=lambda x:(attempts.get(x[0],""),-int(x[1]["iso"].replace("-","")),x[0]))[:40]
    audit_keys={k for k,_ in audit_pending}
    report={"selected":len(plan),"attempted":0,"verified":0,"pending":0,"reasons":{},"reusedVerified":promoted,"matchDiagnostics":{}}
    previous_audits={k:copy.deepcopy(matches[k]) for k,_ in plan if k in audit_keys and k in matches}
    await run_matches(master,matches,plan,time.monotonic()+15*60,report)
    control.setdefault("matchDiagnostics",{}).update(report["matchDiagnostics"])
    for k,r in plan:
        if k in matches and str(matches[k].get("checkedAt",""))>=clock.isoformat()[:19]:
            attempts[k]=matches[k]["checkedAt"]
        if verified(k,r) and k in byid:promote(k)
        if k in audit_keys and matches.get(k,{}).get("checkedAt") and str(matches[k]["checkedAt"])>=clock.isoformat()[:19]:
            audits[k]=int(audits.get(k,0))+1
            if k in previous_audits and not verified(k,r):
                matches[k]=previous_audits[k]
                control.setdefault("windowAuditFailures",{})[k]=utc_now()
    # Recover a missing score only from the total in a successfully closed official acta.
    for k,r in rows.items():
        if not verified(k,r) or score_tuple(byid[k]):continue
        totals=[p.get("score","") for p in matches[k].get("details",{}).get("periods",[]) if norm(p.get("period"))=="total"]
        if len(totals)==1:
            value=re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*",totals[0])
            if value and all(byid[k].get(f) in (None,int(value[i])) for i,f in ((1,"homeScore"),(2,"awayScore"))):
                byid[k].update(homeScore=int(value[1]),awayScore=int(value[2]),scoreSource="FECAPA:acta_oficial",scoreUpdatedAt=utc_now())
    # A change in the acta availability field alone must not trigger another scrape.
    write(CANONICAL,doc)
    fresh=all_candidates(doc)
    for k,r in fresh.items():
        if k in rows and verified(k,rows[k]):
            matches[k]["fingerprint"]=r["fingerprint"]
    enrich_names(master,Path("."));link_memberships(master)
    verify_master(master);save(path,master);save(statepath,state)
    report["remainingEligible"]=sum(not verified(k,r) for k,r in fresh.items())
    gaps,field_counts=coverage(master,matches,byid)
    report["coverage"]={"verifiedWithAllTrackedFields":sum(not v for v in gaps.values()),"verifiedWithGaps":sum(bool(v) for v in gaps.values()),"playerFields":field_counts,"optionalPlayerFields":["Cat"],"optionalActaFields":["staff"],"gapCounts":{f:sum(f in v for v in gaps.values()) for f in sorted({f for v in gaps.values() for f in v})},"unconfirmedGapsByMatch":{k:v for k,v in gaps.items() if v}}
    report["remainingAudit"]=sum(bool(v) and k in fresh and verified(k,fresh[k]) for k,v in gaps.items())
    remaining={k for k,r in fresh.items() if not verified(k,r) or gaps.get(k)}
    report["pendingCompleteActs"]=len(remaining)
    diagnostics=control.get("matchDiagnostics",{})
    report["pendingByMatch"]={k:{
        "iso":fresh[k]["iso"],"competition":byid[k].get("competition",""),
        "home":byid[k].get("home",""),"away":byid[k].get("away",""),
        "actaUrl":make_match_url(fresh[k]["leagueId"],fresh[k]["matchId"]),
        "verified":verified(k,fresh[k]),"missingFields":gaps.get(k,[]),
        "lastAttempt":diagnostics.get(k,{})} for k in sorted(remaining)}
    # Chain fresh work or genuine progress immediately. Persistent gaps
    # without progress remain eligible at the next scheduled execution,
    # rather than creating an endless self-dispatch loop.
    unattempted=sum(k not in attempts for k in remaining)
    before_gaps=sum(len(v) for v in missing_before.values())
    after_gaps=sum(len(v) for v in gaps.values())
    progress=len(remaining)<len(work) or (len(remaining)==len(work) and after_gaps<before_gaps)
    report["readyNext"]=len(remaining) if progress else unattempted
    report["players"]=len(master["players"]);report["appearances"]=len(master["matchAppearances"])
    return report
async def main():
    phase=sys.argv[1]; doc=read(CANONICAL,{});before=copy.deepcopy(doc)
    control=read(STATE,{})
    control["window"]={"from":START,"to":END}
    initial=summarize(doc)
    if phase=="ids":report=await discover(doc,control)
    elif phase=="acts":report=await acts(doc,Path(sys.argv[2]),control)
    else:raise ValueError("unknown_phase")
    persist(doc,before)
    report={"phase":phase,"before":initial,"after":summarize(doc),**report}
    control["last"+phase.title()]=report
    if phase=="acts":control["lastActsFinishedAt"]=utc_now()
    write(STATE,control);print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":asyncio.run(main())
