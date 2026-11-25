#!/usr/bin/env python3
"""Full known FECAPA inventory. Identifiable data stays in ephemeral runner storage."""
import argparse,asyncio,collections,json,os,re,tempfile,time,unicodedata
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from playwright.async_api import async_playwright
from zonaok_fecapa_unificat import chromium_context
from zonaok_jugadors_auto import BASE,empty,collect,inventory,enrich_names,verify_master,save,load,now,numeric
from zonaok_actes_jugadors_probe import CAPTURE,ingest_appearances

def read_catalog(root):
    acts={};leagues=set();errors=[]
    for filename,collection in (("zonaok-actes.json","fixtures"),("zonaok-tots-actes.json","rows")):
        try:
            rows=json.loads((root/filename).read_text(encoding="utf-8"))[collection]
            for row in rows:
                l=str(row.get("leagueId") or row.get("league") or "")
                m=str(row.get("matchId") or row.get("id") or "")
                if numeric(l) and numeric(m):
                    acts.setdefault((l,m),True);leagues.add(l)
        except Exception as e:errors.append({"catalog":filename,"errorType":type(e).__name__})
    for filename in ("zonaok-classificacions.json","zonaok-tots-agenda.json"):
        try:leagues.update(inventory([root/filename]))
        except Exception as e:errors.append({"catalog":filename,"errorType":type(e).__name__})
    return sorted(acts,key=lambda x:(int(x[0]),int(x[1]))),sorted(leagues,key=int),errors

async def stable_rows(page,league,mode):
    previous=None;stable=0;raw={"rows":[]}
    for _ in range(24):
        raw=await page.evaluate(CAPTURE,{"league":league,"mode":mode})
        sig=json.dumps(raw,sort_keys=True)
        stable=stable+1 if raw["rows"] and sig==previous else 1
        previous=sig
        if stable>=3:return raw["rows"]
        await page.wait_for_timeout(650)
    return []

async def fetch_acta(ctx,l,m):
    page=await ctx.new_page()
    try:
        response=await page.goto(BASE+"?"+urlencode({"liga":l,"vista":"calendar","partido":m}),wait_until="domcontentloaded",timeout=30000)
        if response and response.status in (403,429,503):return [],[],f"http_{response.status}"
        await page.wait_for_selector(".sidgad-match-modal .sidgad-roster-table",timeout=18000)
        summary=await stable_rows(page,l,"summary")
        if not summary:return [],[],"summary_empty"
        modal=page.locator(".sidgad-match-modal:visible")
        tabs=modal.locator(".sidgad-modal-tab-btn:visible")
        official=[]
        if await modal.count()==1 and await tabs.count()==2:
            await tabs.nth(1).click(timeout=10000)
            try:
                await page.wait_for_selector(".sidgad-match-modal .sidgad-acta-hoja",timeout=12000)
                official=await stable_rows(page,l,"official")
            except Exception:pass
        return summary,official,None if official else "official_unavailable"
    except Exception as e:return [],[],type(e).__name__
    finally:await page.close()

def link_memberships(doc):
    def norm(v):return " ".join("".join(c for c in unicodedata.normalize("NFKD",str(v or "")) if not unicodedata.combining(c)).upper().split())
    by=collections.defaultdict(list)
    for m in doc["memberships"].values():
        if m.get("teamName"):by[(m["leagueId"],m["playerId"],norm(m["teamName"]))].append(m["teamFilterId"])
    linked=0
    for a in doc["matchAppearances"].values():
        options=set(by.get((a["leagueId"],a["playerId"],norm(a.get("teamName"))),[]))
        if len(options)==1:a["teamFilterId"]=next(iter(options));linked+=1
    return linked

async def fetch_acta_retry(ctx,l,m):
    result=([],[],"not_attempted")
    for attempt in range(3):
        result=await fetch_acta(ctx,l,m)
        summary,official,error=result
        if error in ("http_403","http_429","http_503") or (summary and official):return result
        if attempt<2:await asyncio.sleep(3*(attempt+1))
    return result

async def all_actes(acts,doc,report,checkpoint,deadline):
    queue=asyncio.Queue()
    for item in acts:queue.put_nowait(item)
    counter=report["acts"];failures=[];retry=[];lock=asyncio.Lock()
    stop=asyncio.Event()
    async with async_playwright() as pw:
        browser,ctx=await chromium_context(pw)
        async def worker():
            while not stop.is_set() and time.monotonic()<deadline:
                try:l,m=queue.get_nowait()
                except asyncio.QueueEmpty:break
                try:
                    summary,official,error=await fetch_acta_retry(ctx,l,m)
                    if error in ("http_403","http_429","http_503"):
                        stop.set()
                    if summary:
                        result=ingest_appearances(doc,l,m,summary,official,now())
                        if result["stored"]:
                            counter["withAppearances"]+=1
                            counter["withOfficialMatches"]+=int(result["officialMatched"]>0)
                            counter["officialMatchedRows"]+=result["officialMatched"]
                            counter["conflicts"]+=result["conflicts"]
                        else:error=error or "no_verified_appearances"
                    if error:failures.append({"leagueId":l,"matchId":m,"reason":error})
                    if not summary or not result["stored"]:counter["withoutAppearances"]+=1
                    counter["attempted"]+=1
                    if counter["attempted"]%50==0:
                        async with lock:
                            save(checkpoint,doc)
                            print(json.dumps({"phase":"acts","attempted":counter["attempted"],"target":len(acts),"withAppearances":counter["withAppearances"],"appearances":len(doc["matchAppearances"])}),flush=True)
                except Exception as e:
                    counter["attempted"]+=1;counter["withoutAppearances"]+=1
                    failures.append({"leagueId":l,"matchId":m,"reason":type(e).__name__})
                finally:queue.task_done()
                await asyncio.sleep(1.2)
        try:await asyncio.gather(worker(),worker())
        finally:await ctx.close();await browser.close()
    counter["unattempted"]=queue.qsize();counter["rateLimitStop"]=stop.is_set()
    counter["failures"]=failures
    counter["failureReasons"]=dict(collections.Counter(x["reason"] for x in failures))

