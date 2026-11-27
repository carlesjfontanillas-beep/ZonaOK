#!/usr/bin/env python3
"""One-shot FECAPA Agenda schedule audit; only existing fixture iso/time may change."""
import asyncio, copy, json, os, sys
from collections import defaultdict, Counter
from pathlib import Path
from playwright.async_api import async_playwright
from zonaok_fecapa_unificat import (AGENDA_URL, CANONICAL, JS_AGENDA, chromium_context,
    page_ready, next_page, load_unified, norm, check_iso, check_time, score_tuple,
    utc_now, write_compatibility, ROOT, JS_CALENDAR, verified_league_rows, clean)
START, END = "2026-11-01", "2026-12-31"
REPORT=Path("imports/agenda-revisio-20261101-1231.json")

def inside(r):
    return START<=str(r.get("iso",""))<=END

def identity(r):
    return tuple(norm(r.get(k)) for k in ("competition","home","away"))

def when(r):
    return (r.get("iso"),r.get("time"))

def matchid(r):
    return (clean(r.get("leagueId")),clean(r.get("matchId")))

def describe(r):
    return {k:r.get(k) for k in ("iso","time","competition","home","away","leagueId","matchId")}

def score_compatible(a,b):
    # A published result must not be reassigned to another fixture.
    if score_tuple(a):
        return score_tuple(b) and (a["homeScore"],a["awayScore"])==(b["homeScore"],b["awayScore"])
    return True

def write(path,doc):
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

async def capture(ctx,report,old):
    page=await ctx.new_page()
    rows={}
    try:
        res=await page.goto(AGENDA_URL,wait_until="domcontentloaded",timeout=60000)
        if res and res.status>=400:raise RuntimeError(f"FECAPA HTTP {res.status}")
        await page.wait_for_selector("table",timeout=30000)
        # Explicitly select the entire season so that moved fixtures can be
        # recognized even when they cross the requested date boundaries.
        selected=False
        for select in await page.locator("select").all():
            options=await select.evaluate("s=>[...s.options].map(o=>({value:o.value,text:o.textContent}))")
            choices=[o for o in options if norm(o["text"]) in ("TOTA LA TEMPORADA","TODA LA TEMPORADA","ALL SEASON")]
            if len(choices)==1:
                await select.select_option(value=choices[0]["value"])
                report["seasonFilter"]=choices[0]["text"].strip()
                selected=True
                break
        if not selected:raise RuntimeError("No s'ha pogut verificar el selector Tota la Temporada")
        await page.wait_for_timeout(6000)
        seen=set()
        for index in range(100):
            data=await page.evaluate(JS_AGENDA)
            page_rows=data.get("rows",[])
            sig=(len(page_rows),tuple((identity(r),when(r)) for r in page_rows[:3]))
            if sig in seen:raise RuntimeError("Paginació repetida; captura no fiable")
            seen.add(sig)
            for r in page_rows:
                key=(identity(r),when(r))
                if all(key[0]) and check_iso(r.get("iso")) and check_time(r.get("time")):
                    previous=rows.get(key)
                    if previous is not None and score_tuple(previous) and score_tuple(r) and not score_compatible(previous,r):
                        raise RuntimeError("Resultats contradictoris a la captura")
                    if previous is None or (not score_tuple(previous) and score_tuple(r)):rows[key]=r
            if not await next_page(page):break
        else:raise RuntimeError("Límit de paginació assolit")
        incoming=list(rows.values())
        report["sourceRowsSeason"]=len(incoming)
        report["sourceRowsWindow"]=sum(inside(r) for r in incoming)
        report["sourcePages"]=len(seen)
        # Fail closed if FECAPA returned a partial / empty listing.
        if len(incoming)<0.80*len(old) or report["sourceRowsWindow"]<0.80*sum(inside(r) for r in old):
            raise RuntimeError("Cobertura Agenda insuficient; no es publiquen canvis")
        return incoming
    finally:
        await page.close()

def propose(old,incoming):
    old_groups=defaultdict(list); new_groups=defaultdict(list)
    for i,r in enumerate(old):old_groups[identity(r)].append((i,r))
    for r in incoming:new_groups[identity(r)].append(r)
    proposals=[]; unresolved=[]; unchanged=0; matched=set()
    for key, originals in old_groups.items():
        fresh=new_groups.get(key,[])
        before=[]; after=list(fresh)
        # First consume identical schedules across the whole season.
        for i,r in originals:
            same=[j for j,x in enumerate(after) if when(x)==when(r)]
            if len(same)==1:
                after.pop(same[0]);matched.add(i)
                if inside(r):unchanged+=1
            else:before.append((i,r))
        if not before:continue
        if len(before)==1 and len(after)==1:
            i,r=before[0]; n=after[0]
            if not (inside(r) or inside(n)):continue
            if when(r)==when(n):continue
            if score_compatible(r,n):
                proposals.append((i,n)); continue
        for i,r in before:
            if inside(r) or any(inside(n) for n in after):
                unresolved.append((i, "Identitat o marcador no inequívoc", [when(n) for n in after]))
    return proposals,unresolved,unchanged

