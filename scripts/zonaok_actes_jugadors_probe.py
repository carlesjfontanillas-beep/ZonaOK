#!/usr/bin/env python3
"""Bounded acta diagnostic. No personal names, IDs, dates of birth or row values are persisted."""
import asyncio,json,re,copy,tempfile
from pathlib import Path
from urllib.parse import urlencode
from playwright.async_api import async_playwright
from zonaok_fecapa_players import chromium_context
from zonaok_jugadors_auto import empty,verify_master,persistence_probe,now,numeric
BASE="https://www.hoqueipatins.fecapa.cat/"
PROBE=r"""({league,match})=>{
 const visible=e=>!!e&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
 const norm=v=>String(v||'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().replace(/\s+/g,' ').trim();
 const known={goalkeeper:/^(?:p|porter|portero|portera)$/,captain:/^(?:c|capita|capitana|capitan)$/,number:/^(?:dorsal|num|numero|numero de dorsal|n[º°])$/,position:/^(?:posicio|posicion|rol|demarcacio|demarcacion)$/,player:/^(?:jugador|jugadora|nom|nombre|nom i cognoms|nombre y apellidos)$/,played:/^(?:pj|partits jugats|partidos jugados)$/,goals:/^(?:g|gols?|goles?)$/,assists:/^(?:a|assistencies|asistencias)$/,yellowCards:/^(?:ta|targetes grogues|tarjetas amarillas)$/,blueCards:/^(?:tb|targetes blaves|tarjetas azules)$/,redCards:/^(?:tr|targetes vermelles|tarjetas rojas)$/,minutes:/^(?:min|minuts|minutos)$/,starter:/^(?:titular|titulars|titulares)$/,substitute:/^(?:suplent|suplente|suplents|suplentes)$/,penalties:/^(?:penals|penaltis|penalties)$/,saves:/^(?:aturades|paradas)$/,role:/^(?:jugador de pista|jugador de campo)$/};
 const field=v=>Object.keys(known).find(k=>known[k].test(norm(v).replace(/[.:]+$/,'')))||null;
 const scopes=[...document.querySelectorAll('.sidgad-match-modal')].filter(visible);
 // Never treat the underlying competition roster as acta evidence.
 const scope=scopes.length===1?scopes[0]:null;
 const classes={};for(const e of document.querySelectorAll('[class*="sidgad"]'))if(visible(e))for(const c of e.classList)if(/^sidgad-[a-z-]{2,70}$/.test(c)&&/acta|partido|match|lineup|alineacio|overlay|modal/.test(c))classes[c]=(classes[c]||0)+1;
 if(!scope)return {actaScope:false,classes};
 const tables=[];
 const ids=new Set();let playerLinksTotal=0,matchContextLinks=0;
 const playerLink=a=>{
   try{const u=new URL(a.getAttribute('href'),document.baseURI),q=u.searchParams;
     if(u.protocol==='https:'&&/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(u.hostname)&&/^[1-9]\d*$/.test(q.get('jugador')||''))return {id:q.get('jugador'),context:q.get('liga')===league&&/^[1-9]\d*$/.test(q.get('filtro')||'')};
   }catch{}return null;
 };
 for(const a of scope.querySelectorAll('a[href]')){
   if(!visible(a))continue;const p=playerLink(a);
   if(p){playerLinksTotal++;ids.add(p.id);if(p.context)matchContextLinks++}
 }
 const divBlocks=[];
 for(const block of scope.querySelectorAll('.sidgad-match-stats-table-like,[role="table"],[role="grid"]')){
   if(!visible(block))continue;
   const classCounts={},dataAttrCounts={},labelCounts={},rowShapes={};let numericCells=0,linkedRows=0;
   for(const e of block.querySelectorAll('*')){
     if(!visible(e))continue;
     for(const c of e.classList)if(/^sidgad-[a-z-]{2,70}$/.test(c))classCounts[c]=(classCounts[c]||0)+1;
     for(const a of e.attributes)if(/^data-[a-z-]{1,50}$/.test(a.name))dataAttrCounts[a.name]=(dataAttrCounts[a.name]||0)+1;
     if(!e.children.length&&/^\d{1,5}$/.test(norm(e.innerText)))numericCells++;
     for(const v of [e.children.length===0?e.innerText:'',e.title,e.getAttribute('aria-label'),e.getAttribute('alt')]){
       const k=field(v);if(k)labelCounts[k]=(labelCounts[k]||0)+1;
     }
   }
   const rows=[...block.querySelectorAll('[role="row"],tr,[class*="stats-row"],[class*="fila"],[class*="player-row"]')].filter(visible);
   for(const r of rows){
     const n=[...r.children].filter(visible).length;rowShapes[n]=(rowShapes[n]||0)+1;
     if([...r.querySelectorAll('a[href]')].some(a=>visible(a)&&playerLink(a)))linkedRows++;
   }
   divBlocks.push({classCounts,dataAttrCounts,labelCounts,rowShapes,numericCells,rows:rows.length,linkedRows});
 }
 const tabs=[...scope.querySelectorAll('.sidgad-modal-tab-btn')].filter(visible).map(e=>{
   const v=norm(e.innerText||e.getAttribute('aria-label'));
   return {label:/^(?:resum|resumen|estadistiques|estadisticas|acta|alineacions|alineaciones|jugadors|jugadores|incidencies|incidencias|detalls|detalles|partit|partido|fitxa|ficha|cronologia|esdeveniments|eventos)$/.test(v)?v:'other'};
 });
 const modalClassCounts={},modalDataAttributes={};
 for(const e of scope.querySelectorAll('*')){
   if(!visible(e))continue;
   for(const c of e.classList)if(/^sidgad-[a-z-]{2,70}$/.test(c))modalClassCounts[c]=(modalClassCounts[c]||0)+1;
   for(const a of e.attributes)if(/^data-[a-z-]{1,50}$/.test(a.name))modalDataAttributes[a.name]=(modalDataAttributes[a.name]||0)+1;
 }
 for(const tb of scope.querySelectorAll('table')){
   if(!visible(tb))continue;
   const h=tb.querySelector('thead tr:last-child')||[...tb.rows].find(r=>[...r.cells].some(c=>c.tagName==='TH'));
   const columns=h?[...h.cells].map(c=>{
     const values=[c.innerText,c.title,c.getAttribute('aria-label'),...Array.from(c.querySelectorAll('[title],[aria-label],img[alt]')).flatMap(e=>[e.title,e.getAttribute('aria-label'),e.getAttribute('alt')])];
     const candidates=[...new Set(values.map(field).filter(Boolean))];return candidates.length===1?candidates[0]:'unknown';
   }):[];
   const rows=[...tb.rows].filter(r=>r!==h&&[...r.cells].some(c=>c.tagName==='TD')&&visible(r));
   let playerLinks=0,linkedRows=0;const populated={},markerCoverage={},linkedMarkerCoverage={};
   for(const row of rows){
     let links=0;
     for(const a of row.querySelectorAll('a[href]')){
       try{const u=new URL(a.getAttribute('href'),document.baseURI),q=u.searchParams;
       if(u.protocol==='https:'&&/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(u.hostname)&&/^[1-9]\d*$/.test(q.get('jugador')||''))links++;}catch{}
     }
     playerLinks+=links;linkedRows+=Number(links>0);
     if(columns.length===row.cells.length&&[...row.cells].every(c=>c.colSpan===1&&c.rowSpan===1))columns.forEach((k,i)=>{
       if(k==='unknown')return;const val=norm(row.cells[i].innerText);
       if(val)populated[k]=(populated[k]||0)+1;
       // User-confirmed acta conventions: P = goalkeeper, C = captain, Num = shirt number.
       // Only count an explicit marker in its own unambiguous column.
       if(!["goalkeeper","captain","number"].includes(k)||columns.filter(x=>x===k).length!==1)return;
       const marker=k==="goalkeeper"?"p":k==="captain"?"c":null;
       const status=k==="number"?(/^\d{1,3}$/.test(val)?"numeric":val?"other":"blank"):(val===marker?"marked":!val?"blank":"other");
       const bump=dest=>{const d=dest[k]||(dest[k]={});d[status]=(d[status]||0)+1};
       bump(markerCoverage);if(links===1)bump(linkedMarkerCoverage);
     });
   }
   tables.push({columns,rows:rows.length,playerLinks,linkedRows,populated,markerCoverage,linkedMarkerCoverage});
 }
 const labels={};
 for(const e of scope.querySelectorAll('th,h2,h3,h4,dt,label,[title],[aria-label]')){
   if(!visible(e))continue;
   for(const v of [e.innerText,e.title,e.getAttribute('aria-label')]){const k=field(v);if(k)labels[k]=(labels[k]||0)+1}
 }
 return {actaScope:true,classes,tabs,tables,divBlocks,labels,modalClassCounts,modalDataAttributes,playerLinks:playerLinksTotal,uniquePlayerIds:ids.size,matchContextLinks,rows:tables.reduce((n,t)=>n+t.rows,0)+divBlocks.reduce((n,t)=>n+t.rows,0)};
}"""

