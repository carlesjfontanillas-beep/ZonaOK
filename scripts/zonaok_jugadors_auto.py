#!/usr/bin/env python3
"""ZonaOK: importació candidata de plantilles FECAPA; no publica dades personals."""
import argparse, asyncio, json, re, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from zonaok_fecapa_unificat import chromium_context

BASE="https://www.hoqueipatins.fecapa.cat/"
SCHEMA="zonaok-jugadors-v1"
def now(): return datetime.now(timezone.utc).isoformat()
def numeric(x): return isinstance(x,str) and bool(re.fullmatch(r"[1-9][0-9]*",x))
def url(league,season,team=None,player=None):
    q={"liga":league,"vista":"plantillas"}
    if team: q["filtro"]=team
    if player: q["jugador"]=player
    q["s"]=season
    return BASE+"?"+urlencode(q)
def empty(season): return {"schema":SCHEMA,"source":"FECAPA","seasonId":season,"players":{},"memberships":{}}
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,delete=False) as f:
        tmp=f.name;json.dump(data,f,ensure_ascii=False,indent=2)
    os.replace(tmp,path)
def load(path,season):
    if not path or not Path(path).exists(): return empty(season)
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema")!=SCHEMA or d.get("source")!="FECAPA" or d.get("seasonId")!=season or not isinstance(d.get("players"),dict) or not isinstance(d.get("memberships"),dict): raise ValueError("Master incompatible")
    return d
def merge(d,league,team,rows,label,stamp):
    seen=set()
    for r in rows:
        pid=r.get("id");name=" ".join(str(r.get("name") or "").split())
        if not numeric(pid) or not name or len(name)>200 or not any(c.isalpha() for c in name): continue
        if [r.get("league"),r.get("team"),r.get("season")]!=[league,team,d["seasonId"]]: continue
        p=d["players"].setdefault(pid,{"playerId":pid,"name":name,"firstSeenAt":stamp,"nameVariants":[]})
        p["lastSeenAt"]=stamp;p["nameVariants"]=sorted(set(p["nameVariants"]+[p["name"],name]))
        key="|".join([d["seasonId"],league,team,pid])
        m=d["memberships"].setdefault(key,{"playerId":pid,"leagueId":league,"teamFilterId":team,"seasonId":d["seasonId"],"teamName":None,"teamId":None,"clubId":None,"clubName":None,"firstSeenAt":stamp})
        if r.get("teamName") or label: m["teamName"]=r.get("teamName") or label
        if numeric(r.get("clubId")): m["clubId"]=r["clubId"]
        if isinstance(r.get("sports"),dict): m["sports"]=r["sports"]
        m.update(lastSeenAt=stamp,profileUrl=url(league,d["seasonId"],team,pid))
        seen.add(key)
    return len(seen)
def verify_master(d):
    from jsonschema import Draft202012Validator
    schema_path=Path(__file__).resolve().parents[1]/"schemas"/"jugadors-master.schema.json"
    schema=json.loads(schema_path.read_text(encoding="utf-8"))
    # Do not print ValidationError, which could contain a player's personal data.
    if not Draft202012Validator(schema).is_valid(d):raise ValueError("schema_invalid")
    for key,p in d["players"].items():
        if key!=p["playerId"]:raise ValueError("player_key_invalid")
    referenced=set()
    for key,m in d["memberships"].items():
        expected="|".join([m["seasonId"],m["leagueId"],m["teamFilterId"],m["playerId"]])
        if key!=expected or m["seasonId"]!=d["seasonId"] or m["playerId"] not in d["players"]:raise ValueError("membership_invalid")
        if m["profileUrl"]!=url(m["leagueId"],m["seasonId"],m["teamFilterId"],m["playerId"]):raise ValueError("profile_url_invalid")
        referenced.add(m["playerId"])
    if referenced!=set(d["players"]):raise ValueError("unlinked_player")
    return True
