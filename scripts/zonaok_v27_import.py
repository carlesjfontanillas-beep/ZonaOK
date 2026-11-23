#!/usr/bin/env python3
"""ZonaOK V27: només classificacions independents o marcadors DINS Agenda existent.

NO importa Agenda, NO toca dreceres d'Agenda i NO modifica actes.
Requereix el paquet FECAPA-SAFARI en Base64 al workflow_dispatch.
"""
from __future__ import annotations
import base64
import copy
import gzip
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

LEAGUES = ('4789', '4786', '4784')
MAX_PACKET = 62000


def decode_payload(value):
    """Extract the Base64 payload without accidentally decoding wrapper text."""
    value=unicodedata.normalize('NFKC',str(value or '')).strip()
    # Filtering non-Base64 characters corrupts wrapper text because its letters
    # are valid Base64 too. Decode candidate runs and accept only gzip or JSON.
    candidates=re.findall(r'[A-Za-z0-9+/_-]+={0,2}',value)
    # Some Shortcuts versions turn '+' into spaces. Restore them only if the
    # whole input otherwise consists solely of Base64 characters and spaces.
    if re.fullmatch(r'[A-Za-z0-9/_=+\-\s]+',value):
        candidates.append(re.sub(r'\s+','',value))
        candidates.append(re.sub(r'\s+','+',value))
    candidates=sorted({x for x in candidates if len(x)>=16},key=len,reverse=True)
    for candidate in candidates:
        if len(candidate)>MAX_PACKET:continue
        encoded=candidate.replace('-','+').replace('_','/')
        encoded+='='*(-len(encoded)%4)
        try: raw=base64.b64decode(encoded,validate=True)
        except (ValueError,base64.binascii.Error):continue
        if raw.startswith(b'\x1f\x8b') or raw.lstrip().startswith((b'{',b'[')):
            return raw
    raise ValueError('El paquet rebut no és Base64 vàlid o no conté gzip/JSON. No s’ha escrit res; revisa la variable payload de la drecera.')


