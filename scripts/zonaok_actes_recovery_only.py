#!/usr/bin/env python3
"""Single-writer FECAPA acta recovery: recover official IDs, then closed acta content."""
import asyncio, json, re, time, sys, copy
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
from types import SimpleNamespace
from playwright.async_api import async_playwright
from zonaok_fecapa_unificat import (CANONICAL, ROOT, JS_CALENDAR, league_ids_from_files,
    verified_league_rows, make_match_url, match_index, clean, write_compatibility, local_today,
    score_tuple, utc_now, chromium_context)
from zonaok_jugadors_incremental import candidates
from zonaok_jugadors_blocks import run_matches, STATS_REVISION
from zonaok_jugadors_auto import load, save, verify_master, enrich_names
from zonaok_jugadors_total_master import link_memberships

STATE=Path("imports/actes-recovery-state.json")
def read(p,default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
def write(p,doc):
    p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def ids(r):
    return (clean(r.get("leagueId") or r.get("league")),clean(r.get("matchId") or r.get("id")))
def valid(r):
    return bool(make_match_url(*ids(r)))
def attach(rows,r):
    l,m=ids(r)
    if not make_match_url(l,m):return False
    r={**r,"leagueId":l,"matchId":m}
    i=match_index(rows,r,"agenda")
    if i is None or valid(rows[i]):return False
    if any(ids(x)==(l,m) for x in rows):return False
    rows[i].update(leagueId=l,matchId=m,actaUrl=make_match_url(l,m))
    return True
def historical(r):
    return bool(r.get("iso") and r["iso"]<local_today().isoformat() and not re.search(
        r"ajorn|aplaz|susp|cancel|anul",str(r.get("status","")),re.I))
def summarize(doc):
    rows=doc["matches"]; past=[r for r in rows if historical(r)]
    return dict(total=len(rows),identified=sum(valid(r) for r in rows),
        missingHistoricalIDs=sum(not valid(r) for r in past),
        missingHistoricalScores=sum(not score_tuple(r) for r in past),
        historical=len(past),verified=sum(r.get("actaState")=="available" for r in rows),
        historicalUnverified=sum(r.get("actaState")!="available" for r in past))
def persist(doc, before):
    if len(doc["matches"])!=len(before["matches"]):raise ValueError("fixture_count_changed")
    for a,b in zip(before["matches"],doc["matches"]):
        if any(a.get(k)!=b.get(k) for k in ("iso","time","competition","home","away","homeScore","awayScore")):
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
    for name,key in [("zonaok-actes.json","fixtures"),("zonaok-tots-actes.json","rows")]:
        for raw in read(Path(name),{}).get(key,[]):
            if isinstance(raw,dict):added+=attach(rows,raw)
    pending=[r for r in rows if not valid(r)]
    league_ids=league_ids_from_files()
    known={ids(r)[0] for r in pending if ids(r)[0] in league_ids}
    checks=state.setdefault("leagueChecks",{})
    # Rotate all known calendars, prioritising leagues with unresolved matches.
    selected=sorted(league_ids,key=lambda l:(bool(checks.get(l)),l not in known,checks.get(l,""),int(l)))[:8] if pending else []
    report={"legacyIDs":added,"calendarIDs":0,"checks":[]}
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
                    n=sum(attach(rows,r) for r in accepted)
                    report["calendarIDs"]+=n
                    report["checks"].append({"league":l,"ids":n,"status":meta["status"],"accepted":len(accepted)})
                except Exception as exc:
                    report["checks"].append({"league":l,"error":type(exc).__name__})
                checks[l]=utc_now()
                await asyncio.sleep(1.5)
            await page.close()
        finally:await ctx.close();await browser.close()
    return report
async def acts(doc,root):
    path=root/"jugadors-master.json"; statepath=root/"jugadors-maintenance-state.json"
    master=load(path,"41");verify_master(master)
    state=read(statepath,{"matches":{},"rosters":{}})
    matches=state.setdefault("matches",{})
    rows=candidates(Path("."))
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
    pending=[(k,r) for k,r in rows.items() if not verified(k,r)]
    clock=datetime.now(timezone.utc)
    def due(k):
        try:return clock-datetime.fromisoformat(matches.get(k,{}).get("checkedAt",""))>=timedelta(hours=2)
        except (ValueError,TypeError):return True
    plan=sorted((x for x in pending if due(x[0])),key=lambda x:(matches.get(x[0],{}).get("checkedAt",""),x[1]["iso"],x[0]))[:40]
    report={"selected":len(plan),"attempted":0,"verified":0,"pending":0,"reasons":{},"reusedVerified":promoted}
    await run_matches(master,matches,plan,time.monotonic()+15*60,report)
    for k,r in plan:
        if verified(k,r) and k in byid:promote(k)
    # A change in the acta availability field alone must not trigger another scrape.
    write(CANONICAL,doc)
    fresh=candidates(Path("."))
    for k,r in fresh.items():
        if k in rows and verified(k,rows[k]):
            matches[k]["fingerprint"]=r["fingerprint"]
    enrich_names(master,Path("."));link_memberships(master)
    verify_master(master);save(path,master);save(statepath,state)
    report["remainingEligible"]=sum(not verified(k,r) for k,r in fresh.items())
    report["players"]=len(master["players"]);report["appearances"]=len(master["matchAppearances"])
    return report
async def main():
    phase=sys.argv[1]; doc=read(CANONICAL,{});before=copy.deepcopy(doc)
    control=read(STATE,{})
    initial=summarize(doc)
    if phase=="ids":report=await discover(doc,control)
    elif phase=="acts":report=await acts(doc,Path(sys.argv[2]))
    else:raise ValueError("unknown_phase")
    persist(doc,before)
    report={"phase":phase,"before":initial,"after":summarize(doc),**report}
    control["last"+phase.title()]=report
    write(STATE,control);print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":asyncio.run(main())