# Raw values are read only inside the ephemeral runner and never included in
# the public diagnostic, logs, screenshots or uploaded artifacts.
CAPTURE=r"""({league,mode})=>{
 const vis=e=>!!e&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
 const norm=x=>String(x||'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().replace(/[.,]/g,' ').replace(/\s+/g,' ').trim();
 const modal=[...document.querySelectorAll('.sidgad-match-modal')].filter(vis);
 if(modal.length!==1)return {rows:[],shapes:{},sideEvidence:{}};
 const scope=modal[0],text=e=>String(e?.innerText||'').replace(/\s+/g,' ').trim();
 const teams={home:text(scope.querySelector('.sidgad-modal-team.sidgad-local .sidgad-modal-team-name')),away:text(scope.querySelector('.sidgad-modal-team.sidgad-visit .sidgad-modal-team-name'))};
 const fields={number:/^(num|numero|dorsal|nº)$/,goalkeeper:/^(p|porter|portero|portera)$/,captain:/^(c|capita|capitana|capitan)$/,goals:/^(g|gol|gols|goles)$/,assists:/^(a|as|assistencies|asistencias)$/,yellowCards:/^(ta|targetes grogues|tarjetas amarillas)$/,blueCards:/^(tb|targetes blaves|tarjetas azules)$/,redCards:/^(tr|targetes vermelles|tarjetas rojas)$/};
 const field=c=>{
   const values=[text(c),c.title,c.getAttribute('aria-label'),...Array.from(c.querySelectorAll('[title],[aria-label],img[alt]')).flatMap(e=>[e.title,e.getAttribute('aria-label'),e.getAttribute('alt')])];
   const iconFields={yellowCards:'.acta-hp-card.card-yellow',blueCards:'.acta-hp-card.card-blue',redCards:'.acta-hp-card.card-red'};
   const iconKeys=Object.entries(iconFields).filter(([k,selector])=>c.matches(selector)||c.querySelector(selector)).map(([k])=>k);
   const keys=[...new Set([...values.flatMap(v=>Object.keys(fields).filter(k=>fields[k].test(norm(v)))),...iconKeys])];
   return keys.length===1?keys[0]:'unknown';
 };
 const header=tb=>tb.querySelector('thead tr:last-child')||[...tb.rows].find(r=>[...r.cells].some(c=>c.tagName==='TH'));
 const expand=(row,fn)=>[...row.cells].flatMap(c=>Array(Math.max(1,c.colSpan)).fill(fn(c)));
 const get=(cols,cells,k)=>cols.filter(x=>x===k).length===1?cells[cols.indexOf(k)]:null;
 const val=c=>c===null?null:norm(text(c));
 const integer=c=>c&&/^\d{1,3}$/.test(val(c))?Number(val(c)):null;
 const shape={},sideEvidence={},out=[];
 const bump=(o,k)=>o[k]=(o[k]||0)+1;
 const sideFor=tb=>{
   // Require exact team label in a one-roster ancestor, not just table order.
   for(let p=tb.parentElement;p&&p!==scope;p=p.parentElement){
     if(p.querySelectorAll('.sidgad-roster-table').length!==1)break;
     const candidates=[...p.querySelectorAll('.sidgad-team-roster-header,.sidgad-modal-team-name,.sidgad-team-link')].filter(vis);
     const matches=Object.keys(teams).filter(k=>teams[k]&&candidates.some(e=>[e,...e.querySelectorAll('*')].some(x=>norm(text(x))===norm(teams[k]))));
     if(matches.length===1)return {side:matches[0],method:'exact_team_header'};
   }
   return {side:null,method:'unresolved'};
 };
 const tables=mode==='summary'?[...scope.querySelectorAll('.sidgad-roster-table')]:[...scope.querySelectorAll('.sidgad-acta-hoja table')];
 for(const tb of tables.filter(vis)){
   const h=header(tb);if(!h)continue;
   const cols=expand(h,field);
   if(!cols.includes('number')||!cols.includes('goalkeeper'))continue;
   const binding=mode==='summary'?sideFor(tb):{side:null,method:'official'};
   bump(sideEvidence,binding.method);
   for(const row of [...tb.rows].filter(r=>r!==h&&vis(r)&&[...r.cells].some(c=>c.tagName==='TD'))){
     const cells=expand(row,c=>c);
     bump(shape,cols.length+':'+cells.length);
     if(cells.length!==cols.length||[...row.cells].some(c=>c.rowSpan!==1))continue;
     const shirt=integer(get(cols,cells,'number'));
     if(shirt===null)continue;
     const p=val(get(cols,cells,'goalkeeper')),c=val(get(cols,cells,'captain'));
     const stats={};for(const k of ['goals','assists','yellowCards','blueCards','redCards']){
       const n=integer(get(cols,cells,k));if(n!==null)stats[k]=n;
     }
     const r={shirtNumber:shirt,stats};
     if(p==='p'||p==='')r.position=p==='p'?'goalkeeper':'field';
     if(c==='c'||c==='')r.captain=c==='c';
     if(mode==='summary'){
       const links=[...row.querySelectorAll('a.sidgad-player-link[href]')].filter(vis).map(a=>{
         try{const u=new URL(a.getAttribute('href'),document.baseURI);const id=u.searchParams.get('jugador');
           if(u.protocol==='https:'&&/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(u.hostname)&&/^[1-9]\d*$/.test(id||''))return {id,a};
         }catch{}return null;
       }).filter(Boolean);
       if(links.length!==1)continue;
       const {id,a}=links[0],last=text(a.querySelector('.sidgad-player-last')),first=text(a.querySelector('.sidgad-player-first'));
       r.playerId=id;r.name=first&&last?first+' '+last:text(a);
       r.nameKeys=[...new Set([norm(r.name),norm(text(a)),norm(last+' '+first)].filter(Boolean))];
       r.side=binding.side;r.teamName=binding.side?teams[binding.side]:null;
       // Captain badge is structural evidence only until its P/C meaning is confirmed.
       r.captainBadge=!!row.querySelector('.sidgad-captain-badge');
       out.push(r);
     }else{
       // Official acta has no IDs. Only match exact name cell + shirt number.
       r.nameKeys=[...new Set([...row.cells].map(x=>norm(text(x))).filter(x=>x&&/[a-z]/.test(x)))];
       out.push(r);
     }
   }
 }
 return {rows:out,shapes:shape,sideEvidence};
}"""
def ingest_appearances(doc,league,match,summary,official,stamp):
    report={"summaryRows":len(summary),"officialRows":len(official),"sideResolved":0,"officialMatched":0,"captainsMarked":0,"conflicts":0,"stored":0}
    seen=set()
    for r in summary:
        pid=r.get("playerId");side=r.get("side");name=r.get("name","").strip()
        if side not in {"home","away"} or not numeric(pid) or not name or len(name)>200:continue
        report["sideResolved"]+=1
        key="|".join([doc["seasonId"],league,match,side,pid])
        if key in seen:report["conflicts"]+=1;continue
        seen.add(key)
        p=doc["players"].setdefault(pid,{"playerId":pid,"name":name,"nameVariants":[name],"firstSeenAt":stamp,"lastSeenAt":stamp})
        p["nameVariants"]=sorted(set(p["nameVariants"]+[name]));p["lastSeenAt"]=stamp
        a={"seasonId":doc["seasonId"],"leagueId":league,"matchId":match,"side":side,"playerId":pid,"participation":"listed","actaUrl":BASE+"?"+urlencode({"liga":league,"vista":"calendar","partido":match}),"source":"FECAPA:acta_resum","checkedAt":stamp,"shirtNumber":r["shirtNumber"]}
        if r.get("teamName"):a["teamName"]=r["teamName"]
        if r.get("position") in {"goalkeeper","field"}:a["position"]=r["position"]
        stats=dict(r.get("stats",{}))
        matches=[o for o in official if o["shirtNumber"]==r["shirtNumber"] and set(o["nameKeys"])&set(r["nameKeys"])]
        # Reject ambiguous matches in either direction.
        if len(matches)==1:
            o=matches[0]
            reverse=[x for x in summary if x["shirtNumber"]==o["shirtNumber"] and set(x["nameKeys"])&set(o["nameKeys"])]
            if len(reverse)==1:
                report["officialMatched"]+=1
                if "captain" in o:a["captain"]=o["captain"];report["captainsMarked"]+=int(o["captain"])
                for k,v in o.get("stats",{}).items():
                    if k in stats and stats[k]!=v:stats.pop(k);report["conflicts"]+=1
                    else:stats[k]=v
        if stats:a["stats"]=stats
        prev=doc["matchAppearances"].get(key)
        if prev:
            if any(prev.get(k)!=a.get(k) for k in ("shirtNumber","position","captain","stats","teamName")):
                report["conflicts"]+=1
                continue
        doc["matchAppearances"][key]=a;report["stored"]+=1
    return report

