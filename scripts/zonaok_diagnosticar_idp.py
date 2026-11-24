#!/usr/bin/env python3
"""Inspecció no destructiva de la càrrega de calendaris FECAPA. Cap publicació."""
import asyncio
import json
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright

ROOT="https://www.hoqueipatins.fecapa.cat/"
LEAGUES=("4789","4786","4774")
JS=r"""() => {
  const T=e=>String(e?.innerText||e?.textContent||'').replace(/\s+/g,' ').trim();
  const vis=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();
    return s.display!=='none'&&s.visibility!=='hidden'&&r.width>1&&r.height>1};
  const els=[...document.querySelectorAll('button,a,[class*="calendar"],[class*="calend"],[class*="partido"],[class*="jornada"],[id*="calend"],[id*="partido"]')];
  const candidates=els.filter(vis).filter(e=>/partido|jornada|calend|equip|partit|result/i.test(
    String(e.className||'')+' '+e.id+' '+T(e).slice(0,60))).slice(0,40);
  const spinner=[...document.querySelectorAll('*')].filter(e=>e.children.length<3&&vis(e)&&
    /^CARREGANT$|^CARGANDO$|^LOADING$/i.test(T(e))).slice(0,8);
  return {
    title:document.title,url:location.href,ready:document.readyState,
    body:(document.body?.innerText||'').slice(0,7000),
    spinners:spinner.map(e=>({html:e.parentElement?.outerHTML.slice(0,1300),id:e.id,cls:e.className})),
    totalCards:document.querySelectorAll('.sidgad-partido-fila').length,
    visibleCards:[...document.querySelectorAll('.sidgad-partido-fila')].filter(vis).slice(0,15).map(e=>({
      text:T(e).slice(0,250),html:e.outerHTML.slice(0,1000)
    })),
    visibleCandidates:candidates.map(e=>({tag:e.tagName,id:e.id,cls:String(e.className||'').slice(0,150),
      text:T(e).slice(0,190),html:e.outerHTML.slice(0,540)})),
    officialAnchors:[...document.querySelectorAll('a[href]')].filter(a=>/partido=|idp=|fecapa_gr_/i.test(a.href))
      .slice(0,20).map(e=>({href:e.href,visible:vis(e),text:T(e).slice(0,90)})),
    scriptSrc:[...document.querySelectorAll('script[src]')].map(x=>x.src).slice(0,35)
  };
}""";

async def inspect(page, league):
    item={"leagueId":league,"url":ROOT+f"?liga={league}&vista=calendar",
          "samples":[],"requests":[],"errors":[],"status":None}
    responses=[]
    def response(r):
        u=r.url
        if len(responses)>=250:return
        if re.search(r"hoqueipatins|sidgad",u,re.I):
            responses.append({"status":r.status,"type":r.request.resource_type,"url":u[:350]})
    def failed(r):
        if len(item["errors"])<35:
            item["errors"].append({"type":"requestfailed","url":r.url[:320],"error":r.failure})
    page.on("response",response)
    page.on("requestfailed",failed)
    page.on("pageerror",lambda err: item["errors"].append({"type":"pageerror","message":str(err)[:450]}) if len(item["errors"])<35 else None)
    page.on("console",lambda msg: item["errors"].append({"type":"console","message":msg.text[:450]})
            if msg.type=="error" and len(item["errors"])<35 else None)
    try:
        result=await page.goto(item["url"],wait_until="domcontentloaded",timeout=45000)
        item["status"]=result.status if result else None
        last=0
        for seconds in (2,10,25,42):
            await page.wait_for_timeout((seconds-last)*1000)
            last=seconds
            snap=await page.evaluate(JS)
            item["samples"].append({"seconds":seconds,"surface":snap})
            print(f"Lliga {league} després de {seconds}s: visibles={len(snap['visibleCards'])}, "+
                  f"totals={snap['totalCards']}, carregant={len(snap['spinners'])}, "+
                  f"candidats={len(snap['visibleCandidates'])}",flush=True)
            # If calendar finally reveals fixture components, that's useful; no need to wait more.
            if snap["visibleCards"] or (
                seconds>=10 and len(snap["body"])>1800 and not snap["spinners"]):
                break
        item["calendarRows"]=await page.evaluate("""() => [...document.querySelectorAll('tr.sidgad-calendario-partido')].slice(0,4).map(tr=>({
          text:(tr.innerText||'').slice(0,500),
          html:tr.outerHTML.slice(0,10000),
          attrs:Object.fromEntries([...tr.attributes].map(a=>[a.name,a.value])),
          cells:[...tr.cells].map(td=>({cls:td.className,text:(td.innerText||'').slice(0,170),
            links:[...td.querySelectorAll('a[href]')].map(a=>({href:a.href,text:a.innerText})),
            attrs:Object.fromEntries([...td.attributes].map(a=>[a.name,a.value]))}))
        }))""")
        item["visibleCalendarRows"]=await page.locator("tr.sidgad-calendario-partido:visible").count()
        item["requests"]=responses
    except Exception as exc:
        item["errors"].append({"type":"exception","message":str(exc)[:450]})
    return item

async def main():
    d={"checkedAt":datetime.now(timezone.utc).isoformat(),"kind":"wait-and-network-diagnostic-only","leagues":[]}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=False,args=["--no-sandbox"])
        context=await browser.new_context(locale="ca-ES",timezone_id="Europe/Madrid")
        try:
            for league in LEAGUES:
                page=await context.new_page()
                d["leagues"].append(await inspect(page,league))
                await page.close()
        finally:
            await context.close()
            await browser.close()
    with open("diagnostic-calendar-click-idp.json","w",encoding="utf-8") as f:
        json.dump(d,f,ensure_ascii=False,indent=2)
    print("Diagnòstic escrit (cap JSON productiu modificat)",flush=True)

if __name__=="__main__":
    asyncio.run(main())
