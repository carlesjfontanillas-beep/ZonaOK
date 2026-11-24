#!/usr/bin/env python3
"""Diagnòstic Playwright no destructiu de les targetes del calendari FECAPA."""
import asyncio
import json
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright

BASE = "https://www.hoqueipatins.fecapa.cat/"
LEAGUES = ("4789", "4786", "4774")

async def inspect(page, lid):
    report={"leagueId":lid,"url":BASE+f"?liga={lid}&vista=calendar","cards":0,"clicks":[]}
    events=[]
    page.on("framenavigated", lambda fr: events.append({"type":"frame", "url":fr.url[:350]}) if fr==page.main_frame else None)
    page.on("popup", lambda p: events.append({"type":"popup","url":p.url[:350]}))
    page.on("response", lambda r: events.append({"type":"response","url":r.url[:350],"status":r.status})
            if re.search(r"partido=|idp=|fecapa_gr_|(?:/acta|/report)",r.url,re.I) and len(events)<60 else None)
    try:
        await page.goto(report["url"], wait_until="domcontentloaded",timeout=45000)
        await page.wait_for_timeout(1500)
        report["surface"]=await page.evaluate("""() => {
          const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
          const matchish=[...document.querySelectorAll('[class*="calendar"],[class*="calend"],[class*="partido"],[class*="match"]')];
          return {
            title:document.title,url:location.href,body:(document.body?.innerText||'').slice(0,7500),
            totalMatchish:matchish.length,
            visibleMatchish:matchish.filter(visible).slice(0,45).map(e=>({tag:e.tagName,cls:String(e.className).slice(0,180),id:e.id,
                text:(e.innerText||'').slice(0,320),html:e.outerHTML.slice(0,550)})),
            allButtons:[...document.querySelectorAll('button')].filter(visible).slice(0,35).map(e=>({text:(e.innerText||'').slice(0,120),cls:e.className})),
            officialAnchors:[...document.querySelectorAll('a[href]')].filter(a=>/partido=|idp=|fecapa_gr_|calendar/i.test(a.href)).slice(0,40).map(a=>({href:a.href,text:(a.innerText||'').slice(0,70),visible:visible(a)}))
          };
        }""")
        buttons=page.locator(".sidgad-partido-fila:visible")
        report["cards"]=await buttons.count()
        for index in range(min(3,report["cards"])):
            item={"index":index,"beforeUrl":page.url}
            btn=buttons.nth(index)
            try:
                item["before"]=await btn.evaluate("""el=>({
                    html:el.outerHTML.slice(0,1300),
                    text:(el.innerText||'').slice(0,280),
                    attributes:Object.fromEntries([...el.attributes].map(a=>[a.name,a.value]))
                })""")
                before=len(events)
                await btn.click(timeout=8000)
                await page.wait_for_timeout(900)
                item["afterUrl"]=page.url
                item["after"]=await page.evaluate("""() => ({
                    modal:[...document.querySelectorAll('[role=dialog],dialog,.modal,.sidgad-modal,#sidgad-modal,.sidgad-ficha-partido')]
                      .filter(e=>{const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'})
                      .slice(0,5).map(e=>({id:e.id,cls:e.className,text:(e.innerText||'').slice(0,700),html:e.outerHTML.slice(0,2300)})),
                    matchAnchors:[...document.querySelectorAll('a[href]')]
                      .filter(a=>/partido=|idp=|fecapa_gr_|acta/i.test(a.href)).slice(0,15).map(a=>({text:a.innerText.slice(0,100),href:a.href})),
                    matchFrames:[...document.querySelectorAll('iframe[src]')].map(f=>f.src).slice(0,8)
                })""")
                item["networkEvents"]=events[before:before+20]
            except Exception as exc:
                item["error"]=str(exc)[:350]
            report["clicks"].append(item)
            # Independent page state for each investigated card
            if index+1<min(3,report["cards"]):
                await page.goto(report["url"],wait_until="domcontentloaded",timeout=45000)
                await page.wait_for_timeout(300)
                buttons=page.locator(".sidgad-partido-fila:visible")
    except Exception as exc:
        report["error"]=str(exc)[:350]
    return report

async def main():
    output={"checkedAt":datetime.now(timezone.utc).isoformat(),"kind":"diagnostic-only","leagues":[]}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=False,args=["--no-sandbox"])
        context=await browser.new_context(locale="ca-ES",timezone_id="Europe/Madrid")
        try:
            for lid in LEAGUES:
                page=await context.new_page()
                output["leagues"].append(await inspect(page,lid))
                await page.close()
        finally:
            await context.close();await browser.close()
    with open("diagnostic-calendar-click-idp.json","w",encoding="utf-8") as f:
        json.dump(output,f,ensure_ascii=False,indent=2)
    for league in output["leagues"]:
        print(f"Lliga {league['leagueId']}: {league.get('cards')} targetes; "+", ".join(
            f"clic {x['index']}: URL {x.get('afterUrl','error')}" for x in league.get('clicks',[])),flush=True)

if __name__=="__main__":
    asyncio.run(main())
