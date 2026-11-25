#!/usr/bin/env python3
"""Player maintenance: read public fixture metadata; update only a private master.
Plan mode never opens FECAPA or reads personal records."""
import argparse,asyncio,collections,json,os,re,time,unicodedata
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from zonaok_jugadors_auto import BASE,collect,empty,enrich_names,load,now,numeric,save,verify_master
from zonaok_jugadors_total_master import read_catalog,stable_rows,link_memberships,all_rosters,official_tab
from zonaok_actes_jugadors_probe import ingest_appearances
from zonaok_fecapa_players import chromium_context
from playwright.async_api import async_playwright

def norm(v):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD",str(v or "")) if not unicodedata.combining(c)).lower().split())

FINAL={"final","finalitzat","finalitzada","finalizado","finalizada","acabat","acabada","terminado","terminada","tancat","tancada","cerrado","cerrada","partit finalitzat","partido finalizado","acta tancada","acta cerrada","finished","completed"}
LIVE=re.compile(r"\b(en joc|en directe|en juego|en curso|playing|live|in progress|ajornat|aplazado|susp[eè]s|suspendido|cancelado|cancel.lat)\b")
def scores(r):
    return all(type(r.get(k)) is int and r[k]>=0 for k in ("homeScore","awayScore"))

def candidates(root,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    d=json.loads((root/"zonaok-tots-partits.json").read_text(encoding="utf-8"))
    if d.get("schema")!="zonaok-partits-total-v1" or not isinstance(d.get("matches"),list):raise ValueError("catalog_invalid")
    out={}
    for r in d["matches"]:
        l,m=str(r.get("leagueId","")),str(r.get("matchId",""))
        iso=r.get("iso","");status=norm(r.get("status"))
        if not numeric(l) or not numeric(m) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",iso or "") or iso>today or LIVE.search(status) or not scores(r):continue
        # A verified available acta plus score is a candidate, not proof of closure.
        if status not in FINAL and r.get("actaState")!="available":
            # Blank statuses are common in the public feed. A past scored
            # fixture is only a candidate; the modal must explicitly confirm closure.
            if iso==today:
                try:
                    kickoff=datetime.fromisoformat(iso+"T"+r.get("time","")).replace(tzinfo=ZoneInfo("Europe/Madrid"))
                    if datetime.now(ZoneInfo("Europe/Madrid"))-kickoff<timedelta(minutes=90):continue
                except (TypeError,ValueError):continue
        key=l+"|"+m
        # Do not use last poll timestamps as a revision: they change without content changes.
        fingerprint=json.dumps([r["homeScore"],r["awayScore"],status,r.get("actaState"),r.get("actaUrl")],ensure_ascii=False,separators=(",",":"))
        if key in out and out[key]["fingerprint"]!=fingerprint:raise ValueError("conflicting_fixture")
        out[key]={"leagueId":l,"matchId":m,"iso":iso,"fingerprint":fingerprint}
    return out

def select(rows,state,mode,today=None):
    today=today or datetime.now(ZoneInfo("Europe/Madrid")).date()
    recent=(today-timedelta(days=7)).isoformat()
    selected=[]
    for key,r in rows.items():
        old=state.get(key,{})
        if mode!="weekly" and old.get("status")=="verified" and old.get("fingerprint")==r["fingerprint"]:continue
        if mode!="weekly" and old.get("status")=="pending" and old.get("fingerprint")==r["fingerprint"]:
            try:
                if datetime.now(timezone.utc)-datetime.fromisoformat(old["checkedAt"])<timedelta(minutes=15):continue
            except (KeyError,ValueError,TypeError):pass
        if mode=="weekly" or r["iso"]>=recent or old: selected.append((key,r))
    if mode=="weekly":
        return sorted(selected,key=lambda x:(state.get(x[0],{}).get("checkedAt",""),x[1]["iso"],x[0]))
    return sorted(selected,key=lambda x:(state.get(x[0],{}).get("checkedAt",""),x[1]["iso"],x[0]))

# Only explicitly labelled team foul values; do not infer missing zeros or sides.
FOULS_CAPTURE=r"""()=>{
 const visible=e=>e&&e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 const scopes=[...document.querySelectorAll('.sidgad-match-modal')].filter(visible);if(scopes.length!==1)return {};
 const scope=scopes[0],norm=x=>String(x||'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().replace(/\s+/g,' ').trim();
 const label=/^(?:faltas|faltes|faltas de equipo|faltes d'equip|faltas equipo|team fouls)$/;
 const read=x=>/^\d{1,3}$/.test(norm(x))?Number(norm(x)):null;
 const values={home:new Set(),away:new Set()};
 for(const [side,selector] of [['home','.sidgad-local'],['away','.sidgad-visit']]){
  for(const box of scope.querySelectorAll(selector)){
   if(!visible(box))continue;
   for(const e of box.querySelectorAll('*')){
    if(!visible(e)||e.children.length)continue;
    const t=norm(e.innerText),m=t.match(/^(?:faltas(?: de equipo)?|faltes(?: d'equip)?|team fouls)\s*:?\s*(\d{1,3})$/);
    if(m)values[side].add(Number(m[1]));
    if(label.test(t.replace(/:$/,''))){const siblings=[...e.parentElement.children].filter(x=>x!==e&&visible(x));if(siblings.length===1){const v=read(siblings[0].innerText);if(v!==null)values[side].add(v)}}
   }
  }
 }
 return Object.fromEntries(Object.entries(values).filter(([_,v])=>v.size===1).map(([k,v])=>[k,[...v][0]]));
}"""

# Explicit sports comparison rows; preserve labels and values, not arbitrary page text.
TEAM_STATS_CAPTURE=r"""()=>{
 const visible=e=>e&&e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 const scopes=[...document.querySelectorAll('.sidgad-match-modal')].filter(visible);if(scopes.length!==1)return {};
 const out={},text=e=>String(e?.innerText||'').trim().replace(/\s+/g,' ');
 for(const row of scopes[0].querySelectorAll('.sidgad-match-stats-table-like .sidgad-stat-row')){
   if(!visible(row))continue;
   const names=[...row.querySelectorAll('.sidgad-stat-name')].filter(visible),vals=[...row.querySelectorAll('.sidgad-stat-val')].filter(visible);
   if(names.length!==1||vals.length!==2)continue;
   const label=text(names[0]),home=text(vals[0]),away=text(vals[1]);
   if(!label||label.length>80||!/^[\p{L}\p{N} .,%()/'’+\-]+$/u.test(label)||!/^\d{1,4}(?:[.,]\d+)?\s*%?$/.test(home)||!/^\d{1,4}(?:[.,]\d+)?\s*%?$/.test(away))continue;
   if(!(vals[1].matches('.sidgad-right')||vals[1].closest('.sidgad-right')))continue;
   out[label]={home,away};
 }
 return out;
}"""

async def closed_acta(ctx,league,match,details=None):
    page=await ctx.new_page()
    try:
        res=await page.goto(BASE+"?"+urlencode({"liga":league,"vista":"calendar","partido":match}),wait_until="domcontentloaded",timeout=30000)
        if res and res.status in (403,429,503):return [],[],f"http_{res.status}"
        await page.wait_for_selector(".sidgad-match-modal .sidgad-roster-table",timeout=18000)
        # Require a positive closed/finished label inside the match modal.
        labels=await page.locator(".sidgad-match-modal:visible .sidgad-modal-status:visible").all_inner_texts()
        if not any(norm(v) in FINAL for v in labels) or any(LIVE.search(norm(v)) for v in labels):return [],[],"closure_unverified"
        if details is not None:
            try:
                fouls=await page.evaluate(FOULS_CAPTURE)
                if fouls:details.update(source="FECAPA",fouls=fouls)
                team_stats=await page.evaluate(TEAM_STATS_CAPTURE)
                if team_stats:
                    details.update(source="FECAPA",teamStats=team_stats)
                    for label,values in team_stats.items():
                        if norm(label) in {"faltes","faltas","faltes d'equip","faltas de equipo"}:
                            found={k:int(v) for k,v in values.items() if v.isdigit()}
                            old=details.get("fouls",{})
                            details["fouls"]={**old,**{k:v for k,v in found.items() if k not in old or old[k]==v}}
            except Exception:
                pass
        summary=await stable_rows(page,league,"summary")
        if not summary:return [],[],"summary_empty"
        modal=page.locator(".sidgad-match-modal:visible")
        target=await official_tab(modal) if await modal.count()==1 else None
        if target is None:return [],[],"official_unavailable"
        await target.click(timeout=10000)
        await page.wait_for_selector(".sidgad-match-modal .sidgad-acta-hoja",timeout=12000)
        if details is not None:
            try:
                fouls=await page.evaluate(FOULS_CAPTURE)
                if fouls:
                    old=details.get("fouls",{})
                    merged={**old,**fouls}
                    for side in old.keys() & fouls.keys():
                        if old[side]!=fouls[side]:merged.pop(side,None)
                    if merged:details.update(source="FECAPA",fouls=merged)
                    else:details.pop('fouls',None)
            except Exception:
                pass
        official=await stable_rows(page,league,"official")
        return summary,official,None if official else "official_empty"
    except Exception as e:return [],[],type(e).__name__
    finally:await page.close()

def merge_verified(master,candidate):
    # Only complete and unambiguous match snapshots reach this function.
    # Correct explicit values; retain old optional facts when a new page omits them.
    for pid,p in candidate["players"].items():
        old=master["players"].setdefault(pid,p)
        old["nameVariants"]=sorted(set(old["nameVariants"]+p["nameVariants"]+[old["name"]]))
        old["lastSeenAt"]=p["lastSeenAt"]
    for key,a in candidate["matchAppearances"].items():
        old=master["matchAppearances"].get(key,{})
        merged={**old,**a}
        if old.get("stats") or a.get("stats"):merged["stats"]={**old.get("stats",{}),**a.get("stats",{})}
        if old.get("fecapaFields") or a.get("fecapaFields"):
            merged["fecapaFields"]={**old.get("fecapaFields",{}),**a.get("fecapaFields",{})}
        master["matchAppearances"][key]=merged

async def maintain(a,rows,leagues):
    target=a.private_dir/"jugadors-master.json"
    state_path=a.private_dir/"jugadors-maintenance-state.json"
    if not a.private_dir.is_absolute() or not a.private_dir.is_dir() or not target.is_file():raise ValueError("private_master_required")
    if a.private_dir.stat().st_mode&0o077:raise ValueError("private_permissions_required")
    master=load(target,"41");verify_master(master)
    if not master["players"]:raise ValueError("bootstrap_required")
    master.setdefault("matchAppearances",{})
    state=json.loads(state_path.read_text()) if state_path.exists() else {"matches":{}}
    if not isinstance(state.get("matches"),dict):raise ValueError("state_invalid")
    plan=select(rows,state["matches"],a.mode)
    if a.mode=="incremental" and not plan:
        return {"mode":a.mode,"selected":0,"verified":0,"pending":0,"noChanges":True}
    if a.limit:plan=plan[:a.limit]
    report={"mode":a.mode,"selected":len(plan),"verified":0,"pending":0,"reasons":{},"rosterErrors":[],"leagues":[]}
    deadline=time.monotonic()+a.budget_minutes*60
    match_deadline=deadline-90*60 if a.mode=="weekly" else deadline-30
    affected=set()
    if plan:
        async with async_playwright() as pw:
            browser,ctx=await chromium_context(pw)
            try:
                for key,r in plan:
                    if time.monotonic()>=match_deadline:break
                    l,m=r["leagueId"],r["matchId"]
                    for attempt in range(3):
                        summary,official,error=await closed_acta(ctx,l,m)
                        if not error or error in ("closure_unverified","http_403","http_429","http_503"):break
                        await asyncio.sleep(3*(attempt+1))
                    if error in ("http_403","http_429","http_503"):
                        report["reasons"][error]=report["reasons"].get(error,0)+1;break
                    if not error:
                        candidate=empty("41")
                        result=ingest_appearances(candidate,l,m,summary,official,now())
                        old_keys={k for k,v in master["matchAppearances"].items() if v["leagueId"]==l and v["matchId"]==m}
                        if not result["stored"] or result["stored"]!=len(summary) or result["officialMatched"]!=len(summary) or result["conflicts"] or not old_keys<=set(candidate["matchAppearances"]):
                            error="incomplete_or_changed_roster"
                        else:
                            verify_master(candidate);merge_verified(master,candidate)
                            affected.update((l,norm(v.get("teamName"))) for v in candidate["matchAppearances"].values())
                            report["verified"]+=1
                    if error:
                        report["pending"]+=1;report["reasons"][error]=report["reasons"].get(error,0)+1
                    state["matches"][key]={"status":"pending" if error else "verified","fingerprint":r["fingerprint"],"checkedAt":now()}
                    # Write master before state: a crash may cause safe reprocessing, never skipping.
                    if (report["verified"]+report["pending"])%10==0:
                        verify_master(master);save(target,master);save(state_path,state)
                    await asyncio.sleep(1.2)
            finally:await ctx.close();await browser.close()
    if a.mode=="weekly":
        await all_rosters(leagues,master,report,deadline)
    else:
        seeds=sorted({(m["leagueId"],m["teamFilterId"]) for m in master["memberships"].values() if (m["leagueId"],norm(m.get("teamName"))) in affected})
        if seeds and time.monotonic()<deadline:
            args=SimpleNamespace(seed=seeds,only_seed=True,season="41",max_teams=None,inspect_profiles=False,profiles_per_team=1)
            try:await asyncio.wait_for(collect(args,sorted({l for l,t in seeds}),master,report),timeout=max(1,deadline-time.monotonic()))
            except Exception as e:report["rosterErrors"].append({"errorType":type(e).__name__})
    enrich_names(master,a.catalog);report["linkedAppearances"]=link_memberships(master)
    master.update(updatedAt=now(),coverageVerified=False)
    verify_master(master);save(target,master);save(state_path,state)
    if load(target,"41")!=master:raise ValueError("roundtrip_mismatch")
    report["rosterTeamsObserved"]=sum(x["teamsObserved"] for x in report["leagues"])
    report["rosterTeamsSelected"]=sum(x["teamsSelected"] for x in report["leagues"])
    report["rosterLeaguesAttempted"]=len(report["leagues"])
    report["rosterErrorCount"]=sum(x["errors"] for x in report.pop("leagues"))
    report["unprocessed"]=max(0,len(plan)-report["verified"]-report["pending"])
    report["coverageComplete"]=not (report["unprocessed"] or report["pending"] or report["rosterErrorCount"] or report["rosterErrors"]) and (a.mode!="weekly" or report["rosterLeaguesAttempted"]==len(leagues))
    report["players"]=len(master["players"]);report["appearances"]=len(master["matchAppearances"])
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",type=Path,required=True);p.add_argument("--mode",choices=["incremental","weekly"],required=True)
    p.add_argument("--private-dir",type=Path);p.add_argument("--limit",type=int,default=0);p.add_argument("--budget-minutes",type=int)
    a=p.parse_args()
    if a.budget_minutes is None:a.budget_minutes=320 if a.mode=="weekly" else 4
    try:
        rows=candidates(a.catalog);acts,leagues,errors=read_catalog(a.catalog)
        if a.private_dir:
            report=asyncio.run(maintain(a,rows,leagues))
        else:
            report={"mode":a.mode,"planOnly":True,"eligibleFixtures":len(rows),"recentCandidates":len(select(rows,{},"incremental")),"inventoryActs":len(acts),"inventoryLeagues":len(leagues),"catalogErrors":errors,"privateStorageConfigured":False}
        print(json.dumps(report),flush=True);return 0
    except Exception as e:
        print(json.dumps({"errorType":type(e).__name__}),flush=True);return 2
if __name__=="__main__":raise SystemExit(main())
