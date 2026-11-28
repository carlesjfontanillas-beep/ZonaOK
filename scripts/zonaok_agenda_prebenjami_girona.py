import json,copy
from pathlib import Path
from zonaok_fecapa_unificat import CANONICAL,load_unified,norm,score_tuple,utc_now,write_compatibility,clean
from zonaok_agenda_reparacio_confirmats import write
def pair(r):return tuple(norm(r.get(k)) for k in ('competition','home','away'))
def slot(r):return (r.get('iso'),r.get('time'))
def repair(doc,manifest,agenda):
    if doc['season']!=manifest['season']:raise ValueError('season mismatch')
    rows=copy.deepcopy(doc['matches']);details=[]
    for spec in manifest['fixtures']:
        k=pair(spec);obsolete=tuple(spec['old']);official={tuple(x) for x in spec['official']}
        d={'fixture':list(k),'obsolete':list(obsolete),'official':spec['official'],'removed':0,'source':spec['url']}
        details.append(d)
        source=[x for x in agenda['conflicts'] if x.get('fixture')==list(k+obsolete)]
        if len(source)!=1 or {tuple(s) for s in source[0].get('possible',[])}!=official:
            d.update(status='review',reason='official_capture_does_not_confirm');continue
        group=[r for r in rows if pair(r)==k]
        old=[r for r in group if slot(r)==obsolete]
        targets=[r for r in group if slot(r) in official]
        if len(targets)!=len(official) or {slot(r) for r in targets}!=official:
            d.update(status='review',reason='official_rows_not_unique_in_catalog');continue
        if not old:
            d.update(status='already_correct');continue
        if any(r.get('homeScore') is not None or r.get('awayScore') is not None or r.get('actaState')=='available' or r.get('actaUrl') or clean(r.get('matchId')) for r in old):
            d.update(status='review',reason='obsolete_has_protected_data');continue
        d.update(status='removed',removed=len(old),originalRows=old)
        rows=[r for r in rows if not(pair(r)==k and slot(r)==obsolete)]
    result={**doc,'matches':rows,'updatedAt':utc_now(),'stats':{**doc.get('stats',{}),'total':len(rows),'withScores':sum(score_tuple(r) for r in rows),'withActaLinks':sum(bool(r.get('actaUrl')) for r in rows),'verifiedActes':sum(r.get('actaState')=='available' for r in rows)}}
    assert len(doc['matches'])-len(rows)==sum(d['removed'] for d in details)
    return result,{'schema':'zonaok-obsolete-slot-repair-v1','sourceRun':manifest['sourceRun'],'removed':sum(d['removed'] for d in details),'review':sum(d['status']=='review' for d in details),'before':len(doc['matches']),'after':len(rows),'details':details}
if __name__=='__main__':
    manifest=json.loads(Path('imports/agenda-prebenjami-girona-confirmats.json').read_text())
    agenda=json.loads(Path('imports/agenda-daily-report.json').read_text())
    doc=load_unified(CANONICAL)
    out,report=repair(doc,manifest,agenda)
    if report['removed']:
        write(CANONICAL,out);write_compatibility(out)
    write('imports/agenda-prebenjami-girona-resultat.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=False))