async def calendar_check(ctx, old, proposals, report):
    # /ag/ has no official IDP. Verify the proposed changes against the
    # official competition calendar whenever the fixture already has IDs.
    by_league=defaultdict(list)
    accepted=[]; rejected=[]
    for i,n in proposals:
        lid,mid=matchid(old[i])
        if lid and mid:by_league[lid].append((i,n))
        else:accepted.append((i,n,"Agenda: competició i equips inequívocs"))
    page=await ctx.new_page()
    try:
        for lid,group in sorted(by_league.items()):
            official=defaultdict(list)
            try:
                res=await page.goto(ROOT+f"?liga={lid}&vista=calendar",wait_until="domcontentloaded",timeout=35000)
                if res and res.status>=400:raise RuntimeError(f"HTTP {res.status}")
                await page.wait_for_selector("tr.sidgad-calendario-partido:visible",timeout=18000)
                data=await page.evaluate(JS_CALENDAR,lid)
                rows,meta=verified_league_rows(lid,data["rows"],[])
                for row in rows:official[matchid(row)].append(row)
                report.setdefault("leagueChecks",[]).append({"leagueId":lid,"status":meta["status"],"rows":len(rows)})
            except Exception as e:
                report.setdefault("leagueChecks",[]).append({"leagueId":lid,"error":type(e).__name__})
            for i,n in group:
                candidates=official.get(matchid(old[i]),[])
                slots={when(x) for x in candidates}
                if slots=={when(n)}:
                    accepted.append((i,n,"Agenda + IDP oficial"))
                else:
                    rejected.append((i,"IDP no confirma la nova data/hora",list(slots)))
    finally:await page.close()
    return accepted,rejected

def apply(old, accepted):
    rows=copy.deepcopy(old); changes=[]
    for i,n,proof in accepted:
        a=old[i]; b=rows[i]
        if not (inside(a) or inside(n)):raise ValueError("outside_window")
        if when(a)==when(n):continue
        b["iso"],b["time"]=when(n)
        changes.append({**describe(a),"newIso":b["iso"],"newTime":b["time"],"proof":proof})
    # Exact per-row invariant: ONLY these two fields may change.
    if len(rows)!=len(old):raise ValueError("count_changed")
    for a,b in zip(old,rows):
        if {k:v for k,v in a.items() if k not in ("iso","time")}!={k:v for k,v in b.items() if k not in ("iso","time")}:
            raise ValueError("non_schedule_field_changed")
    before=Counter((identity(r),when(r)) for r in old)
    after=Counter((identity(r),when(r)) for r in rows)
    if any(n>max(1,before[k]) for k,n in after.items()):raise ValueError("new_duplicate")
    return rows,changes

async def main():
    report={"window":{"from":START,"to":END},"sourceUrl":AGENDA_URL,"runId":os.environ.get("GITHUB_RUN_ID"),
            "startedAt":utc_now(),"status":"error","changes":[],"unresolved":[]}
    try:
        doc=load_unified(CANONICAL)
        old=doc["matches"]
        report["catalogBefore"]=len(old);report["windowBefore"]=sum(inside(r) for r in old)
        async with async_playwright() as pw:
            browser,ctx=await chromium_context(pw)
            try:
                incoming=await capture(ctx,report,old)
                proposals,unresolved,unchanged=propose(old,incoming)
                report["unchanged"]=unchanged;report["proposals"]=len(proposals)
                accepted,rejected=await calendar_check(ctx,old,proposals,report)
            finally:await ctx.close();await browser.close()
        rows,changes=apply(old,accepted)
        report["unresolved"]=[{**describe(old[i]),"reason":reason,"possibleSchedules":poss}
                              for i,reason,poss in unresolved+rejected]
        report["changes"]=changes
        report["catalogAfter"]=len(rows);report["windowAfter"]=sum(inside(r) for r in rows)
        report["changed"]=len(changes)
        report["dateChanged"]=sum(c["iso"]!=c["newIso"] for c in changes)
        report["timeChanged"]=sum(c["time"]!=c["newTime"] for c in changes)
        report["status"]="success" if not report["unresolved"] else "partial"
        if changes:
            doc["matches"]=rows;doc["updatedAt"]=utc_now()
            write(CANONICAL,doc);write_compatibility(doc)
        return 0
    except Exception as e:
        report["error"]=type(e).__name__+": "+str(e)
        return 1
    finally:
        report["finishedAt"]=utc_now();write(REPORT,report)
        print(json.dumps({k:v for k,v in report.items() if k not in ("changes","unresolved","leagueChecks")},ensure_ascii=False),flush=True)

if __name__=="__main__":sys.exit(asyncio.run(main()))