def persistence_probe(d):
    import copy
    verify_master(d)
    with tempfile.TemporaryDirectory(prefix="zonaok-private-") as tmp:
        target=Path(tmp)/"jugadors-master.json"
        save(target,d)
        first=load(target,d["seasonId"])
        verify_master(first)
        if first!=d:raise ValueError("roundtrip_mismatch")
        # Exercise another merge using observed rows, preserving all memberships.
        second=copy.deepcopy(first)
        for m in first["memberships"].values():
            p=first["players"][m["playerId"]]
            r={"id":m["playerId"],"name":p["name"],"league":m["leagueId"],"team":m["teamFilterId"],"season":m["seasonId"],"teamName":m.get("teamName"),"clubId":m.get("clubId"),"sports":m.get("sports",{})}
            merge(second,m["leagueId"],m["teamFilterId"],[r],m.get("teamName"),m["lastSeenAt"])
        verify_master(second)
        if len(second["players"])!=len(first["players"]) or len(second["memberships"])!=len(first["memberships"]):raise ValueError("duplicate_after_reimport")
        save(target,second)
        reread=load(target,d["seasonId"])
        verify_master(reread)
        if reread!=second:raise ValueError("second_roundtrip_mismatch")
        return {"schemaValid":True,"roundTrip":True,"reimportNoDuplicates":True,"playersSavedAndReloaded":len(first["players"]),"membershipsSavedAndReloaded":len(first["memberships"]),"jsonBytes":target.stat().st_size,"retention":"temporary_only_deleted"}

def inventory(paths):
    ids=set()
    for p in paths:
        d=json.loads(Path(p).read_text(encoding="utf-8"))
        for v in d.get("competitions",{}).values():
            if isinstance(v,dict): ids.add(str(v.get("leagueId","")))
        for v in d.get("matches",d.get("rows",[])):
            if isinstance(v,dict): ids.add(str(v.get("leagueId") or v.get("league") or ""))
    return {x for x in ids if numeric(x)}
