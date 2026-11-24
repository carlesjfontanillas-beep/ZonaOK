#!/usr/bin/env python3
"""Bounded acta diagnostic. No personal names, IDs, dates of birth or row values are persisted."""
import asyncio,json,re
from pathlib import Path
from urllib.parse import urlencode
from playwright.async_api import async_playwright
from zonaok_fecapa_unificat import chromium_context
BASE="https://www.hoqueipatins.fecapa.cat/"
PROBE=r"""({league,match})=>{
 const visible=e=>!!e&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
 const norm=v=>String(v||'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().replace(/\s+/g,' ').trim();
 const known={number:/^(?:dorsal|num|numero|numero de dorsal|n[º°])$/,position:/^(?:posicio|posicion|rol|demarcacio|demarcacion)$/,player:/^(?:jugador|jugadora|nom|nombre|nom i cognoms|nombre y apellidos)$/,played:/^(?:pj|partits jugats|partidos jugados)$/,goals:/^(?:g|gols?|goles?)$/,assists:/^(?:a|assistencies|asistencias)$/,yellowCards:/^(?:ta|targetes grogues|tarjetas amarillas)$/,blueCards:/^(?:tb|targetes blaves|tarjetas azules)$/,redCards:/^(?:tr|targetes vermelles|tarjetas rojas)$/,minutes:/^(?:min|minuts|minutos)$/,starter:/^(?:titular|titulars|titulares)$/,substitute:/^(?:suplent|suplente|suplents|suplentes)$/,penalties:/^(?:penals|penaltis|penalties)$/,saves:/^(?:aturades|paradas)$/,role:/^(?:porter|portero|portera|jugador de pista|jugador de campo)$/};
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
   let playerLinks=0,linkedRows=0;const populated={};
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
     });
   }
   tables.push({columns,rows:rows.length,playerLinks,linkedRows,populated});
 }
 const labels={};
 for(const e of scope.querySelectorAll('th,h2,h3,h4,dt,label,[title],[aria-label]')){
   if(!visible(e))continue;
   for(const v of [e.innerText,e.title,e.getAttribute('aria-label')]){const k=field(v);if(k)labels[k]=(labels[k]||0)+1}
 }
 return {actaScope:true,classes,tabs,tables,divBlocks,labels,modalClassCounts,modalDataAttributes,playerLinks:playerLinksTotal,uniquePlayerIds:ids.size,matchContextLinks,rows:tables.reduce((n,t)=>n+t.rows,0)+divBlocks.reduce((n,t)=>n+t.rows,0)};
}"""
async def main():
    data=json.loads(Path("zonaok-actes.json").read_text())
    fixtures=data["fixtures"]
    targets=[{"league":"4786","id":"152361","view":"plantillas","filter":"12597"},{"league":"4786","id":"152361","view":"calendar"},{"league":"4786","id":"152361","view":"calendar","filter":"12597"}]
    for league in ("4774","4775","4789"):
        m=next((x for x in fixtures if str(x.get("league"))==league and re.fullmatch(r"[1-9]\d*",str(x.get("id") or ""))),None)
        if m:targets.append({"league":league,"id":str(m["id"]),"view":"calendar"})
    report={"schema":"zonaok-actes-jugadors-diagnostic-v1","source":"FECAPA","candidateActes":len(fixtures),"probes":[],"personalRecordsPersisted":False}
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
                            except Exception as e:tab_report["errorType"]=type(e).__name__
                            result["tabProbes"].append(tab_report)
                except Exception as e:result["errorType"]=type(e).__name__
                finally:await page.close()
                report["probes"].append(result)
        finally:await ctx.close();await browser.close()
    report["actaScopesFound"]=sum(bool(x.get("diagnostic",{}).get("actaScope")) for x in report["probes"])
    report["actaTablesFound"]=sum(len(x.get("diagnostic",{}).get("tables",[])) for x in report["probes"])
    report["divBlocksFound"]=sum(len(x.get("diagnostic",{}).get("divBlocks",[])) for x in report["probes"])
    report["tabsRead"]=sum(bool(t.get("diagnostic",{}).get("actaScope")) for x in report["probes"] for t in x.get("tabProbes",[]))
    report["maxPlayerLinksPerView"]=max((d.get("playerLinks",0) for x in report["probes"] for d in [x.get("diagnostic",{})]+[t.get("diagnostic",{}) for t in x.get("tabProbes",[])]),default=0)
    Path("actes-jugadors-diagnostic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["actaScopesFound"] and (report["actaTablesFound"] or report["divBlocksFound"] or report["tabsRead"]) else 2
if __name__=="__main__":raise SystemExit(asyncio.run(main()))
