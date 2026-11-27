#!/usr/bin/env python3
"""One-shot FECAPA Agenda schedule audit; only existing fixture iso/time may change."""
import asyncio, copy, hashlib, json, os, re, sys
from collections import defaultdict, Counter
from pathlib import Path
from playwright.async_api import async_playwright
from zonaok_fecapa_unificat import (AGENDA_URL, CANONICAL, JS_AGENDA, chromium_context,
    page_ready, next_page, load_unified, norm, check_iso, check_time, score_tuple,
    utc_now, write_compatibility, ROOT, JS_CALENDAR, verified_league_rows, clean)
START, END = "2026-11-01", "2026-12-31"
REPORT=Path("imports/agenda-revisio-20261101-1231.json")
SCRIPT_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def inside(r):
    return START<=str(r.get("iso",""))<=END

def identity(r):
    return tuple(norm(r.get(k)) for k in ("competition","home","away"))

def when(r):
    return (r.get("iso"),r.get("time"))

def matchid(r):
    return (clean(r.get("leagueId")),clean(r.get("matchId")))

def describe(r):
    has_result=score_tuple(r)
    result=f"{r.get('homeScore')}-{r.get('awayScore')}" if has_result else None
    return {**{k:r.get(k) for k in ("iso","time","competition","home","away","leagueId","matchId")},
            "hasResult":has_result,"result":result}

def logo_identity(r, side):
    value=clean(r.get(side+"Logo"))
    match=re.search(r"/logos_clubes/(\d+(?:_\d+)?)\.(?:png|gif)(?:[?#]|$)",value,re.I)
    return match.group(1) if match else ""

def same_team(a,b,side):
    left,right=norm(a.get(side)),norm(b.get(side))
    if left and left==right:return True
    left_logo,right_logo=logo_identity(a,side),logo_identity(b,side)
    return bool(left_logo and left_logo==right_logo)

def same_teams(a,b):
    return same_team(a,b,"home") and same_team(a,b,"away")

def same_calendar_fixture(old, official):
    # Alguns registres antics tenen la pista al camp away per una captura
    # desplaçada. Només recuperem aquests casos si local i pista coincideixen
    # exactament dins el calendari IDP de la competició.
    if same_teams(old, official):
        return True
    away=clean(old.get("away"))
    venue=clean(official.get("venue"))
    if not away or not venue or not same_team(old, official, "home"):
        return False
    venue_like=bool(re.match(
        r"^(?:PAVELL|PABELL|POLIESPORT|POLIDEPORT|PISTA|POLIESPORTIU|"
        r"POLIDEPORTIVO|PAVILLO|PAVELLON)\b", norm(away)))
    return venue_like and norm(away)==norm(venue)

def league_ids_by_competition():
    path=Path("zonaok-classificacions.json")
    if not path.exists():return {}
    try:doc=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}
    result=defaultdict(set)
    for item in doc.get("competitions",{}).values():
        if not isinstance(item,dict):continue
        lid=clean(item.get("leagueId"))
        if not re.fullmatch(r"\d{4,6}",lid):continue
        for key in ("competition","category","name"):
            label=norm(item.get(key))
            if label:result[label].add(lid)
    return {key:sorted(ids,key=int) for key,ids in result.items()}

def score_compatible(a,b):
    # An empty Agenda score is not evidence against the same fixture. Conflicting
    # published scores remain a hard stop.
    sa,sb=score_tuple(a),score_tuple(b)
    return not (sa and sb) or (a["homeScore"],a["awayScore"])==(b["homeScore"],b["awayScore"])

def schedule_keys(r):
    names=(norm(r.get("home")),norm(r.get("away")))
    keys=[]
    if all(names):keys.append(("teams",*names))
    logos=(logo_identity(r,"home"),logo_identity(r,"away"))
    if all(logos):keys.append(("logos",*logos))
    return keys

