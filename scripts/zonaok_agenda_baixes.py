#!/usr/bin/env python3
"""Remove only the 22 approved non-fixtures; preserve a reversible audit."""
import json
from pathlib import Path
from zonaok_fecapa_unificat import CANONICAL,load_unified,norm,score_tuple,utc_now,write_compatibility,invalid_fixture_team
MANIFEST=Path('imports/agenda-baixes-20261128-confirmades.json')
REPORT=Path('imports/agenda-baixes-20261128-resultat.json')
def key(r):
    return (*[norm(r.get(k)) for k in ('competition','home','away')],r.get('iso'),r.get('time'))
def remove(doc,manifest,prior=None):
    if doc.get('season')!=manifest.get('season'):raise ValueError('season mismatch')
    confirmed_absent={tuple(k) for k in manifest.get("confirmedAbsentFixtures",[])}
    approved={tuple(k) for k in manifest['fixtures']} | confirmed_absent
    kept=[];removed=[];review=[];found=set()
    for r in doc['matches']:
        k=key(r)
        if k not in approved:
            kept.append(r);continue
        found.add(k)
        if (k not in confirmed_absent and not invalid_fixture_team(r)) or any(r.get(f) is not None for f in ('homeScore','awayScore')) or r.get('actaState')=='available':
            kept.append(r);review.append(r);continue
        removed.append(r)
    old_removed=(prior or {}).get('removedRows',[])
    archive=old_removed+removed
    removed_keys={key(r) for r in archive}
    report={'schema':'zonaok-withdrawn-fixtures-report-v1','sourceRun':manifest['sourceRun'],'checkedAt':utc_now(),'approved':len(approved),'before':len(doc['matches']),'after':len(kept),'removedNow':len(removed),'removedTotal':len(archive),'resolved':len(approved & removed_keys),'review':review,'notFound':[list(k) for k in sorted(approved-found-removed_keys)],'removedRows':archive}
    result={**doc,'matches':kept,'updatedAt':utc_now(),'stats':{**doc.get('stats',{}),'total':len(kept),'withScores':sum(score_tuple(r) for r in kept),'withActaLinks':sum(bool(r.get('actaUrl')) for r in kept),'verifiedActes':sum(r.get('actaState')=='available' for r in kept)}}
    assert len(removed)+len(kept)==len(doc['matches'])
    return result,report
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    doc=load_unified(CANONICAL)
    previous=json.loads(REPORT.read_text()) if REPORT.exists() else None
    result,report=remove(doc,json.loads(MANIFEST.read_text()),previous)
    if report['removedNow']:
        write(CANONICAL,result);write_compatibility(result)
    write(REPORT,report)
    print(json.dumps({k:v for k,v in report.items() if k!='removedRows'},ensure_ascii=False))
if __name__=='__main__':main()
