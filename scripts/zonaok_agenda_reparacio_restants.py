#!/usr/bin/env python3
"""Approved remaining cases; retain the latest date and correct inverted rows."""
import copy,json
from pathlib import Path
from zonaok_fecapa_unificat import CANONICAL,load_unified,norm,score_tuple,utc_now,write_compatibility,make_match_url,official_match_url
from zonaok_agenda_reparacio_confirmats import repair,pair,slot,scores,identity,official_id
MANIFEST=Path('imports/agenda-reparacio-restants-20261128-confirmats.json')
REPORT=Path('imports/agenda-reparacio-restants-20261128-resultat.json')
def correct(doc,manifest):
    out,audit=repair(doc,manifest)
    rows=out['matches']
    details=audit['details']
    for spec in manifest['reversed']:
        k=pair(spec); t=slot(spec); rev=(k[0],k[2],k[1])
        group=[r for r in rows if slot(r)==t and pair(r) in (k,rev)]
        record={'fixture':list(k),'official':list(t),'originalRows':copy.deepcopy(group),'removed':0}
        details.append(record)
        if not group:
            record.update(status='review',reason='not_found');continue
        # A reverse record with its own official identity or acta is not safe to delete.
        correct_rows=[r for r in group if pair(r)==k]
        reverse_rows=[r for r in group if pair(r)==rev]
        if any(official_id(r) or r.get('actaUrl') or r.get('actaState')=='available' for r in reverse_rows):
            record.update(status='review',reason='reverse_has_official_identity');continue
        if any((r.get('homeScore') is None)!=(r.get('awayScore') is None) for r in group):
            record.update(status='review',reason='partial_score');continue
        target=scores(spec)
        if any(scores(r) is not None and (scores(r) if pair(r)==k else scores(r)[::-1])!=target for r in group):
            record.update(status='review',reason='conflicting_score');continue
        if len(correct_rows)>1:
            record.update(status='review',reason='multiple_correct_rows');continue
        if correct_rows:
            result=dict(correct_rows[0])
        else:
            result=dict(reverse_rows[0])
            result['homeLogo'],result['awayLogo']=result.get('awayLogo',''),result.get('homeLogo','')
            result['home'],result['away']=spec['home'],spec['away']
        result.update(homeScore=target[0],awayScore=target[1],status='FINAL',venue=spec['venue'])
        if not correct_rows or not scores(correct_rows[0]):
            result.update(scoreSource='Agenda',scoreUpdatedAt=manifest['capturedAt'],finalDetectedAt=manifest['capturedAt'],agendaRecoveredAt=manifest['capturedAt'])
        rows=[r for r in rows if not (slot(r)==t and pair(r) in (k,rev))]+[result]
        record.update(status='merged' if len(group)>1 else ('corrected' if reverse_rows or not scores(group[0]) else 'already_correct'),removed=len(group)-1,result=result)
    assert {official_id(r) for r in doc['matches'] if official_id(r)}=={official_id(r) for r in rows if official_id(r)}
    assert len(doc['matches'])-len(rows)==sum(r['removed'] for r in details)
    rows.sort(key=lambda r:(r.get('iso',''),r.get('time',''),norm(r.get('competition')),norm(r.get('home'))))
    out.update(matches=rows,updatedAt=utc_now(),stats={**out.get('stats',{}),'total':len(rows),'withScores':sum(score_tuple(r) for r in rows),'withActaLinks':sum(bool(r.get('actaUrl')) for r in rows),'verifiedActes':sum(r.get('actaState')=='available' for r in rows)})
    return out,{'schema':'zonaok-approved-remaining-repairs-v1','before':len(doc['matches']),'after':len(rows),'removed':len(doc['matches'])-len(rows),'resolved':sum(r['status']!='review' for r in details),'review':sum(r['status']=='review' for r in details),'details':details}
def main():
    doc=load_unified(CANONICAL)
    out,report=correct(doc,json.loads(MANIFEST.read_text()))
    if doc['matches']!=out['matches']:
        CANONICAL.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        write_compatibility(out)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=False))
if __name__=='__main__':main()
