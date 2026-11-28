#!/usr/bin/env python3
"""Approved schedule changes, with reversible audit and preservation of IDs/scores."""
import copy,json,re
from pathlib import Path
from zonaok_fecapa_unificat import CANONICAL,load_unified,norm,clean,score_tuple,check_when,utc_now,write_compatibility,make_match_url,official_match_url,check_iso,check_time
from zonaok_deduplicar_partits import identity,official_id

MANIFEST=Path('imports/agenda-reparacio-20261128-confirmats.json')
REPORT=Path('imports/agenda-reparacio-20261128-resultat.json')
def pair(r):return tuple(norm(r.get(k)) for k in ('competition','home','away'))
def slot(r):return (r.get('iso'),r.get('time'))
def present(v):return v is not None and v!=''
def scores(r):return (r['homeScore'],r['awayScore']) if score_tuple(r) else None
def repair(doc,manifest):
    if doc.get('season')!=manifest.get('season'):raise ValueError('season mismatch')
    rows=copy.deepcopy(doc['matches']); before=copy.deepcopy(rows); results=[]
    for spec in manifest['fixtures']:
        k=pair(spec); target=slot(spec); old=(spec['oldIso'],spec['oldTime'])
        entry={'fixture':list(k),'old':list(old),'official':list(target),'removed':0}
        if not check_iso(target[0]) or not check_time(target[1]):raise ValueError('invalid official slot')
        idx=[i for i,r in enumerate(rows) if pair(r)==k]
        group=[rows[i] for i in idx]
        entry['originalRows']=copy.deepcopy(group)
        if not group:
            entry.update(status='review',reason='not_found');results.append(entry);continue
        if any(slot(r) not in (old,target) for r in group):
            entry.update(status='review',reason='another_slot_not_in_review');results.append(entry);continue
        ids=[{identity(r)[n] for r in group if identity(r)[n]} for n in (0,1)]
        values={scores(r) for r in group if scores(r) is not None}
        source_score=scores(spec)
        if source_score is not None:values.add(source_score)
        if any(len(x)>1 for x in ids) or len(values)>1:
            entry.update(status='review',reason='different_official_ids_or_scores');results.append(entry);continue
        if any(r.get('actaUrl') and not official_match_url(r['actaUrl'],*identity(r)) for r in group):
            entry.update(status='review',reason='invalid_acta_link');results.append(entry);continue
        if any((r.get('homeScore') is None)!=(r.get('awayScore') is None) for r in group):
            entry.update(status='review',reason='partial_score');results.append(entry);continue
        if any(scores(r) is not None and slot(r)!=target for r in group) and source_score is None and not any(scores(r) is not None and slot(r)==target for r in group):
            entry.update(status='review',reason='old_slot_has_unconfirmed_score');results.append(entry);continue
        if any(r.get('actaState')=='available' and not official_id(r) for r in group):
            entry.update(status='review',reason='verified_acta_without_id');results.append(entry);continue
        if len(group)==1 and slot(group[0])==target:
            entry.update(status='already_correct',result=group[0]);results.append(entry);continue
        # Prefer the official slot; preserve verified acta and score metadata from any duplicate.
        ref=max(group,key=lambda r:(slot(r)==target,r.get('actaState')=='available',bool(official_id(r)),bool(scores(r)),sum(present(v) for v in r.values())))
        out=copy.deepcopy(ref)
        for r in group:
            for field,value in r.items():
                if present(value) and not present(out.get(field)):out[field]=copy.deepcopy(value)
        out['iso'],out['time']=target
        lid,mid=(next(iter(x),'') for x in ids)
        if lid:out['leagueId']=lid
        if mid:out['matchId']=mid
        if make_match_url(lid,mid):
            out['actaUrl']=make_match_url(lid,mid)
            out['actaState']='available' if any(r.get('actaState')=='available' for r in group) else 'pending'
        for field in ('lastAgendaAt','lastDirecteAt','directeUpdatedAt','scoreUpdatedAt','actaCheckedAt','finalDetectedAt','agendaRecoveredAt'):
            vals=[r[field] for r in group if r.get(field)]
            if vals:out[field]=max(vals,key=check_when)
        if values:
            out['homeScore'],out['awayScore']=next(iter(values))
            scored=[r for r in group if scores(r) is not None]
            if scored:
                best=max(scored,key=lambda r:(r.get('actaState')=='available',norm(r.get('scoreSource'))=='EN DIRECTE',bool(r.get('scoreUpdatedAt')),slot(r)==target))
                for field in ('status','scoreSource','scoreUpdatedAt'):
                    if best.get(field):out[field]=best[field]
            if source_score is not None and target[0]<'2026-11-28':
                out['status']='FINAL'
                if not scored:out.update(scoreSource='Agenda',scoreUpdatedAt=manifest['capturedAt'],finalDetectedAt=manifest['capturedAt'],agendaRecoveredAt=manifest['capturedAt'])
        entry.update(status='merged' if len(group)>1 else 'rescheduled',removed=len(group)-1,result=out)
        rows=[r for i,r in enumerate(rows) if i not in set(idx)];rows.append(out);results.append(entry)
    assert {official_id(r) for r in before if official_id(r)}=={official_id(r) for r in rows if official_id(r)}
    assert len(before)-len(rows)==sum(r['removed'] for r in results)
    rows.sort(key=lambda r:(r.get('iso',''),r.get('time',''),norm(r.get('competition')),norm(r.get('home'))))
    report={'schema':'zonaok-approved-schedule-repair-report-v1','sourceRun':manifest['sourceRun'],'processed':len(results),'before':len(before),'after':len(rows),'removed':len(before)-len(rows),'rescheduled':sum(r['status']=='rescheduled' for r in results),'merged':sum(r['status']=='merged' for r in results),'alreadyCorrect':sum(r['status']=='already_correct' for r in results),'review':sum(r['status']=='review' for r in results),'details':results}
    out={**doc,'matches':rows,'updatedAt':utc_now(),'stats':{**doc.get('stats',{}),'total':len(rows),'withScores':sum(score_tuple(r) for r in rows),'withActaLinks':sum(bool(r.get('actaUrl')) for r in rows),'verifiedActes':sum(r.get('actaState')=='available' for r in rows)}}
    return out,report
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    doc=load_unified(CANONICAL); out,report=repair(doc,json.loads(MANIFEST.read_text()))
    if report['removed'] or report['rescheduled']:
        write(CANONICAL,out);write_compatibility(out)
    write(REPORT,report)
    print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=False))
    for r in report['details']:
        print('REPAIR',json.dumps({k:v for k,v in r.items() if k not in ('originalRows','result')},ensure_ascii=False))
if __name__=='__main__':main()
