#!/usr/bin/env python3
"""Correct the Girona B–Figueres fixture using the user's FECAPA calendar screenshot."""
import json
from pathlib import Path
from zonaok_fecapa_unificat import CANONICAL,load_unified,norm,score_tuple,check_iso,write_compatibility,utc_now
from zonaok_agenda_reparacio_confirmats import repair
REPORT=Path('imports/agenda-girona-figueres-20261128.json')
OLD=('2026-11-27','20:50')
TARGET=('2027-10-08','20:50')
HOME={'GIRONA CLUB HOQUEI B','GIRONA B'}
AWAY={'CH FIGUERES','FIGUERES'}
def slot(r):return r.get('iso'),r.get('time')
def correct(doc):
    rows=doc['matches']
    possible=[r for r in rows if norm(r.get('home')) in HOME and norm(r.get('away')) in AWAY]
    relevant=[r for r in possible if slot(r) in (OLD,TARGET)]
    report={'source':'Captura del calendari oficial FECAPA aportada per l’usuari el 28/11/2026','old':list(OLD),'official':list(TARGET),'checkedAt':utc_now(),'candidateRows':relevant}
    groups={norm(r.get('competition')) for r in relevant}
    if not relevant or len(groups)!=1:
        report.update(status='review',reason='missing_or_ambiguous_category')
        return doc,report
    group=next(iter(groups))
    if any(norm(r.get('competition'))==group and slot(r) not in (OLD,TARGET) for r in possible):
        report.update(status='review',reason='another_slot_requires_verification')
        return doc,report
    # Use the exact stored name, not a guessed category. Do not mix distinct official IDs.
    names={(norm(r.get('home')),norm(r.get('away'))) for r in relevant}
    if len(names)!=1:
        report.update(status='review',reason='different_name_variants')
        return doc,report
    ref=relevant[0]
    spec={k:ref[k] for k in ('competition','home','away')}
    spec.update(oldIso=OLD[0],oldTime=OLD[1],iso=TARGET[0],time=TARGET[1],homeScore=None,awayScore=None)
    out,audit=repair(doc,{'season':doc['season'],'sourceRun':46126797596,'capturedAt':utc_now(),'fixtures':[spec]})
    detail=audit['details'][0]
    final=[r for r in out['matches'] if norm(r.get('competition'))==group and norm(r.get('home')) in HOME and norm(r.get('away')) in AWAY]
    report.update(status=detail['status'],reason=detail.get('reason'),competition=ref['competition'],removed=audit['removed'],before=len(rows),after=len(out['matches']),remaining=len(final),details=detail)
    if detail['status']!='review':
        assert len(final)==1 and slot(final[0])==TARGET
    return out,report
def main():
    doc=load_unified(CANONICAL)
    out,report=correct(doc)
    if report['status'] in ('merged','rescheduled'):
        CANONICAL.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        write_compatibility(out)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('candidateRows','details')},ensure_ascii=False))
if __name__=='__main__':main()