async def all_rosters(leagues,doc,report,deadline):
    args=SimpleNamespace(seed=[],only_seed=False,season="41",max_teams=None,inspect_profiles=False,profiles_per_team=1)
    # Two bounded sequential streams, each with one browser page at a time.
    async def worker(items):
        for league in items:
            if time.monotonic()>=deadline:break
            try:
                await asyncio.wait_for(collect(args,[league],doc,report),timeout=max(1,deadline-time.monotonic()))
            except asyncio.TimeoutError:break
            except Exception as e:report["rosterErrors"].append({"leagueId":league,"errorType":type(e).__name__})
            print(json.dumps({"phase":"rosters","leaguesAttempted":len(report["leagues"]),"target":len(leagues),"memberships":len(doc["memberships"])}),flush=True)
    await asyncio.gather(worker(leagues[::2]),worker(leagues[1::2]))

async def run(a,private):
    acts,leagues,catalog_errors=read_catalog(a.catalog)
    if not acts or not leagues:raise ValueError("inventory_empty")
    doc=empty("41")
    report={"schema":"zonaok-jugadors-total-master-diagnostic-v1","source":"FECAPA","seasonId":"41","startedAt":now(),"inventory":{"acts":len(acts),"leagues":len(leagues),"catalogErrors":catalog_errors},"acts":{"attempted":0,"withAppearances":0,"withoutAppearances":0,"withOfficialMatches":0,"officialMatchedRows":0,"conflicts":0},"leagues":[],"rosterErrors":[],"personalRecordsPersisted":False}
    started=time.monotonic()
    # Keep an independent finalisation window within the six-hour runner limit.
    deadline=started+a.budget_minutes*60
    checkpoint=private/"jugadors-master.json"
    print(json.dumps({"phase":"inventory","acts":len(acts),"leagues":len(leagues)}),flush=True)
    await all_actes(acts,doc,report,checkpoint,min(deadline-90*60,started+240*60))
    save(checkpoint,doc)
    await all_rosters(leagues,doc,report,deadline)
    report["nameEnrichment"]=enrich_names(doc,a.catalog)
    report["linkedAppearances"]=link_memberships(doc)
    doc.update(updatedAt=now(),coverageVerified=False,status="candidate_only")
    verify_master(doc);save(checkpoint,doc)
    reread=load(checkpoint,"41");verify_master(reread)
    if reread!=doc:raise ValueError("roundtrip_mismatch")
    report["master"]={"schemaValid":True,"roundTrip":True,"players":len(doc["players"]),"memberships":len(doc["memberships"]),"appearances":len(doc["matchAppearances"]),"jsonBytes":checkpoint.stat().st_size,"fieldCoverage":dict(collections.Counter(k for r in doc["matchAppearances"].values() for k in ("shirtNumber","position","captain","teamFilterId") if k in r)),"statCoverage":dict(collections.Counter(k for r in doc["matchAppearances"].values() for k in r.get("stats",{})))}
    report["rosters"]={"leaguesAttempted":len(report["leagues"]),"leaguesWithTeams":sum(x["teamsObserved"]>0 for x in report["leagues"]),"teamsSelected":sum(x["teamsSelected"] for x in report["leagues"]),"teamsObserved":sum(x["teamsObserved"] for x in report["leagues"]),"errors":sum(x["errors"] for x in report["leagues"])}
    # Keep only public match/league IDs and aggregate diagnostics; strip detailed roster probes.
    report["leagues"]=[{k:v for k,v in x.items() if k in ("leagueId","filters","teamsSelected","teamsObserved","membershipsObserved","errors","discoveredFilters","failedTeamFilters")} for x in report["leagues"]]
    report["profileEnrichment"]="not_run_separate_phase"
    report["finishedAt"]=now()
    report["coverageComplete"]=not catalog_errors and report["acts"]["attempted"]==len(acts) and not report["acts"]["failures"] and report["rosters"]["leaguesAttempted"]==len(leagues) and report["rosters"]["teamsObserved"]==report["rosters"]["teamsSelected"] and not report["rosters"]["errors"] and not report["rosterErrors"]
    report["retention"]="temporary_only_deleted"
    save(a.report,report)
    print(json.dumps({k:v for k,v in report.items() if k not in ("leagues","acts")}|{"acts":{k:v for k,v in report["acts"].items() if k!="failures"}}),flush=True)
    return 0 if report["coverageComplete"] else 2

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",type=Path,required=True)
    p.add_argument("--report",type=Path,default=Path("jugadors-total-master-diagnostic.json"))
    p.add_argument("--budget-minutes",type=int,default=330)
    a=p.parse_args()
    if not 100<=a.budget_minutes<=330:p.error("budget")
    try:
        with tempfile.TemporaryDirectory(prefix="zonaok-master-private-") as tmp:
            os.chmod(tmp,0o700)
            return asyncio.run(run(a,Path(tmp)))
    except Exception as e:
        print(json.dumps({"fatalError":type(e).__name__,"personalRecordsPersisted":False}),flush=True)
        return 2
if __name__=="__main__":raise SystemExit(main())