DISCOVER=r"""({league,season})=>{
 const out=new Map(), t=x=>(x||'').replace(/\s+/g,' ').trim();
 const add=(id,label)=>{if(/^[1-9]\d*$/.test(id||''))out.set(id,out.get(id)||t(label)||null)};
 for(const a of document.querySelectorAll('a[href]')){
  if(!a.getClientRects().length)continue;
  let u;try{u=new URL(a.getAttribute('href'),document.baseURI)}catch{continue}
  const q=u.searchParams;
  if(u.protocol==='https:'&&/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(u.hostname)&&q.get('vista')==='plantillas'&&q.get('liga')===league&&!q.has('jugador')&&(!q.has('s')||q.get('s')===season))add(q.get('filtro'),a.innerText);
 }
 // V3 confirmed these actual SIDGAD selector items. Each candidate
 // still requires a roster profile link matching its league and filter.
 for(const item of document.querySelectorAll('.sidgad-liga-team-selector .sidgad-team-selector-item[data-team-id]')){
   add(item.getAttribute('data-team-id'),item.getAttribute('data-team-name')||item.querySelector('.sidgad-team-selector-name')?.textContent);
 }
 for(const s of document.querySelectorAll('select[name="filtro"],select#filtro')){
  if(!s.getClientRects().length)continue;
  for(const o of s.options)if(!o.disabled)add(o.value,o.textContent);
 }
 return [...out].map(([id,label])=>({id,label}));
}"""
EXTRACT=r"""({league,team,season})=>{
 const out=new Map(), t=x=>(x||'').replace(/\s+/g,' ').trim();
 let links=0,missing=0; const headerCounts={}, logoPatterns={};
 for(const a of document.querySelectorAll('.sidgad-plantillas a.sidgad-player-link[href]')){
  if(!a.getClientRects().length)continue;
  let u;try{u=new URL(a.getAttribute('href'),document.baseURI)}catch{continue}
  const q=u.searchParams,id=q.get('jugador');
  if(u.protocol!=='https:'||!/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(u.hostname)||q.get('vista')!=='plantillas'||!id||q.get('liga')!==league||q.get('filtro')!==team||(q.has('s')&&q.get('s')!==season))continue;
  links++;
  const name=t(a.innerText);
  if(!/\p{L}/u.test(name)||/^(ver|veure|perfil|ficha|fitxa|estad[ií]sticas|estad[ií]stiques|detalles|detalls)$/i.test(name)){missing++;continue}
  const row=a.closest('tr'), table=row?.closest('table'), sports={};
  const norm=x=>t(x).normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().replace(/[.:\s]+/g,' ').trim();
  const fields={dorsal:'number',numero:'number',num:'number',pj:'played','partits jugats':'played','partidos jugados':'played',g:'goals',gols:'goals',goles:'goals',ta:'yellowCards',tr:'redCards',tb:'blueCards','targetes grogues':'yellowCards','tarjetas amarillas':'yellowCards','targetes vermelles':'redCards','tarjetas rojas':'redCards','targetes blaves':'blueCards','tarjetas azules':'blueCards'};
  if(row&&table){
    const h=table.querySelector('thead tr:last-child')||[...table.rows].find(r=>[...r.cells].some(c=>c.tagName==='TH'));
    if(h&&h.cells.length===row.cells.length&&[...h.cells,...row.cells].every(c=>c.colSpan===1&&c.rowSpan===1)){
      [...h.cells].forEach((c,i)=>{
        const label=norm(c.innerText), title=norm(c.title);
        // Only emit recognized sports labels and aggregate unknown counts.
        const safeLabels=/^(nom|nombre|jugador|jugadora|dorsal|numero|num|n|pj|pg|pe|pp|g|gl|gol|gols|goles|gf|gc|p|pts|pt|ta|tr|tb|tg|tv|min|mj|mp|pos|posicio|posicion|partits jugats|partidos jugados|targetes grogues|targetes vermelles|targetes blaves|tarjetas amarillas|tarjetas rojas|tarjetas azules)$/;
        const key=safeLabels.test(label)?label:safeLabels.test(title)?title:'other';
        headerCounts[key]=(headerCounts[key]||0)+1;
        const field=fields[label]||fields[title];
        const v=t(row.cells[i].innerText);
        if(field&&/^\d{1,5}$/.test(v))sports[field]=Number(v);
      });
    }
  }
  const sel=[...document.querySelectorAll('.sidgad-liga-team-selector .sidgad-team-selector-item[data-team-id]')].find(x=>x.getAttribute('data-team-id')===team);
  const teamName=t(sel?.getAttribute('data-team-name')||sel?.querySelector('.sidgad-team-selector-name')?.textContent);
  const logo=sel?.querySelector('img[src]');let clubId=null;
  if(logo){try{const u=new URL(logo.getAttribute('src'),document.baseURI),m=u.pathname.match(/^\/fecapa\/images\/logos_clubes\/(\d+)\.png$/i);if(u.protocol==='https:'&&u.hostname==='sidgad.cloud'&&m)clubId=m[1]}catch{}}
  const prior=out.get(id);
  if(prior){
    // Repeated links may represent different tables. Keep fields only if
    // consistent, and never sum statistics from different rows.
    for(const [k,v] of Object.entries(sports)){
      if(k in prior.sports&&prior.sports[k]!==v){delete prior.sports[k];prior.conflicts.add(k);}
      else if(!prior.conflicts.has(k))prior.sports[k]=v;
    }
    continue;
  }
  out.set(id,{id,name,league,team,season,sports,teamName,clubId,conflicts:new Set()});
 }
 const birthLabel=[...document.querySelectorAll('th,label,dt')].some(e=>/nacimiento|naixement|fecha de nacimiento|data de naixement/i.test(e.textContent||''));
 return {rows:[...out.values()].map(({conflicts,...r})=>({...r,conflictCount:conflicts.size})),links,missing,birthLabel,headerCounts};
}"""
DIAG=r"""()=>{
 const count=s=>document.querySelectorAll(s).length;
 const attrs={},classes={},params={};
 const increment=(o,k)=>o[k]=(o[k]||0)+1;
 const safe=k=>/^[a-z][a-z_-]{1,64}$/i.test(k);
 for(const e of document.querySelectorAll('*')){
   for(const a of e.attributes)if(/^data-/.test(a.name)&&safe(a.name))increment(attrs,a.name);
   for(const k of e.classList)if(/^sidgad[-_]/i.test(k)&&safe(k))increment(classes,k);
   if(e.tagName==='A'){
     try{const u=new URL(e.getAttribute('href')||'',document.baseURI);for(const k of u.searchParams.keys())if(['liga','vista','filtro','jugador','s'].includes(k))increment(params,k)}catch{}
   }
 }
 return {ready:document.readyState,bodyTextLength:document.body?.innerText.length||0,
   anchors:count('a[href]'),tables:count('table'),rows:count('tr'),selects:count('select'),frames:count('iframe'),
   playerHref:count('a[href*="jugador="]'),playerOnclick:count('[onclick*="jugador"]'),
   dataAttributes:attrs,sidgadClasses:classes,queryKeys:params,
   nameHeader: [...document.querySelectorAll('th')].some(e=>/^(nom|nombre|jugador|jugadora|nom i cognoms|nombre y apellidos)$/i.test(e.innerText.trim())),
   filterSelects:[...document.querySelectorAll('select')].map(e=>({name:safe(e.name)?e.name:null,id:safe(e.id)?e.id:null,options:e.options.length})).slice(0,30)};
}"""
async def diagnostic(page):
    out=[]
    for frame in page.frames:
        try:
            u=urlparse(frame.url)
            # Avoid URLs, query values, text, screenshots and raw bodies in logs.
            if u.hostname not in {"www.hoqueipatins.fecapa.cat","hoqueipatins.fecapa.cat","sidgad.cloud"}:continue
            d=await frame.evaluate(DIAG);d["host"]=u.hostname;d["main"]=frame==page.main_frame;out.append(d)
        except Exception:continue
    return out