def propose(old,incoming):
    # Match the entire season, then edit only fixtures whose old or new date is
    # in scope. The general Agenda has no IDP, so use an ordered team pair as
    # the stable key and the competition label only as a tie-breaker.
    old_schedule=defaultdict(list);new_schedule=defaultdict(list)
    for i,r in enumerate(old):old_schedule[(identity(r),when(r))].append(i)
    for j,r in enumerate(incoming):new_schedule[(identity(r),when(r))].append(j)
    used_old=set();used_new=set();unchanged=0
    for key,olds in old_schedule.items():
        news=new_schedule.get(key,[])
        if len(olds)==len(news)==1 and score_compatible(old[olds[0]],incoming[news[0]]):
            i,j=olds[0],news[0];used_old.add(i);used_new.add(j)
            if inside(old[i]):unchanged+=1

    new_index=defaultdict(set)
    for j,r in enumerate(incoming):
        if j in used_new:continue
        for key in schedule_keys(r):new_index[key].add(j)

    candidate_map={}
    for i,r in enumerate(old):
        if i in used_old:continue
        candidates=set()
        for key in schedule_keys(r):candidates.update(new_index.get(key,set()))
        # Prefer the same competition when teams appear in more than one
        # competition; allow a changed competition label only if unique.
        compatible={j for j in candidates if score_compatible(r,incoming[j])}
        same_comp={j for j in compatible if norm(incoming[j].get("competition"))==norm(r.get("competition"))}
        if same_comp:compatible=same_comp
        candidate_map[i]=compatible
    reverse=defaultdict(set)
    for i,candidates in candidate_map.items():
        for j in candidates:reverse[j].add(i)

    proposals=[];unresolved=[]
    for i,r in enumerate(old):
        if i in used_old:continue
        candidates=candidate_map.get(i,set())
        related=inside(r) or any(inside(incoming[j]) for j in candidates)
        if not related:continue
        if len(candidates)==1:
            j=next(iter(candidates))
            if len(reverse[j])==1:
                if when(r)==when(incoming[j]):
                    if inside(r):unchanged+=1
                else:
                    proposals.append((i,incoming[j]))
                continue
        # Include same-team matches that failed score validation so conflicts
        # are visible instead of silently looking like a missing fixture.
        team_candidates=set()
        for key in schedule_keys(r):team_candidates.update(new_index.get(key,set()))
        if len(candidates)>1 or any(len(reverse[j])>1 for j in candidates):
            reason="Més d'una correspondència possible"
            possible=[when(incoming[j]) for j in sorted(candidates)]
        elif team_candidates and not candidates:
            reason="Marcador oficial contradictori"
            possible=[when(incoming[j]) for j in sorted(team_candidates)]
        else:
            reason="No s'ha trobat una correspondència inequívoca a l'Agenda oficial"
            possible=[]
        unresolved.append((i,reason,possible))
    return proposals,unresolved,unchanged

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