async def main():
    data=json.loads(Path("zonaok-actes.json").read_text())
    fixtures=data["fixtures"]
    targets=[{"league":"4786","id":"152361","view":"plantillas","filter":"12597"},{"league":"4786","id":"152361","view":"calendar"},{"league":"4786","id":"152361","view":"calendar","filter":"12597"}]
    for league in ("4774","4775","4789"):
        m=next((x for x in fixtures if str(x.get("league"))==league and re.fullmatch(r"[1-9]\d*",str(x.get("id") or ""))),None)
        if m:targets.append({"league":league,"id":str(m["id"]),"view":"calendar"})
    report={"schema":"zonaok-actes-jugadors-diagnostic-v1","source":"FECAPA","candidateActes":len(fixtures),"probes":[],"personalRecordsPersisted":False}
    candidate=empty("41")
    captured=[]
    async with async_playwright() as pw:
        browser,ctx=await chromium_context(pw)
        try:
            for target in targets:
                page=await ctx.new_page()
                result={"leagueId":target["league"],"matchId":target["id"],"view":target["view"],"withTeamFilter":bool(target.get("filter"))}
                try:
                    q={"liga":target["league"],"vista":target["view"]}
                    if target.get("filter"):q["filtro"]=target["filter"]
                    q["partido"]=target["id"]
                    response=await page.goto(BASE+"?"+urlencode(q),wait_until="domcontentloaded",timeout=30000)
                    result["httpStatus"]=response.status if response else None
                    previous=None;stable=0
                    for _ in range(35):
                        probe=await page.evaluate(PROBE,{"league":target["league"],"match":target["id"]})
                        sig=json.dumps(probe,sort_keys=True)
                        stable=stable+1 if sig==previous and probe.get("actaScope") and (probe.get("rows") or probe.get("divBlocks")) else 1
                        previous=sig
                        if stable>=4:break
                        await page.wait_for_timeout(700)
                    result["diagnostic"]=probe
                    modal=page.locator(".sidgad-match-modal:visible")
                    result["tabProbes"]=[]
                    summary_rows=[];official_rows=[]
                    result["captureShapes"]={}
                    if await modal.count()==1:
                        tabs=modal.locator(".sidgad-modal-tab-btn:visible")
                        for index in range(min(await tabs.count(),4)):
                            tab_report={"index":index}
                            try:
                                await tabs.nth(index).click(timeout=10000)
                                await page.wait_for_timeout(3000)
                                previous=None;stable=0
                                for _ in range(24):
                                    probe=await page.evaluate(PROBE,{"league":target["league"],"match":target["id"]})
                                    sig=json.dumps(probe,sort_keys=True)
                                    stable=stable+1 if sig==previous and probe.get("actaScope") else 1
                                    previous=sig
                                    if stable>=4:break
                                    await page.wait_for_timeout(700)
                                tab_report["diagnostic"]=probe
                                mode="summary" if probe.get("modalClassCounts",{}).get("sidgad-roster-table") else "official" if probe.get("modalClassCounts",{}).get("sidgad-acta-hoja") else None
                                if mode:
                                    raw=await page.evaluate(CAPTURE,{"league":target["league"],"mode":mode})
                                    result["captureShapes"][mode]={"rows":len(raw["rows"]),"shapes":raw["shapes"],"sideEvidence":raw["sideEvidence"]}
                                    if mode=="summary":summary_rows=raw["rows"]
                                    else:official_rows=raw["rows"]
                            except Exception as e:tab_report["errorType"]=type(e).__name__
                            result["tabProbes"].append(tab_report)
                    if summary_rows:
                        captured.append((target["league"],target["id"],summary_rows,official_rows))
                        result["fusion"]=ingest_appearances(candidate,target["league"],target["id"],summary_rows,official_rows,now())
                except Exception as e:result["errorType"]=type(e).__name__
                finally:await page.close()
                report["probes"].append(result)
        finally:await ctx.close();await browser.close()
    report["actaScopesFound"]=sum(bool(x.get("diagnostic",{}).get("actaScope")) for x in report["probes"])
    report["actaTablesFound"]=sum(len(x.get("diagnostic",{}).get("tables",[])) for x in report["probes"])
    report["divBlocksFound"]=sum(len(x.get("diagnostic",{}).get("divBlocks",[])) for x in report["probes"])
    report["tabsRead"]=sum(bool(t.get("diagnostic",{}).get("actaScope")) for x in report["probes"] for t in x.get("tabProbes",[]))
    report["maxPlayerLinksPerView"]=max((d.get("playerLinks",0) for x in report["probes"] for d in [x.get("diagnostic",{})]+[t.get("diagnostic",{}) for t in x.get("tabProbes",[])]),default=0)
    verify_master(candidate)
    report["masterFusion"]={"players":len(candidate["players"]),"appearances":len(candidate["matchAppearances"]),"fieldCoverage":{}}
    for a in candidate["matchAppearances"].values():
        for k in ("shirtNumber","position","captain","teamName"):
            if k in a:report["masterFusion"]["fieldCoverage"][k]=report["masterFusion"]["fieldCoverage"].get(k,0)+1
        for k in a.get("stats",{}):
            key="stats."+k;report["masterFusion"]["fieldCoverage"][key]=report["masterFusion"]["fieldCoverage"].get(key,0)+1
    if candidate["matchAppearances"]:
        report["masterFusion"]["persistence"]=persistence_probe(candidate)
        second=copy.deepcopy(candidate)
        for league,match,summary,official in captured:ingest_appearances(second,league,match,summary,official,now())
        verify_master(second)
        report["masterFusion"]["actaReimportNoDuplicates"]=set(candidate["matchAppearances"])==set(second["matchAppearances"]) and set(candidate["players"])==set(second["players"])
    Path("actes-jugadors-diagnostic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["masterFusion"]["appearances"] and report["masterFusion"].get("actaReimportNoDuplicates") else 2
if __name__=="__main__":raise SystemExit(asyncio.run(main()))