async def open_page(page,target,selector):
    r=await page.goto(target,wait_until="domcontentloaded",timeout=30000)
    if not r or not r.ok: raise RuntimeError("HTTP_"+str(r.status if r else "none"))
    u=urlparse(page.url);q=parse_qs(u.query);want=parse_qs(urlparse(target).query)
    if u.scheme!="https" or u.hostname not in {"www.hoqueipatins.fecapa.cat","hoqueipatins.fecapa.cat"} or any(q.get(k)!=v for k,v in want.items() if k!="s") or ("s" in q and q["s"]!=want.get("s")):raise RuntimeError("context")
    try: await page.locator(selector).first.wait_for(timeout=15000)
    except Exception: pass
    await page.wait_for_timeout(5000)
PROFILE_DIAG=r"""()=>{
 const hero=document.querySelector('.sidgad-player-hero-card');
 const name=hero?.querySelector('.sidgad-player-name-compact');
 const visible=e=>!!e&&e.getClientRects().length>0;
 const scope=document.querySelector('.sidgad-player-overlay-body');
 if(!visible(hero)||!visible(name)||!name.innerText.trim()||!visible(scope))return {ready:false};
 const nodes=[...scope.querySelectorAll('th,label,dt,.sidgad-player-meta-item,.sidgad-ficha-subtitulo')];
 // Field-presence flags only. No text, dates, names or raw profile values in output.
 const has=rx=>nodes.some(e=>rx.test(e.innerText||''));
 return {ready:true,team:visible(hero.querySelector('.sidgad-player-team-name')),
 number:has(/\bdorsal\b/i),position:has(/posici[oó]/i),
 played:has(/partits jugats|partidos jugados|\bPJ\b/i),
 goals:has(/\bgols?\b|\bgoles?\b/i),
 cards:has(/targetes|tarjetas/i)};
}"""
async def inspect_profile(ctx,league,team,season,pid):
    page=await ctx.new_page()
    try:
        await open_page(page,url(league,season,team,pid),'.sidgad-player-name-compact')
        for _ in range(16):
            result=await page.evaluate(PROFILE_DIAG)
            if result.get("ready"):return result
            await page.wait_for_timeout(650)
        return {"ready":False}
    except Exception:return {"ready":False}
    finally:await page.close()

