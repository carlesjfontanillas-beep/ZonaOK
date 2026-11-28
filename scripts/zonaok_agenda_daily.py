#!/usr/bin/env python3
"""Daily FECAPA Agenda: capture once, reapply on latest main, preserve existing scores."""
import argparse, asyncio, copy, json, os, re
from collections import defaultdict, Counter
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from zonaok_fecapa_unificat import (CANONICAL, SEASON, load_unified, norm, clean, score_tuple, check_iso, check_time, check_when, utc_now, write_compatibility, canonicalize, chromium_context)
from zonaok_agenda_dates_review import capture
from zonaok_fecapa_unificat import invalid_fixture_team, state_competition, state_team_key

MADRID=ZoneInfo('Europe/Madrid')
EXCLUDED=re.compile(r'AJORN|APLAZ|SUSP[EÈ]|SUSPEND|CANCEL|ANUL',re.I)
LIVE=re.compile(r'EN JOC|EN DIRECTE|EN DIRECTO|LIVE|PLAYING|PRIMERA PART|SEGONA PART|DESCANS',re.I)
FINAL=re.compile(r'\b(FINAL|FINALITZAT|FINALIZADO|ACABAT|ACABADO|FINISHED|FULL TIME)\b',re.I)
def pair(r):
    comp=state_competition(r.get('competition'))
    if comp:return (comp,state_team_key(r.get('home'),comp),state_team_key(r.get('away'),comp))
    return tuple(norm(r.get(k)) for k in ('competition','home','away'))
def slot(r):return (r.get('iso'),r.get('time'))
def key(r):return (*pair(r),*slot(r))
def idpair(r):return tuple(clean(r.get(k)) for k in ('leagueId','matchId'))
def safe(r):return not invalid_fixture_team(r) and all(pair(r)) and check_iso(r.get('iso')) and check_time(r.get('time')) and (not score_tuple(r) or all(0<=r[k]<=199 for k in ('homeScore','awayScore')))
def no_conflict(a,b):
    return not any(x and y and x!=y for x,y in zip(idpair(a),idpair(b)))
def recent(r,cut):return clean(r.get('iso'))>=cut
def index(rows,fn,indices):
    out=defaultdict(list)
    for i in indices:out[fn(rows[i])].append(i)
    return out
def reconcile_duplicate_pairs(doc,incoming,cut,captured):
    """Match the whole season, including official rows already used by exact matches.
    Never collapse distinct IDs, separate phases/groups, or contradictory scores.
    """
    from zonaok_agenda_reparacio_confirmats import repair
    old=doc['matches']
    oi=index(old,pair,range(len(old)))
    ni=index(incoming,pair,range(len(incoming)))
    specs=[]
    for k,indices in oi.items():
        if len(indices)<2 or state_competition(k[0]):continue
        targets=ni.get(k,[])
        if len(targets)!=1:continue
        b=incoming[targets[0]]
        group=[old[i] for i in indices]
        if not any(recent(a,cut) for a in group) and not recent(b,cut):continue
        if not all(no_conflict(a,b) for a in group):continue
        if any(a.get('lastAgendaAt') and check_when(a['lastAgendaAt'])>check_when(captured) for a in group):continue
        if any(slot(a)!=slot(b) and (score_tuple(a) or a.get('actaState')=='available' or FINAL.search(clean(a.get('status'))) or LIVE.search(clean(a.get('status')))) for a in group):continue
        if k==('BCN BENJAMI PLATA 3','CH LES FRANQUESES','UNIO ESPORTIVA D HORTA B'):continue
        # No need for a pre-existing exact slot. One official ordered pair
        # in the entire season is sufficient, subject to the ID/score guards.
        # For an alert, use the most recently observed old fixture, then the
        # latest old slot as a deterministic fallback. Keep all old slots in audit.
        a=max(group,key=lambda x:(x.get('lastAgendaAt') or '',slot(x)))
        specs.append({**{f:a[f] for f in ('competition','home','away')},
                      'oldIso':a['iso'],'oldTime':a['time'],'iso':b['iso'],'time':b['time'],
                      'approvedSlots':[list(slot(x)) for x in group],
                      'homeScore':None,'awayScore':None})
    if not specs:return doc,[],[]
    updated,audit=repair(doc,{'season':doc['season'],'sourceRun':os.environ.get('GITHUB_RUN_ID','daily'),'capturedAt':captured,'fixtures':specs})
    merged=[r for r in audit['details'] if r['status']=='merged']
    by_pair={tuple(r['fixture']):r for r in merged}
    for r in updated['matches']:
        detail=by_pair.get(pair(r))
        if not detail:continue
        r['lastAgendaAt']=captured
        if not any(slot(x)==slot(r) for x in detail['originalRows']):
            previous=tuple(detail['old'])
            r['agendaScheduleChange']={'previousIso':previous[0],'previousTime':previous[1],'capturedAt':captured,'proof':'unique-season-pair'}
            detail['scheduleChanged']=True
        detail['result']=copy.deepcopy(r)
    return updated,merged,[r for r in audit['details'] if r['status']=='review']


