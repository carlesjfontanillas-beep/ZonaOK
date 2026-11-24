#!/usr/bin/env python3
"""ZonaOK: importació candidata de plantilles FECAPA; no publica dades personals."""
import argparse, asyncio, json, re, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

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
        if label: m["teamName"]=label
        m.update(lastSeenAt=stamp,profileUrl=url(league,d["seasonId"],team,pid))
        seen.add(key)
    return len(seen)
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
 for(const s of document.querySelectorAll('select[name="filtro"],select#filtro')){
  if(!s.getClientRects().length)continue;
  for(const o of s.options)if(!o.disabled)add(o.value,o.textContent);
 }
 return [...out].map(([id,label])=>({id,label}));
}"""
EXTRACT=r"""({league,team,season})=>{
 const out=new Map(), t=x=>(x||'').replace(/\s+/g,' ').trim();
 let links=0,missing=0;
 for(const a of document.querySelectorAll('a[href]')){
  if(!a.getClientRects().length)continue;
  let u;try{u=new URL(a.getAttribute('href'),document.baseURI)}catch{continue}
  const q=u.searchParams,id=q.get('jugador');
  if(u.protocol!=='https:'||!/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(u.hostname)||q.get('vista')!=='plantillas'||!id||q.get('liga')!==league||q.get('filtro')!==team||(q.has('s')&&q.get('s')!==season))continue;
  links++;
  const name=t(a.innerText);
  if(!/\p{L}/u.test(name)||/^(ver|veure|perfil|ficha|fitxa|estad[ií]sticas|estad[ií]stiques|detalles|detalls)$/i.test(name)){missing++;continue}
  out.set(id,{id,name,league,team,season});
 }
 const birthLabel=[...document.querySelectorAll('th,label,dt')].some(e=>/nacimiento|naixement|fecha de nacimiento|data de naixement/i.test(e.textContent||''));
 return {rows:[...out.values()],links,missing,birthLabel};
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
async def collect(a,leagues,doc,report):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=False,args=["--no-sandbox"])
        try:
            page=await browser.new_page(locale="ca-ES",timezone_id="Europe/Madrid",viewport={"width":1420,"height":960})
            network={}
            def on_response(resp):
                try:
                    u=urlparse(resp.url)
                    if resp.request.resource_type not in ("xhr","fetch","script","document"):return
                    if u.hostname not in ("www.hoqueipatins.fecapa.cat","hoqueipatins.fecapa.cat","sidgad.cloud","sidgad.es","www.sidgad.es"):return
                    key=f"{u.hostname}|{resp.request.resource_type}|{resp.status}"
                    if resp.request.resource_type=="script" and resp.status>=400:
                        asset=u.path.rsplit("/",1)[-1]
                        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,100}\.js",asset):key+="|"+asset
                    network[key]=network.get(key,0)+1
                except Exception:pass
            page.on("response",on_response)
            for league in leagues:
                lr={"leagueId":league,"filters":0,"teamsObserved":0,"links":0,"missingNames":0,"membershipsObserved":0,"errors":0,"birthLabelTeams":0}
                report["leagues"].append(lr)
                filters={f:None for l,f in a.seed if l==league}
                if not a.only_seed:
                    try:
                        await open_page(page,url(league,a.season),'a[href*="filtro="]:visible,select[name="filtro"]:visible,select#filtro:visible')
                        for t in await page.evaluate(DISCOVER,{"league":league,"season":a.season}):filters[t["id"]]=t["label"] or filters.get(t["id"])
                    except Exception:lr["errors"]+=1
                lr["filters"]=len(filters)
                if not filters:lr["errors"]+=1
                for team,label in sorted(filters.items(),key=lambda x:int(x[0])):
                    network.clear()
                    stage="navigation"
                    try:
                        await open_page(page,url(league,a.season,team),'a[href*="jugador="]:visible')
                        stage="extract"
                        args={"league":league,"team":team,"season":a.season}
                        first=await page.evaluate(EXTRACT,args)
                        await page.wait_for_timeout(1200)
                        data=await page.evaluate(EXTRACT,args)
                        if first["links"]!=data["links"]:
                            await page.wait_for_timeout(1500);data=await page.evaluate(EXTRACT,args)
                        n=merge(doc,league,team,data["rows"],label,now())
                        lr["links"]+=data["links"];lr["missingNames"]+=data["missing"];lr["birthLabelTeams"]+=int(data["birthLabel"])
                        lr["membershipsObserved"]+=n;lr["teamsObserved"]+=int(n>0);lr["errors"]+=int(n==0)
                    except Exception as e:
                        lr["errors"]+=1
                        lr["lastError"]={"stage":stage,"type":type(e).__name__,"code":str(e) if str(e) in {"context","HTTP_403","HTTP_404","HTTP_500","HTTP_none"} else None}
                    if a.only_seed or lr["teamsObserved"]==0:
                        lr["pageDiagnostic"]=await diagnostic(page)
                        lr["networkSummary"]=dict(network)
                    await page.wait_for_timeout(1000)
        finally:await browser.close()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inventory",action="append",default=[]);p.add_argument("--league",action="append",default=[]);p.add_argument("--seed",action="append",default=[]);p.add_argument("--only-seed",action="store_true");p.add_argument("--season",default="41");p.add_argument("--max-leagues",type=int);p.add_argument("--previous");p.add_argument("--output",default="private/jugadors-master.json");p.add_argument("--report",default="jugadors-diagnostic.json")
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
    if n:doc.update(updatedAt=now(),coverageVerified=False);save(a.output,doc)
    save(a.report,report)
    print(json.dumps({k:v for k,v in report.items() if k!="leagues"}))
    if a.only_seed: print(json.dumps({"diagnostics":report["leagues"]},ensure_ascii=False))
    return 0 if n else 2
if __name__=="__main__":raise SystemExit(main())
