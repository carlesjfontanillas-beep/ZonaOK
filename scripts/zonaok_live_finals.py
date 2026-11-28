#!/usr/bin/env python3
"""Prioritat de finals del dia, només competicions afectades. No escriu dades."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import re, json, unicodedata
from pathlib import Path
MADRID=ZoneInfo('Europe/Madrid')
FINAL=re.compile(r'\b(FINAL|FINALITZAT|FINALIZADO|ACABAT|ACABADO|FINISHED|FULL TIME|ACTA TANCADA|ACTA CERRADA)\b',re.I)
def norm(s):
    return re.sub(r'[^A-Z0-9]+',' ',''.join(c for c in unicodedata.normalize('NFD',str(s or '')) if unicodedata.category(c)!='Mn').upper()).strip()
def stamp(v):
    try:
        d=datetime.fromisoformat(str(v or '').replace('Z','+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,TypeError):return None
def current_final(r,now):
    if not FINAL.search(norm(r.get('status'))) or not all(type(r.get(k)) is int and r[k]>=0 for k in ('homeScore','awayScore')):return False
    try:kickoff=datetime.strptime(str(r.get('iso'))+' '+str(r.get('time')),'%Y-%m-%d %H:%M').replace(tzinfo=MADRID)
    except (ValueError,TypeError):return False
    local=now.astimezone(MADRID)
    return kickoff<=local and (kickoff.date()==local.date() or (kickoff.date()==local.date()-timedelta(days=1) and kickoff.hour>=20 and local.hour<4))
def targets(fixtures,standings,now=None):
    now=now or datetime.now(timezone.utc)
    groups=standings.get('competitions',{})
    output={}
    for r in fixtures.get('matches',[]):
        if not isinstance(r,dict) or not current_final(r,now):continue
        observed=stamp(r.get('finalDetectedAt') or r.get('actaCheckedAt') or r.get('lastDirecteAt') or r.get('scoreUpdatedAt'))
        if not observed or observed>now:continue
        lid=str(r.get('leagueId') or '')
        exact=[(k,g) for k,g in groups.items() if isinstance(g,dict) and norm(g.get('name'))==norm(r.get('competition')) and (not lid or str(g.get('leagueId'))==lid)]
        if not lid:
            # Infer only from an exact, unique official group and both full names.
            exact=[(k,g) for k,g in exact if {norm(r.get('home')),norm(r.get('away'))} <= {norm(t.get('team')) for t in g.get('standings',[]) if isinstance(t,dict)}]
            lids={str(g.get('leagueId') or '') for _,g in exact}
            if len(lids)!=1:continue
            lid=next(iter(lids))
        if not re.fullmatch(r'\d{4,6}',lid):continue
        matching=exact or [(k,g) for k,g in groups.items() if isinstance(g,dict) and str(g.get('leagueId'))==lid]
        if matching and all((stamp(g.get('standingsAt') or g.get('capturedAt')) or datetime.min.replace(tzinfo=timezone.utc))>=observed for _,g in matching):continue
        names={norm(g.get('name')) for _,g in exact if norm(g.get('name'))}
        if lid not in output:output[lid]=names or None
        elif output[lid] is not None:
            output[lid]=output[lid]|names if names else None
    return output
def read_targets():
    return targets(json.loads(Path('zonaok-tots-partits.json').read_text()),json.loads(Path('zonaok-classificacions.json').read_text()))
def main():
    result=read_targets()
    print(json.dumps({k:sorted(v) if v is not None else None for k,v in result.items()},ensure_ascii=False))
if __name__=='__main__':main()
