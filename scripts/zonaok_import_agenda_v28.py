#!/usr/bin/env python3
"""ZonaOK V28 — importació automàtica de l'Agenda FECAPA a zonaok-data.json.

Llegeix captures originals de ZO Agenda (kind=agenda-season). Fusiona només
`data.agenda`; no escriu ni modifica classificacions, actes ni altres seccions.
Els fitxers de la carpeta d'entrada romanen a GitHub com a còpies de seguretat.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

INBOX = Path('imports/agenda/v28')
TARGET = Path('zonaok-data.json')
MIN_FULL_SEASON = 100  # rebutgem captures setmanals parcials
MAX_SEASON = 1500


def utc(value):
    try:
        out = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if out.tzinfo is None: return None
        return out.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def normalize(value):
    s = unicodedata.normalize('NFD', str(value or '')).upper()
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


def clubs(name):
    name = normalize(name)
    if re.fullmatch(r'(?:BARCA|FC BARCELONA|F C BARCELONA|FCBETRANS|FCBETERANS)(?: [A-Z0-9]+)?', name):
        return 'barca'
    if re.fullmatch(r'(?:(?:CP|C P) )?SANT CELONI(?: [A-Z0-9]+)?', name) or name in ('CLUB PATI SANT CELONI',):
        return 'celoni'
    return ''


def goals(value):
    if value is None or value == '':return None
    if isinstance(value,bool):raise ValueError('Marcador booleà no vàlid')
    try:v=int(value)
    except (TypeError,ValueError):raise ValueError('Marcador invàlid')
    if isinstance(value,float) and value!=v:raise ValueError('Marcador decimal invàlid')
    if not 0<=v<200:raise ValueError('Marcador fora de rang')
    return v


def parse_row(value, captured):
    if isinstance(value,list):
        if len(value)<8 or len(value)>11:raise ValueError('Una fila no té les 8 columnes oficials')
        value=dict(zip(('iso','time','competition','home','away','homeScore','awayScore','venue','id','actaUrl','league'),value))
    if not isinstance(value,dict):raise ValueError('Fila d’Agenda no vàlida')
    iso=str(value.get('iso') or '').strip();t=str(value.get('time') or '').strip()
    try:
        if not re.fullmatch(r'20\d\d-\d\d-\d\d',iso) or not re.fullmatch(r'\d\d:\d\d',t):raise ValueError()
        dt=datetime.strptime(iso+' '+t,'%Y-%m-%d %H:%M')
    except ValueError:raise ValueError('Data o hora invàlida a la captura')
    if not datetime(2026,7,1)<=dt<=datetime(2027,6,30,23,59):raise ValueError('Data fora de temporada 2026/27')
    fields={k:str(value.get(k) or '').strip() for k in ('competition','home','away','venue')}
    if not all(fields[k] for k in ('competition','home','away')):raise ValueError('Falten competició o noms d’equips')
    if any(len(s)>250 for s in fields.values()):raise ValueError('Text d’una fila massa llarg')
    hh=goals(value.get('homeScore'));aa=goals(value.get('awayScore'))
    if (hh is None) != (aa is None):raise ValueError('Marcador incomplet')
    result={'iso':iso,'time':t,**fields,'homeScore':hh,'awayScore':aa,
            'capturedAt':captured,'homeClub':clubs(fields['home']),'awayClub':clubs(fields['away'])}
    for field in ('id','league','actaUrl'):
        if value.get(field):result[field]=str(value[field])[:350]
    return result


def rowkey(row):
    return (str(row.get('iso') or ''),normalize(row.get('competition')),
            normalize(row.get('home')),normalize(row.get('away')))


def parse_packet(blob, name):
    if not isinstance(blob,dict) or blob.get('source')!='FECAPA-SAFARI' or blob.get('kind')!='agenda-season':
        raise ValueError(f'{name}: el JSON no és una captura agenda-season de FECAPA')
    if str(blob.get('season') or '').replace('-','/') not in ('2026/2027','2026/27'):
        raise ValueError(f'{name}: temporada no compatible')
    when=utc(blob.get('capturedAt'))
    if when is None:raise ValueError(f'{name}: falta una data de captura UTC vàlida')
    rows=blob.get('rows')
    if not isinstance(rows,list) or not MIN_FULL_SEASON<=len(rows)<=MAX_SEASON:
        raise ValueError(f'{name}: {len(rows) if isinstance(rows,list) else 0} files; cal tota la temporada ({MIN_FULL_SEASON}-{MAX_SEASON})')
    normalized=[parse_row(r,blob['capturedAt']) for r in rows]
    unique=set()
    for r in normalized:
        k=(rowkey(r),r['time'])
        if k in unique:raise ValueError(f'{name}: partit duplicat a la captura: {k}')
        unique.add(k)
    return when,normalized,blob


def is_scored(row):
    return isinstance(row,dict) and row.get('homeScore') is not None and row.get('awayScore') is not None


def preserve_score(old,new,new_at):
    if not is_scored(old):return new
    # El marcador confirmat mai es perd per un valor null d'Agenda.
    if not is_scored(new):
        for field in ('homeScore','awayScore','scoreCapturedAt','scoreSource'):
            if field in old:new[field]=old[field]
        return new
    old_score_at=utc(old.get('scoreCapturedAt'))
    if old_score_at and old_score_at>new_at:
        for field in ('homeScore','awayScore','scoreCapturedAt','scoreSource'):
            if field in old:new[field]=old[field]
    elif old.get('homeScore')==new['homeScore'] and old.get('awayScore')==new['awayScore']:
        for field in ('scoreCapturedAt','scoreSource'):
            if old.get(field):new[field]=old[field]
    else:
        # El resultat del nou FECAPA és més recent que la confirmació anterior.
        new['scoreCapturedAt']=new_at.isoformat()
        new['scoreSource']='Agenda FECAPA'
    return new


def merge(existing, incoming, packet):
    if not isinstance(existing,dict) or existing.get('version')!=3 or not isinstance(existing.get('data'),dict):
        raise ValueError('zonaok-data.json ha de tenir {"version":3,"data":{...}}')
    data=existing['data'];old_agenda=data.get('agenda') or {}
    if not isinstance(old_agenda,dict) or not isinstance(old_agenda.get('rows',[]),list):
        raise ValueError('Agenda existent mal formada; no sobreescriure res')
    old_rows=old_agenda.get('rows',[])
    if len(old_rows)>MAX_SEASON*2:raise ValueError('Agenda existent massa gran')
    captured=utc(packet['capturedAt'])
    last_source=utc(old_agenda.get('sourceCapturedAt'))
    if last_source and last_source>=captured:
        return copy.deepcopy(existing),{'skipped_older_capture':True,'existing':len(old_rows),'incoming':len(incoming)}
    # Preservem TOT el document i TOTS els camps addicionals de les files antigues.
    doc=copy.deepcopy(existing)
    bykey={};result=[]
    for r in old_rows:
        if not isinstance(r,dict):raise ValueError('Fila existent no vàlida')
        k=rowkey(r)
        bykey.setdefault(k,[]).append(len(result));result.append(copy.deepcopy(r))
    accepted=0;updated=0;ambiguous=0
    for item in incoming:
        k=rowkey(item);matches=bykey.get(k,[])
        if len(matches)>1:
            # Si hi ha dos enfrontaments al mateix dia, només fusiona l'hora exacta.
            matches=[j for j in matches if result[j].get('time')==item['time']]
        if len(matches)>1:
            ambiguous+=1;continue
        if not matches:
            idx=len(result);result.append(copy.deepcopy(item));bykey.setdefault(k,[]).append(idx);accepted+=1
        else:
            idx=matches[0];old=result[idx]
            merged={**old,**item}
            # Conserva IDs, pistes, logos, URLs, informació d'acta, etc. si no venen en la captura.
            for f,v in old.items():
                if f not in item or (item.get(f) in ('',None) and f not in ('homeScore','awayScore')):
                    merged[f]=v
            merged=preserve_score(old,merged,captured)
            # CapturedAt original dels marcadors no és el de l'Agenda.
            if merged!=old:updated+=1
            result[idx]=merged
    if ambiguous:raise ValueError(f'Hi ha {ambiguous} partits amb identitat ambigua. No es publica res.')
    result.sort(key=lambda r:(str(r.get('iso') or ''),str(r.get('time') or ''),normalize(r.get('competition')),normalize(r.get('home'))))
    # El nom de cada equip per a la UI va en homeClub/awayClub.
    for r in result:
        r['homeClub']=clubs(r.get('home'));r['awayClub']=clubs(r.get('away'))
    out_agenda=doc['data'].setdefault('agenda',{})
    out_agenda.update({'season':'2026/2027','sourceCapturedAt':packet['capturedAt'],
                       'capturedAt':packet['capturedAt'],'sourceURL':str(packet.get('url') or 'https://www.hoqueipatins.fecapa.cat/ag/'),
                       'counts':{'barca':sum(r['homeClub']=='barca' or r['awayClub']=='barca' for r in result),
                                 'celoni':sum(r['homeClub']=='celoni' or r['awayClub']=='celoni' for r in result),
                                 'partits':len(result),'importats':len(incoming)},'rows':result})
    doc['publishedAt']=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    # Garantia: cap altra secció es modifica.
    for key in data:
        if key!='agenda' and doc['data'].get(key)!=data[key]:raise AssertionError('S’ha modificat una secció aliena a Agenda')
    return doc,{'old':len(old_rows),'incoming':len(incoming),'total':len(result),
                'new':accepted,'updated':updated,'sourceCapturedAt':packet['capturedAt']}


def run(root):
    folder=root/INBOX;files=sorted(folder.glob('*.json'))
    if not files:raise ValueError('Encara no hi ha cap captura a imports/agenda/v28/')
    valid=[]
    for p in files:
        try:valid.append((*parse_packet(json.loads(p.read_text(encoding='utf-8')),p.name),p))
        except (ValueError,json.JSONDecodeError,UnicodeError) as e:
            raise ValueError('La captura '+p.name+' no és vàlida. '+str(e))
    valid.sort(key=lambda z:z[0]); when, rows, packet, path=valid[-1]
    target=root/TARGET
    if not target.exists():raise ValueError('Falta zonaok-data.json; no crearem un document buit')
    existing=json.loads(target.read_text(encoding='utf-8'))
    result,stats=merge(existing,rows,packet)
    if result!=existing:target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CAPTURA:',path.relative_to(root),'DATA:',packet['capturedAt'])
    print('RESULTAT:',json.dumps(stats,ensure_ascii=False))
    return stats


if __name__=='__main__':
    try:run(Path(os.environ.get('GITHUB_WORKSPACE') or '.').resolve())
    except (ValueError,KeyError,TypeError,UnicodeError,json.JSONDecodeError,AssertionError) as exc:
        sys.exit('ERROR AGENDA V28: no hem publicat res. '+str(exc))