async def calendar_check(ctx, old, proposals, unresolved, report, extra_candidates=()):
    # Use the official competition catalogue to recover a calendar IDP even
    # when a fixture row has no reliable leagueId or matchId.
    comp_ids=league_ids_by_competition()
    report["competitionMappings"]=len(comp_ids)
    work=defaultdict(list);accepted=[];rejected=[]
    def target_leagues(row):
        mapped=comp_ids.get(norm(row.get("competition")),[])
        lid,mid=matchid(row)
        if mapped:return mapped
        return [lid] if lid else []
    for i,n in proposals:
        lids=target_leagues(old[i])
        if lids:
            for lid in lids:work[lid].append(("proposal",i,n))
        else:accepted.append((i,n,"Agenda oficial: parella d'equips inequívoca"))
    unresolved_without_league=[]
    for item in unresolved:
        i,reason,possible=item
        lids=target_leagues(old[i])
        if lids:
            for lid in lids:work[lid].append(("unresolved",i,item))
        else:unresolved_without_league.append(item)
    # Prioritza els partits sense resultat, sense IDP i amb data ja passada:
    # Agenda pot conservar la data antiga, així que cal consultar l'IDP encara
    # que la comparació d'Agenda indiqui la mateixa data.
    for i in extra_candidates:
        item=(i,"Partit sense resultat, sense IDP i amb data anterior a avui",[])
        lids=target_leagues(old[i])
        if lids:
            for lid in lids:work[lid].append(("heuristic",i,item))
        else:
            unresolved_without_league.append(item)

    resolved=set();calendar_unchanged=0
    page=await ctx.new_page()
    try:
        for lid,items in sorted(work.items(),key=lambda pair:int(pair[0])):
            official=defaultdict(list)
            error=""
            try:
                res=await page.goto(ROOT+f"?liga={lid}&vista=calendar",wait_until="domcontentloaded",timeout=35000)
                if res and res.status>=400:raise RuntimeError(f"HTTP {res.status}")
                await page.wait_for_selector("tr.sidgad-calendario-partido:visible",timeout=18000)
                data=await page.evaluate(JS_CALENDAR,lid)
                # La vista calendar?liga=IDP és el calendari oficial de la competició.
                # verified_league_rows exigeix leagueId i matchId a cada fila; molts
                # partits reprogramats sense resultat no porten aquests atributs al DOM.
                # Per a una revisió de data/hora n'hi ha prou amb validar la fila visible,
                # els equips, la data i l'hora, i fer després una correspondència inequívoca.
                rows=[row for row in data.get("rows",[])
                      if isinstance(row,dict)
                      and clean(row.get("home")) and clean(row.get("away"))
                      and check_iso(row.get("iso")) and check_time(row.get("time"))]
                for row in rows:official[matchid(row)].append(row)
                report.setdefault("leagueChecks",[]).append({
                    "leagueId":lid,"status":"official-calendar-rows",
                    "rows":len(rows),"rowsWithIDs":sum(bool(matchid(row)[1]) for row in rows),
                    "rowsWithoutIDs":sum(not bool(matchid(row)[1]) for row in rows)})
            except Exception as exc:
                error=type(exc).__name__
                report.setdefault("leagueChecks",[]).append({"leagueId":lid,"error":error})

            for kind,i,payload in items:
                old_row=old[i];old_lid,old_mid=matchid(old_row)
                if error:
                    if kind=="proposal":
                        rejected.append((i,"No s'ha pogut consultar el calendari oficial IDP",[]))
                    else:unresolved_without_league.append(payload)
                    continue
                if old_mid:
                    candidates=[r for group in official.values() for r in group
                                if matchid(r)[1]==old_mid]
                else:
                    candidates=[r for group in official.values() for r in group if same_calendar_fixture(old_row,r)]
                    same_comp=[r for r in candidates if norm(r.get("competition"))==norm(old_row.get("competition"))]
                    if same_comp:candidates=same_comp
                if len(candidates)!=1:
                    slots=[when(r) for r in candidates]
                    if kind=="unresolved" and not candidates and not score_tuple(old_row):
                        target_tokens=set(norm(old_row.get("home")).split())
                        pool=[r for group in official.values() for r in group]
                        related=[]
                        for row in pool:
                            tokens=set(norm(row.get("home")).split())
                            overlap=len(target_tokens & tokens)
                            if overlap and overlap / max(1,min(len(target_tokens),len(tokens))) >= 0.5:
                                related.append(row)
                        report.setdefault("calendarCandidateDiagnostics",[]).append({
                            **describe(old_row),
                            "sameHomeCalendarRows":[
                                {k:r.get(k) for k in ("iso","time","home","away","venue","homeLogo","awayLogo")}
                                for r in related[:6]]})
                    if kind=="proposal":
                        rejected.append((i,"El calendari oficial IDP no dona una única correspondència",slots))
                    else:
                        unresolved_without_league.append((i,"Calendari IDP sense correspondència única",slots))
                    continue
                official_row=candidates[0]
                if not score_compatible(old_row,official_row):
                    if kind=="proposal":
                        rejected.append((i,"Marcador de l'IDP contradictori",[when(official_row)]))
                    else:
                        unresolved_without_league.append((i,"Marcador de l'IDP contradictori",[when(official_row)]))
                    continue
                if kind=="proposal":
                    n=payload
                    if when(official_row)==when(n):
                        accepted.append((i,n,"Agenda i calendari oficial IDP"))
                    else:
                        rejected.append((i,"IDP no confirma la data/hora de l'Agenda",[when(official_row)]))
                else:
                    if when(old_row)==when(official_row):
                        if kind=="heuristic":
                            resolved.add(i);calendar_unchanged+=1
                        else:
                            resolved.add(i);calendar_unchanged+=1
                    else:
                        accepted.append((i,official_row,"Calendari oficial FECAPA per IDP"))
                        resolved.add(i)
    finally:
        await page.close()

    unresolved_left=[item for item in unresolved_without_league if item[0] not in resolved]
    return accepted,rejected,unresolved_left,calendar_unchanged

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
            "reviewScriptSha":SCRIPT_SHA,
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
                today=utc_now()[:10]
                extra_candidates=[i for i,row in enumerate(old)
                                  if inside(row) and str(row.get("iso",""))<today
                                  and not score_tuple(row) and not matchid(row)[0]]
                report["scorelessPastWithoutIDP"]=len(extra_candidates)
                accepted,rejected,unresolved,calendar_unchanged=await calendar_check(
                    ctx,old,proposals,unresolved,report,extra_candidates)
                unchanged+=calendar_unchanged;report["unchanged"]=unchanged
            finally:await ctx.close();await browser.close()
        rows,changes=apply(old,accepted)
        report["unresolved"]=[{**describe(old[i]),"reason":reason,"possibleSchedules":poss}
                              for i,reason,poss in unresolved+rejected]
        report["unresolvedWithoutResult"]=[item for item in report["unresolved"] if not item["hasResult"]]
        report["unresolvedWithoutResultCount"]=len(report["unresolvedWithoutResult"])
        report["unresolvedWithResultCount"]=len(report["unresolved"])-report["unresolvedWithoutResultCount"]
        report["changes"]=changes
        report["changesWithoutResult"]=[item for item in changes if not item.get("hasResult")]
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