def merge(doc,packet):
    if packet.get('season')!=SEASON or packet.get('kind')!='agenda-daily':raise ValueError('invalid daily packet')
    captured=packet['capturedAt']; clock=check_when(captured);today=clock.astimezone(MADRID).date()
    cut=(today-timedelta(days=7)).isoformat()
    old=doc['matches']; incoming=packet['rows']
    if not incoming or any(not safe(r) for r in incoming):raise ValueError('invalid or empty source rows')
    if len(incoming)<.8*len(old):raise ValueError('incomplete source coverage')
    if sum(recent(r,cut) for r in incoming)<.8*sum(recent(r,cut) for r in old):raise ValueError('incomplete recent/future coverage')
    original_count=len(old)
    doc,duplicate_repairs,duplicate_reviews=reconcile_duplicate_pairs(doc,incoming,cut,captured)
    old=doc['matches']
    all_incoming_pairs=index(incoming,pair,range(len(incoming)))
    old_keys={key(a) for a in old}
    rows=copy.deepcopy(old); used_old=set();used_new=set(); links=[]
    # Stable official ID when available; the general Agenda normally has none.
    for fn,require in ((idpair,lambda k:all(k)),(key,lambda k:all(k))):
        oi=index(old,fn,(i for i in range(len(old)) if i not in used_old))
        ni=index(incoming,fn,(j for j in range(len(incoming)) if j not in used_new))
        for k,os in oi.items():
            ns=ni.get(k,[])
            if require(k) and len(os)==len(ns)==1 and no_conflict(old[os[0]],incoming[ns[0]]):
                i,j=os[0],ns[0];links.append((i,j,'exact'));used_old.add(i);used_new.add(j)
    # Match the entire season before deciding which changed fixtures are in scope.
    # An ordered pair must be unique in both directions after exact matches.
    oi=index(old,pair,(i for i in range(len(old)) if i not in used_old))
    ni=index(incoming,pair,(j for j in range(len(incoming)) if j not in used_new))
    for k,os in oi.items():
        ns=ni.get(k,[])
        if len(os)==len(ns)==1:
            i,j=os[0],ns[0];a,b=old[i],incoming[j]
            if no_conflict(a,b) and not score_tuple(a) and a.get('actaState')!='available' and not FINAL.search(clean(a.get('status'))) and not LIVE.search(clean(a.get('status'))):
                links.append((i,j,'unique-season-pair'));used_old.add(i);used_new.add(j)
    changes=[{'competition':d['result']['competition'],'home':d['result']['home'],'away':d['result']['away'],'previousIso':d['old'][0],'previousTime':d['old'][1],'iso':d['result']['iso'],'time':d['result']['time'],'leagueId':d['result'].get('leagueId'),'matchId':d['result'].get('matchId'),'proof':'unique-season-pair'} for d in duplicate_repairs if d.get('scheduleChanged')];recovered=[];conflicts=[];new=[]
    for i,j,proof in links:
        a,b=old[i],incoming[j];r=rows[i]
        if not (recent(a,cut) or recent(b,cut)):continue
        if a.get('lastAgendaAt') and check_when(a['lastAgendaAt'])>clock:continue
        if slot(a)!=slot(b):
            # User selected the latest of three conflicting records. Do not silently
            # revert that choice to the already known older source slot.
            if pair(a)==('BCN BENJAMI PLATA 3','CH LES FRANQUESES','UNIO ESPORTIVA D HORTA B') and slot(a)==('2026-11-29','10:45') and slot(b) in (('2026-11-28','15:00'),('2026-11-28','17:00')):
                conflicts.append({'reason':'approved_latest_date_disagrees_with_source','old':key(a),'incoming':key(b)})
                continue
            if score_tuple(a) or a.get('actaState')=='available' or LIVE.search(clean(a.get('status'))):
                conflicts.append({'reason':'schedule_of_started_or_scored_match','old':key(a),'incoming':key(b)})
            else:
                r['iso'],r['time']=slot(b)
                r['agendaScheduleChange']={'previousIso':a['iso'],'previousTime':a['time'],'capturedAt':captured,'proof':proof}
                changes.append({'competition':r['competition'],'home':r['home'],'away':r['away'],'previousIso':a['iso'],'previousTime':a['time'],'iso':r['iso'],'time':r['time'],'leagueId':r.get('leagueId'),'matchId':r.get('matchId'),'proof':proof})
        if clean(b.get('venue')) and clean(b.get('venue'))!=clean(a.get('venue')) and not score_tuple(a):r['venue']=b['venue']
        status=clean(b.get('status'))
        if status and EXCLUDED.search(status) and not score_tuple(a) and not LIVE.search(clean(a.get('status'))):r['status']=status
        elif status and EXCLUDED.search(clean(a.get('status'))) and not EXCLUDED.search(status):r['status']=status
        # The day after, a numeric official Agenda score is final evidence.
        if r['iso']<today.isoformat() and score_tuple(b) and not EXCLUDED.search(status or clean(r.get('status'))) and not LIVE.search(status):
            if not score_tuple(a):
                r.update(homeScore=b['homeScore'],awayScore=b['awayScore'],status='FINAL',scoreSource='Agenda',scoreUpdatedAt=captured,finalDetectedAt=captured,agendaRecoveredAt=captured)
                recovered.append({'iso':r['iso'],'time':r['time'],'competition':r['competition'],'home':r['home'],'away':r['away'],'homeScore':r['homeScore'],'awayScore':r['awayScore'],'leagueId':r.get('leagueId'),'matchId':r.get('matchId')})
            elif (a['homeScore'],a['awayScore'])!=(b['homeScore'],b['awayScore']):
                conflicts.append({'reason':'existing_score_differs','fixture':key(a),'existing':[a['homeScore'],a['awayScore']],'agenda':[b['homeScore'],b['awayScore']]})
        if r!=a:r['lastAgendaAt']=captured
    # New fixtures only if there is no unresolved old fixture with same teams/category.
    for j,b in enumerate(incoming):
        if j in used_new or not recent(b,cut):continue
        if any(i not in used_old for i in oi.get(pair(b),[])) or key(b) in old_keys:
            conflicts.append({'reason':'ambiguous_or_duplicate','incoming':key(b)});continue
        r=canonicalize(b);r['lastAgendaAt']=captured
        if r['iso']<today.isoformat() and score_tuple(r) and not EXCLUDED.search(clean(r.get('status'))) and not LIVE.search(clean(r.get('status'))):
            r.update(status='FINAL',scoreSource='Agenda',scoreUpdatedAt=captured,finalDetectedAt=captured,agendaRecoveredAt=captured)
        elif r['iso']>=today.isoformat() and score_tuple(r):
            # Never accept a speculative future score.
            r['homeScore']=r['awayScore']=None
        rows.append(r);new.append(key(r))
    for i,a in enumerate(old):
        if i not in used_old and recent(a,cut):conflicts.append({'reason':'not_uniquely_found_in_agenda','fixture':key(a),'possible':[slot(incoming[j]) for j in all_incoming_pairs.get(pair(a),[])]})
    prior_counts=Counter(key(r) for r in old);counts=Counter(key(r) for r in rows)
    if any(n>max(1,prior_counts[k]) for k,n in counts.items()):raise ValueError('new duplicate fixtures')
    rows.sort(key=lambda r:(r.get('iso',''),r.get('time',''),norm(r.get('competition')),norm(r.get('home'))))
    report={'schema':'zonaok-agenda-daily-report-v1','capturedAt':captured,'windowFrom':cut,'sourceRows':len(incoming),'catalogBefore':original_count,'catalogAfter':len(rows),'duplicateRepairs':duplicate_repairs,'duplicateReviews':duplicate_reviews,'duplicatesRemoved':sum(r['removed'] for r in duplicate_repairs),'scheduleChanges':changes,'recoveredResults':recovered,'newFixtures':new,'conflicts':conflicts,'scheduleChangeCount':len(changes),'recoveredResultCount':len(recovered),'newFixtureCount':len(new),'unresolvedCount':len(conflicts),'yesterdayMissingResults':[key(r) for r in rows if r.get('iso')==(today-timedelta(days=1)).isoformat() and not score_tuple(r) and not EXCLUDED.search(clean(r.get('status')))]}
    result={**doc,'matches':rows,'updatedAt':utc_now(),'sources':{**doc.get('sources',{}),'agenda':{**doc.get('sources',{}).get('agenda',{}),'capturedAt':captured,'mergedAt':utc_now(),'scope':'daily',**{k:report[k] for k in ('scheduleChangeCount','recoveredResultCount','newFixtureCount','unresolvedCount')}}}}
    result['stats']={**doc.get('stats',{}),'total':len(rows),'withScores':sum(score_tuple(r) for r in rows),'withActaLinks':sum(bool(r.get('actaUrl')) for r in rows),'verifiedActes':sum(r.get('actaState')=='available' for r in rows)}
    return result,report
