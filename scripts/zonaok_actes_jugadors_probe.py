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
 const scopes=[...document.querySelectorAll('[class*="sidgad"][class*="acta"],[class*="sidgad"][class*="partido-modal"],[role="dialog"],[class*="sidgad"][class*="match-overlay"]')].filter(visible);
 // Never treat the underlying competition roster as acta evidence.
 const scope=scopes.filter(s=>s.querySelector('table')).sort((a,b)=>b.querySelectorAll('table').length-a.querySelectorAll('table').length)[0]||scopes[0];
 const classes={};for(const e of document.querySelectorAll('[class*="sidgad"]'))if(visible(e))for(const c of e.classList)if(/^sidgad-[a-z-]{2,70}$/.test(c)&&/acta|partido|match|lineup|alineacio|overlay|modal/.test(c))classes[c]=(classes[c]||0)+1;
 if(!scope)return {actaScope:false,classes};
 const tables=[];
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
 return {actaScope:true,classes,tables,labels,playerLinks:tables.reduce((n,t)=>n+t.playerLinks,0),rows:tables.reduce((n,t)=>n+t.rows,0)};
}"""
async def main():
    data=json.loads(Path("zonaok-actes.json").read_text())
    fixtures=data["fixtures"]
    targets=[{"league":"4786","id":"152361","view":"plantillas","filter":"12597"},{"league":"4786","id":"152361","view":"calendar"}]
    for league in ("4774","4775","4789"):
        m=next((x for x in fixtures if str(x.get("league"))==league and re.fullmatch(r"[1-9]\d*",str(x.get("id") or ""))),None)
        if m:targets.append({"league":league,"id":str(m["id"]),"view":"calendar"})
    report={"schema":"zonaok-actes-jugadors-diagnostic-v1","source":"FECAPA","candidateActes":len(fixtures),"probes":[],"personalRecordsPersisted":False}
    async with async_playwright() as pw:
        browser,ctx=await chromium_context(pw)
        try:
            for target in targets:
                page=await ctx.new_page()
                result={"leagueId":target["league"],"matchId":target["id"],"view":target["view"]}
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
                        stable=stable+1 if sig==previous and probe.get("actaScope") and probe.get("rows") else 1
                        previous=sig
                        if stable>=4:break
                        await page.wait_for_timeout(700)
                    result["diagnostic"]=probe
                except Exception as e:result["errorType"]=type(e).__name__
                finally:await page.close()
                report["probes"].append(result)
        finally:await ctx.close();await browser.close()
    report["actaScopesFound"]=sum(bool(x.get("diagnostic",{}).get("actaScope")) for x in report["probes"])
    report["actaTablesFound"]=sum(len(x.get("diagnostic",{}).get("tables",[])) for x in report["probes"])
    Path("actes-jugadors-diagnostic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["actaTablesFound"] else 2
if __name__=="__main__":raise SystemExit(asyncio.run(main()))