async def collect(a,leagues,doc,report):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser,ctx=await chromium_context(pw)
        try:
            for league in leagues:
                lr={"leagueId":league,"filters":0,"teamsSelected":0,"teamsObserved":0,"links":0,"missingNames":0,"membershipsObserved":0,"errors":0,"birthLabelTeams":0,"attempts":0}
                report["leagues"].append(lr)
                seeds=[f for l,f in a.seed if l==league]
                filters={f:None for f in seeds}
                if not a.only_seed:
                    page=await ctx.new_page()
                    try:
                        await open_page(page,url(league,a.season,seeds[0] if seeds else None),'.sidgad-liga-team-selector .sidgad-team-selector-item[data-team-id]')
                        previous=None;stable=0;found=[]
                        for _ in range(24):
                            found=await page.evaluate(DISCOVER,{"league":league,"season":a.season})
                            sig=tuple(sorted(x["id"] for x in found))
                            stable=stable+1 if sig and sig==previous else 1
                            previous=sig
                            if sig and stable>=3:break
                            await page.wait_for_timeout(650)
                        for t in found:filters[t["id"]]=t["label"] or filters.get(t["id"])
                        lr["discoveredFilters"]=len(found)
                        lr["seedInSelector"]=any(x["id"] in seeds for x in found) if seeds else None
                    except Exception as e:
                        lr["errors"]+=1;lr["discoveryError"]=type(e).__name__
                    finally:await page.close()
                lr["filters"]=len(filters)
                if not filters:lr["errors"]+=1
                ordered=seeds+[f for f in sorted(filters,key=int) if f not in seeds]
                if a.max_teams:ordered=ordered[:a.max_teams]
                lr["teamsSelected"]=len(ordered)
                for team in ordered:
                    accepted=None
                    for attempt in range(1,4):
                        lr["attempts"]+=1
                        page=await ctx.new_page()
                        network={}
                        def on_response(resp):
                            try:
                                u=urlparse(resp.url)
                                if resp.request.resource_type not in ("xhr","fetch","script","document"):return
                                if u.hostname not in ("www.hoqueipatins.fecapa.cat","hoqueipatins.fecapa.cat","sidgad.cloud","sidgad.es","www.sidgad.es"):return
                                key=f"{u.hostname}|{resp.request.resource_type}|{resp.status}"
                                network[key]=network.get(key,0)+1
                            except Exception:pass
                        page.on("response",on_response)
                        stage="navigation"
                        try:
                            await open_page(page,url(league,a.season,team),'.sidgad-plantillas a.sidgad-player-link[href]')
                            stage="extract"
                            args={"league":league,"team":team,"season":a.season}
                            signature=None;stable=0
                            for _ in range(24):
                                data=await page.evaluate(EXTRACT,args)
                                sig=tuple(sorted((r["id"],r["name"]) for r in data["rows"]))
                                stable=stable+1 if sig and sig==signature else 1
                                signature=sig
                                if sig and stable>=3 and data["missing"]==0:
                                    accepted=data;break
                                await page.wait_for_timeout(650)
                        except Exception as e:
                            lr["lastError"]={"stage":stage,"type":type(e).__name__}
                        finally:
                            if not accepted and attempt==3:
                                lr["pageDiagnostic"]=await diagnostic(page)
                                lr["networkSummary"]=dict(network)
                            await page.close()
                        if accepted:break
                        await asyncio.sleep(attempt)
                    if not accepted:lr["errors"]+=1;continue
                    n=merge(doc,league,team,accepted["rows"],filters[team],now())
                    lr["links"]+=accepted["links"];lr["missingNames"]+=accepted["missing"];lr["birthLabelTeams"]+=int(accepted["birthLabel"])
                    lr["membershipsObserved"]+=n;lr["teamsObserved"]+=int(n>0);lr["errors"]+=int(n==0)
                    hc=lr.setdefault("sportsHeaderCounts",{})
                    for k,v in accepted["headerCounts"].items():hc[k]=hc.get(k,0)+v
                    lr["duplicateLinks"]=lr.get("duplicateLinks",0)+accepted["links"]-len(accepted["rows"])
                    lr["conflictingSportsFields"]=lr.get("conflictingSportsFields",0)+sum(r.get("conflictCount",0) for r in accepted["rows"])
                    if a.inspect_profiles and "profileFieldProbe" not in lr and accepted["rows"]:
                        lr["profileFieldProbe"]=await inspect_profile(ctx,league,team,a.season,accepted["rows"][0]["id"])
                    await asyncio.sleep(1)
        finally:await ctx.close();await browser.close()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inventory",action="append",default=[]);p.add_argument("--league",action="append",default=[]);p.add_argument("--seed",action="append",default=[]);p.add_argument("--only-seed",action="store_true");p.add_argument("--season",default="41");p.add_argument("--max-leagues",type=int);p.add_argument("--max-teams",type=int);p.add_argument("--inspect-profiles",action="store_true");p.add_argument("--diagnostic-only",action="store_true");p.add_argument("--test-persistence",action="store_true");p.add_argument("--previous");p.add_argument("--output",default="private/jugadors-master.json");p.add_argument("--report",default="jugadors-diagnostic.json")
    a=p.parse_args()
    if not numeric(a.season) or any(not numeric(x) for x in a.league) or any(not re.fullmatch(r"[1-9]\d*:[1-9]\d*",x) for x in a.seed):p.error("IDs invàlids")
    a.seed=[tuple(s.split(":")) for s in a.seed]
    leagues=set(a.league)|{l for l,f in a.seed}
    if not a.only_seed:leagues|=inventory(a.inventory)
    if not leagues:p.error("Sense lligues")
    selected=sorted(leagues,key=int)
    if a.max_leagues:selected=selected[:a.max_leagues]
    doc=load(a.previous,a.season)
    report={"schema":"zonaok-jugadors-diagnostic-v1","source":"FECAPA","seasonId":a.season,"checkedAt":now(),"inventoryCount":len(leagues),"selectedCount":len(selected),"coverageVerified":False,"leagues":[]}
    try:asyncio.run(collect(a,selected,doc,report))
    except Exception as e:report["fatalError"]=type(e).__name__
    n=sum(x["membershipsObserved"] for x in report["leagues"])
    report.update(status="candidate_only" if n else "no_verified_rows",observedMemberships=n,playersInCandidate=len(doc["players"]),membershipsInCandidate=len(doc["memberships"]))
    from collections import Counter, defaultdict
    coverage=Counter()
    linked=defaultdict(list)
    for m in doc["memberships"].values():
        linked[m["playerId"]].append(m)
        for k in ("teamName","teamId","clubId","clubName","profileUrl"):
            if m.get(k):coverage[k]+=1
        for k in m.get("sports",{}):coverage["sports."+k]+=1
    report["fieldCoverage"]={"playerId":len(doc["players"]),"name":sum(bool(p.get("name")) for p in doc["players"].values()),"leagueId":len(doc["memberships"]),"teamFilterId":len(doc["memberships"]),"seasonId":len(doc["memberships"]),**dict(coverage)}
    report["multiMembershipPlayers"]=sum(len(v)>1 for v in linked.values())
    report["multiClubPlayersVerifiedByLogo"]=sum(len({m["clubId"] for m in v if m.get("clubId")})>1 for v in linked.values())
    report["teamsObserved"]=sum(x["teamsObserved"] for x in report["leagues"])
    report["leaguesObserved"]=sum(x["teamsObserved"]>0 for x in report["leagues"])
    report["privateDataSaved"]=bool(n and not a.diagnostic_only)
    if n:
        doc.update(updatedAt=now(),coverageVerified=False)
        if a.test_persistence:
            try:report["persistenceTest"]=persistence_probe(doc)
            except Exception as e:
                report["persistenceTest"]={"schemaValid":False,"errorType":type(e).__name__}
                report["status"]="persistence_failed"
        if not a.diagnostic_only and report["status"]!="persistence_failed":
            verify_master(doc);save(a.output,doc)
    report["privateDataSaved"]=bool(n and not a.diagnostic_only and report["status"]!="persistence_failed")
    save(a.report,report)
    print(json.dumps({k:v for k,v in report.items() if k!="leagues"}))
    if a.only_seed or a.max_teams: print(json.dumps({"diagnostics":report["leagues"]},ensure_ascii=False))
    return 0 if n and not report.get("fatalError") and report["status"]!="persistence_failed" else 2
if __name__=="__main__":raise SystemExit(main())