def validate_publication(before,after,packet,report):
    """Allow only explicitly evidenced duplicate reductions, never arbitrary deletion."""
    old=before['matches']; new=after['matches']
    if before['season']!=after['season'] or before['season']!=packet['season']:
        raise ValueError('season mismatch')
    oi=index(old,pair,range(len(old))); ni=index(packet['rows'],pair,range(len(packet['rows']))); fi=index(new,pair,range(len(new)))
    removed=0; seen=set()
    for d in report['duplicateRepairs']:
        k=tuple(d['fixture'])
        if k in seen:raise ValueError('repeated audit pair')
        seen.add(k)
        original=[old[i] for i in oi.get(k,[])]
        official=[packet['rows'][i] for i in ni.get(k,[])]
        final=[new[i] for i in fi.get(k,[])]
        if len(original)<2 or len(official)!=1 or len(final)!=1 or slot(final[0])!=slot(official[0]):
            raise ValueError('duplicate audit without unique official fixture')
        enc=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False)
        if Counter(map(enc,original))!=Counter(map(enc,d['originalRows'])) or d['removed']!=len(original)-1:
            raise ValueError('duplicate audit does not match HEAD')
        removed+=d['removed']
    if removed!=report['duplicatesRemoved'] or len(new)!=len(old)-removed+report['newFixtureCount']:
        raise ValueError('unexplained row count change')
    if not {idpair(r) for r in old if all(idpair(r))}<={idpair(r) for r in new if all(idpair(r))}:
        raise ValueError('lost official identity')
    scores=lambda rows:{(pair(r),r['homeScore'],r['awayScore']) for r in rows if score_tuple(r)}
    if not scores(old)<=scores(new):raise ValueError('lost existing result')
    # Independently reapply the capture on HEAD. Compare fixture rows, not generated metadata.
    expected,expected_report=merge(before,packet)
    if expected['matches']!=new or expected_report['duplicatesRemoved']!=removed:
        raise ValueError('published rows differ from verified merge')
    return removed

