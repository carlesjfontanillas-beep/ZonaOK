#!/usr/bin/env python3
"""Lectura oficial FECAPA independent: només catàleg d'equips, sense resultats."""
import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from zonaok_classificacions_auto import read_league, category_name, slug, ROOT

async def run(args):
    from playwright.async_api import async_playwright
    doc=json.loads(Path(args.standings).read_text(encoding='utf-8'))
    groups=doc['competitions']
    ids=sorted({str(g['leagueId']) for g in groups.values() if g.get('leagueId')},key=int)
    out={}
    diagnostic=[]
    sem=asyncio.Semaphore(3)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=False,args=['--no-sandbox'])
        context=await browser.new_context(locale='ca-ES',timezone_id='Europe/Madrid',viewport={'width':1360,'height':980})
        async def one(lid):
            async with sem:
                expected=sum(str(g.get('leagueId'))==lid for g in groups.values())
                found,errors,warnings=await read_league(context,lid,expected)
                for g in found:
                    out[lid+':'+slug(g['name'])]={'leagueId':lid,'name':g['name'],'category':category_name(g['name']),'standings':g['rows']}
                rows=[r for g in found for r in g['rows']]
                entry={'leagueId':lid,'groups':len(found),'expectedGroups':expected,'teams':len(rows),
                       'aliases':sum(bool(r.get('shortTeam')) for r in rows),'teamIds':sum(bool(r.get('teamId')) for r in rows),
                       'warnings':warnings,'errors':errors}
                diagnostic.append(entry)
                print(json.dumps(entry,ensure_ascii=False),flush=True)
        await asyncio.gather(*(one(lid) for lid in ids))
        await browser.close()
    report={'source':ROOT,'capturedAt':datetime.now(timezone.utc).isoformat(),'leagues':sorted(diagnostic,key=lambda x:int(x['leagueId'])),
            'stats':{'leagues':len(ids),'groups':len(out),'teams':sum(x['teams'] for x in diagnostic),'aliases':sum(x['aliases'] for x in diagnostic),'teamIds':sum(x['teamIds'] for x in diagnostic)}}
    Path(args.capture).write_text(json.dumps({'competitions':out},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['stats'],ensure_ascii=False),flush=True)
    if not out:raise SystemExit('Cap classificació llegida')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--standings',default='zonaok-classificacions.json')
    p.add_argument('--capture',default='captura-equivalencies.json')
    p.add_argument('--report',default='diagnostic-equivalencies.json')
    asyncio.run(run(p.parse_args()))