def stamp(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if d.tzinfo is None: return None
        return d.astimezone(timezone.utc)
    except (TypeError,ValueError):
        return None


def norm(value):
    s = unicodedata.normalize('NFD',str(value or '')).upper()
    return re.sub(r'[^A-Z0-9]+',' ',''.join(c for c in s if unicodedata.category(c)!='Mn')).strip()


def team(value):
    s=norm(value)
    # Distingim explicitament els equips A i B: CPSCA != CPSCB.
    # També acceptem abreviatures CPSC, CPSCA, CPSCB i altres sufixos curts.
    code=re.fullmatch(r'CPSC([A-Z0-9]{0,2})',s.replace(' ',''))
    if code:
        suffix=code.group(1)
        return 'SANT CELONI' + (' '+suffix if suffix else '')
    for rx, replacement in [
        (r'^(?:BAR|BARCA|FC BARCELONA|F C BARCELONA|FCBETRANS|FCBETERANS)(?: (.*))?$', 'BARCA'),
        (r'^(?:CP SANT CELONI|C P SANT CELONI|SANT CELONI)(?: (.*))?$', 'SANT CELONI')
    ]:
        m=re.fullmatch(rx,s)
        if m: return replacement + (' '+m.group(1) if m.group(1) else '')
    return s


def goal(value):
    if value is None or isinstance(value,bool): return None
    s=str(value).strip()
    return int(s) if re.fullmatch(r'\d{1,3}',s) and int(s)<200 else None


def row(value):
    if isinstance(value,list):
        if len(value)<7:return None
        value=dict(zip(('iso','time','competition','home','away','homeScore','awayScore','venue','id'),value))
    if not isinstance(value,dict): return None
    try:
        iso=str(value.get('iso') or '')[:10]
        time=str(value.get('time') or '')[:5]
        if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',iso) or not re.fullmatch(r'\d{2}:\d{2}',time):return None
        datetime.strptime(iso+' '+time,'%Y-%m-%d %H:%M')
    except (ValueError,TypeError):return None
    home=str(value.get('home') or '').strip()
    away=str(value.get('away') or '').strip()
    if not home or not away:return None
    score_h=goal(value.get('homeScore'));score_a=goal(value.get('awayScore'))
    return {'iso':iso,'time':time,'competition':str(value.get('competition') or '').strip(),
        'home':home,'away':away,'id':str(value.get('id') or '').strip(),
        'homeScore':score_h,'awayScore':score_a}


def score_match(old,new):
    # L'ID oficial és preferent; si els dos existeixen i divergeixen, són partits diferents.
    if old['id'] and new['id']:return old['id']==new['id']
    if old['iso']!=new['iso']:return False
    if team(old['home'])!=team(new['home']) or team(old['away'])!=team(new['away']):return False
    a,b=norm(old['competition']),norm(new['competition'])
    return not (a and b and a!=b)


def update_scores(document, incoming, captured_at):
    if not isinstance(document,dict) or document.get('version')!=3 or not isinstance(document.get('data'),dict):
        raise ValueError('zonaok-data.json no té el format compatible {version:3,data:{...}}')
    data=document['data'];agenda=data.get('agenda')
    if not isinstance(agenda,dict) or not isinstance(agenda.get('rows'),list) or not agenda['rows']:
        raise ValueError('No hi ha partits a data.agenda.rows. Importa primer Agenda amb la drecera EXISTENT.')
    fixtures=agenda['rows']
    if len(fixtures)>20000: raise ValueError('Agenda massa gran o danyada')
    changed=outdated=invalid=matched=0
    unmatched=[]
    for raw in incoming:
        candidate=row(raw)
        if not candidate or candidate['homeScore'] is None or candidate['awayScore'] is None:
            invalid+=1;continue
        matches=[i for i,existing in enumerate(fixtures) if (cleaned:=row(existing)) is not None and score_match(cleaned,candidate)]
        if len(matches)!=1:
            unmatched.append({'iso':candidate['iso'],'home':candidate['home'],'away':candidate['away'],'candidats':len(matches)})
            continue
        original=fixtures[matches[0]]
        matched+=1
        # La data d'importació d'Agenda NO és la data de verificació del resultat.
        # Un resultat ja confirmat pot ser anterior o posterior a l'última lectura d'Agenda.
        old_stamp=stamp(original.get('scoreCapturedAt'))
        if not old_stamp and goal(original.get('homeScore')) is not None and goal(original.get('awayScore')) is not None:
            old_stamp=stamp(original.get('capturedAt'))
        if old_stamp and old_stamp>captured_at:
            outdated+=1;continue
        if original.get('homeScore')==candidate['homeScore'] and original.get('awayScore')==candidate['awayScore']:
            # Repetició: no reescriure la data de captura i per tant no fer commits innecessaris.
            continue
        original['homeScore']=candidate['homeScore'];original['awayScore']=candidate['awayScore']
        original['scoreCapturedAt']=captured_at.isoformat();original['scoreSource']='En directe'
        # Necessari per a la fusió del client V23 sense tocar pista, equips ni data del partit.
        if not stamp(original.get('capturedAt')) or stamp(original.get('capturedAt'))<captured_at:
            original['capturedAt']=captured_at.isoformat()
        changed+=1
    if not matched:
        raise ValueError("Cap marcador coincideix de manera unívoca amb Agenda. No s'ha publicat res. Revisa la pàgina FECAPA i els noms dels equips.")
    if changed:
        agenda['scoresAt']=captured_at.isoformat()
        if not stamp(agenda.get('capturedAt')) or stamp(agenda.get('capturedAt'))<captured_at:
            agenda['capturedAt']=captured_at.isoformat()
    return document, {'marcadors_actualitzats':changed,'coincidencies':matched,'ignorats_antics':outdated,
        'no_corresponents_o_ambigus':unmatched,'invalids':invalid,'partits_agenda':len(fixtures)}


def clean_standings(entries):
    if not 2<=len(entries)<=50:raise ValueError('Classificació buida o massa gran')
    out=[];seen=set()
    for x in entries:
        if not isinstance(x,dict):raise ValueError('Fila de classificació no vàlida')
        team_name=str(x.get('team') or '').strip()
        if not team_name:raise ValueError('Equip sense nom')
        namekey=norm(team_name)
        if namekey in seen:raise ValueError('Equip duplicat a la classificació')
        seen.add(namekey)
        r={}
        for key in ('pos','team','played','points','gf','ga','difference'):
            r[key]=str(x.get(key) if x.get(key) is not None else '').strip()[:120]
        r['stats']={k:str(v).strip()[:15] for k,v in (x.get('stats') or {}).items() if re.fullmatch(r'[A-Z0-9_ -]{1,30}',str(k))}
        out.append(r)
    return out


def apply(packet,read_json):
    if not isinstance(packet,dict) or packet.get('source')!='FECAPA-SAFARI':
        raise ValueError('Font no reconeguda')
    captured=stamp(packet.get('capturedAt'))
    if not captured: raise ValueError('La captura no té data UTC correcta')
    kind=packet.get('kind')
    if kind in ('standings-all','classificacions-total'):
        incoming_leagues=packet.get('competitions',packet.get('leagues'))
        if not isinstance(incoming_leagues,dict) or not incoming_leagues or len(incoming_leagues)>500:
            raise ValueError('Cal una llista de classificacions vàlida (màxim 500)')
        filename='zonaok-classificacions.json'
        existing=read_json(filename)
        if existing is not None and not isinstance(existing,dict):
            raise ValueError('Fitxer unificat de classificacions mal format')
        existing=existing or {}
        if existing and existing.get('schema') not in ('zonaok-classificacions-v1','zonaok-classificacions-v2'):
            raise ValueError('Esquema unificat incompatible; cap sobreescriptura')
        old_leagues=existing.get('competitions') or existing.get('leagues') or {}
        if not isinstance(old_leagues,dict):raise ValueError('Classificacions existents mal formades')
        result={};updated=0;preserved=0;total=0
        incoming_names={norm(item.get('name')) for item in incoming_leagues.values() if isinstance(item,dict)}
        for league,item in incoming_leagues.items():
            league=str(league).strip()[:160]
            if not re.fullmatch(r'[A-Za-z0-9:_-]{1,160}',league):raise ValueError('Identificador de classificació no vàlid')
            if not isinstance(item,dict):raise ValueError('Classificació '+league+' mal formada')
            rows=clean_standings(item.get('rows'))
            old=old_leagues.get(league)
            old_at=stamp(old.get('standingsAt') or old.get('capturedAt')) if isinstance(old,dict) else None
            if isinstance(old,dict) and old_at and old_at>=captured and isinstance(old.get('standings'),list):
                result[league]=old;preserved+=1
            else:
                result[league]={'name':str(item.get('name') or league)[:100],
                    'category':str(item.get('category') or '')[:100],
                    'competition':str(item.get('competition') or '')[:100],
                    'leagueId':str(item.get('leagueId') or '')[:30],
                    'capturedAt':captured.isoformat(),'standingsAt':captured.isoformat(),
                    'url':str(item.get('url') or '')[:500],'standings':rows}
                updated+=1
            total+=len(result[league]['standings'])
        # Conserva classificacions antigues que una passada incompleta no hagi inclòs.
        for league,item in old_leagues.items():
            if league not in result and isinstance(item,dict) and norm(item.get('name')) not in incoming_names:result[league]=item
        content={'schema':'zonaok-classificacions-v2','capturedAt':captured.isoformat(),
            'competitions':result}
        return filename,content,{'classificacions_actualitzades':updated,
            'conservades_mes_recents':preserved,'classificacions':len(result),'equips':total}
    incoming=packet.get('rows')
    if not isinstance(incoming,list) or not incoming or len(incoming)>300:raise ValueError('Files buides o massa nombroses')
    if kind in ('standings','classificacio-v27','classificacio-v25'):
        league=str(packet.get('league') or '')
        if league not in LEAGUES:raise ValueError('Lliga desconeguda')
        filename=f'zonaok-classificacio-{league}.json'
        existing=read_json(filename)
        if existing is not None and not isinstance(existing,dict):raise ValueError('Fitxer classificació mal format')
        existing=existing or {}
        if existing and (str(existing.get('league') or '')!=league or existing.get('schema') not in ('zonaok-classificacio-v1','zonaok-classificacio-v27')):
            raise ValueError('Esquema de classificació incompatible; cap sobreescriptura')
        rows=clean_standings(incoming)
        old_at=stamp(existing.get('standingsAt') or existing.get('capturedAt'))
        if existing.get('standings') and old_at and old_at>=captured:
            return filename,existing,{'conservada_classificacio_mes_recent':len(existing['standings'])}
        return filename,{'schema':'zonaok-classificacio-v1','league':league,
            'capturedAt':captured.isoformat(),'standingsAt':captured.isoformat(),'standings':rows}, {'equips':len(rows),'lliga':league}
    if kind in ('resultats-v27','resultats-v25','resultats-v5'):
        filename='zonaok-data.json'
        doc=read_json(filename)
        if doc is None:raise ValueError('No existeix zonaok-data.json. No es crearà una Agenda buida.')
        return filename,*update_scores(copy.deepcopy(doc),incoming,captured)
    raise ValueError('Tipus d’importació no permès (Agenda no es modifica en aquest workflow): '+str(kind))


def run():
    raw=decode_payload(os.environ.get('ZONAOK_PAYLOAD_B64',''))
    if raw.startswith(b'\x1f\x8b'):raw=gzip.decompress(raw)
    packet=json.loads(raw.decode('utf-8'))
    root=Path(os.environ.get('GITHUB_WORKSPACE') or '.').resolve()
    def load(filename):
        path=root/filename
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    filename,content,diagnostic=apply(packet,load)
    path=root/filename
    new=json.dumps(content,ensure_ascii=False,indent=2)+'\n'
    if not path.exists() or path.read_text(encoding='utf-8')!=new:
        path.write_text(new,encoding='utf-8')
    print('FITXER:',filename)
    print('RESULTAT:',json.dumps(diagnostic,ensure_ascii=False))
    return filename


if __name__=='__main__':
    try:run()
    except (ValueError,KeyError,TypeError,UnicodeError,json.JSONDecodeError) as exc:
        sys.exit('ERROR: NO s’ha escrit res. '+str(exc))
