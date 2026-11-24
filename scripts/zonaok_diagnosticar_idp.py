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
        await page.wait_for_selector(".sidgad-partido-fila",timeout=20000)
        await page.wait_for_timeout(900)
        buttons=page.locator(".sidgad-partido-fila")
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
                await page.wait_for_selector(".sidgad-partido-fila",timeout=20000)
                await page.wait_for_timeout(300)
                buttons=page.locator(".sidgad-partido-fila")
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