def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
async def collect():
    from playwright.async_api import async_playwright
    doc=load_unified(CANONICAL); report={}
    async with async_playwright() as pw:
        browser,ctx=await chromium_context(pw)
        try:rows=await capture(ctx,report,doc['matches'])
        finally:await ctx.close();await browser.close()
    packet={'kind':'agenda-daily','season':SEASON,'capturedAt':utc_now(),'rows':[r for r in rows if safe(r)],'captureReport':report}
    write('captura-agenda-auto.json',packet);write('diagnostic-agenda-auto.json',report)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['collect','merge','validate']);args=parser.parse_args()
    if args.command=='collect':asyncio.run(collect());return
    packet=json.loads(Path('captura-agenda-auto.json').read_text())
    if args.command=='validate':
        import subprocess
        before=json.loads(subprocess.check_output(['git','show',f'HEAD:{CANONICAL}']))
        after=load_unified(CANONICAL)
        report=json.loads(Path('fusio-agenda-auto.json').read_text())
        removed=validate_publication(before,after,packet,report)
        print('Validació Agenda: duplicats justificats:',removed,'partits conservats:',len(after['matches']))
        print('Incidències restants:',json.dumps(report['conflicts'],ensure_ascii=False))
        return
    doc,report=merge(load_unified(CANONICAL),packet)
    write(CANONICAL,doc);write_compatibility(doc);write('fusio-agenda-auto.json',report)
    print(json.dumps({k:v for k,v in report.items() if not isinstance(v,list)},ensure_ascii=False))
if __name__=='__main__':main()
