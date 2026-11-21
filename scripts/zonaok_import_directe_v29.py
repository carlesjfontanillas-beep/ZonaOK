#!/usr/bin/env python3
"""ZonaOK V29.5: marcador FECAPA -> files JA EXISTENTS a data.agenda.rows.

Llegeix captures `imports/directe/v29/directe-*.json`. Només modifica
`homeScore`, `awayScore`, `scoreCapturedAt`, `scoreSource` de partits amb
correspondència unívoca; conserva data/hora, pista, identificadors, equips,
classificacions, actes i `agenda.capturedAt` (data de captura de l'Agenda).
NO utilitza localStorage ni crea partits.
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
from urllib.parse import urlparse, parse_qs

INBOX = Path('imports/directe/v29')
TARGET = Path('zonaok-data.json')
MAX_ROWS = 1500
MAX_BYTES = 900_000


def utc(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def norm(value):
    s = unicodedata.normalize('NFD', str(value or '')).upper()
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


def team(value):
    """Identitat estricta: no confon veterans, ni Sant Celoni A amb B."""
    s = norm(value)
    compact = s.replace(' ', '')
    if compact in ('FCBETRANS', 'FCBETERANS'):
        return 'FC BARCELONA VETERANS'
    if s in ('BAR', 'BARCA', 'FC BARCELONA', 'F C BARCELONA'):
        return 'BARCA'
    m = re.fullmatch(r'CPSC([A-Z0-9]{0,2})', compact)
    if m:
        return 'CP SANT CELONI' + (' '+m[1] if m[1] else '')
    m = re.fullmatch(r'(?:CP|C P) SANT CELONI(?: ([A-Z]))?', s)
    if m:
        return 'CP SANT CELONI' + (' '+m[1] if m[1] else '')
    return s


def valid_date(date, hour):
    if not re.fullmatch(r'20\d{2}-\d\d-\d\d', date):
        return False
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', hour):
        return False
    try:
        datetime.strptime(date+' '+hour,'%Y-%m-%d %H:%M')
        return True
    except ValueError:
        return False


def goal(value):
    if isinstance(value, bool) or value is None:
        return None
    s = str(value).strip()
    return int(s) if re.fullmatch(r'\d{1,3}', s) and int(s) < 200 else None


def parse_result(raw):
    if isinstance(raw, list):
        if len(raw) < 7:
            raise ValueError('Fila de resultats amb menys de 7 columnes')
        raw = dict(zip(('iso','time','competition','home','away',
                        'homeScore','awayScore','id'), raw))
    if not isinstance(raw, dict):
        raise ValueError('Fila de resultats no vàlida')
    date = str(raw.get('iso') or '').strip()
    hour = str(raw.get('time') or '').strip()
    if not valid_date(date, hour):
        raise ValueError('Resultat amb data/hora invàlides: '+date+' '+hour)
    comp = str(raw.get('competition') or '').strip()
    home = str(raw.get('home') or '').strip()
    away = str(raw.get('away') or '').strip()
    if not home or not away or len(home)>240 or len(away)>240 or len(comp)>240:
        raise ValueError('Resultat amb noms incomplets o massa llargs')
    h=goal(raw.get('homeScore'))
    a=goal(raw.get('awayScore'))
    if h is None or a is None:
        raise ValueError('Resultat incomplet: '+home+' - '+away)
    return {'iso':date,'time':hour,'competition':comp,'home':home,'away':away,
            'homeScore':h,'awayScore':a,'id':str(raw.get('id') or '').strip()}


def read_packet(packet):
    if not isinstance(packet, dict) or packet.get('source')!='FECAPA-SAFARI' or packet.get('kind')!='resultats-v29':
        raise ValueError('El fitxer no és una captura oficial resultats-v29')
    # A partir de V29.2 En directe NO es pot importar des de /ag/.
    origin=urlparse(str(packet.get('url') or ''))
    if (origin.scheme!='https' or origin.hostname not in ('www.hoqueipatins.fecapa.cat','hoqueipatins.fecapa.cat')
            or origin.path not in ('','/') or 'liga' in parse_qs(origin.query)):
        raise ValueError('En directe ha de venir de la portada FECAPA, no de /ag/')
    captured=utc(packet.get('capturedAt'))
    if not captured:
        raise ValueError('Data de captura UTC invàlida')
    incoming=packet.get('rows')
    if not isinstance(incoming,list) or not 1 <= len(incoming) <= MAX_ROWS:
        raise ValueError('Paquet sense resultats o amb massa files')
    rows=[parse_result(raw) for raw in incoming]
    seen={}
    for r in rows:
        key=(r['iso'],r['time'],norm(r['competition']),norm(r['home']),norm(r['away']))
        if key in seen and (seen[key]['homeScore'],seen[key]['awayScore'])!=(r['homeScore'],r['awayScore']):
            raise ValueError('Dos marcadors contradictoris per al mateix partit: '+str(key))
        seen[key]=r
    return captured,list(seen.values())


def comp_compatible(old, new):
    """Categoria general FECAPA vs subgrup d'Agenda, sense igualar categories distintes."""
    a, b = norm(old), norm(new)
    if not b:
        return False
    if a == b:
        return True
    # La portada dona ALEVÍ OR, l'Agenda dona ALEVÍ OR 4.
    # Igualtat només quan l'única diferència és el número final de grup.
    if re.fullmatch(re.escape(b) + r' [0-9]{1,2}', a):
        return True
    return False


def alias_forms(full):
    """Formes abreujades de FECAPA. Sempre es validen amb dia/hora/rol/rival.

    Les abreviatures no s'utilitzen mai com a prova suficient per si soles.
    """
    name = norm(full)
    t = name.split()
    forms = {name.replace(' ', '')}
    # Inicials del nom complet, i sense termes genèrics de club.
    if len(t) >= 2:
        forms.add(''.join(w[0] for w in t))
    stripped = [w for w in t if w not in {
        'CLUB','PATI','PATINS','CLUBS','HOQUEI','HOCKEY','HC','CH','CP','CHP','FUTBOL'}]
    if stripped and len(stripped) >= 2:
        forms.add(''.join(w[0] for w in stripped))
    # FECAPA abreuja sovint CH OLOT com CHO, CP VOLTREGA A com CPVA.
    # Amb noms complets (CLUB PATI VOLTREGA A) creem CPVA.
    if len(t) >= 2 and t[0] in ('CH','CP','HC','CHP'):
        forms.add(t[0] + ''.join(w[0] for w in t[1:]))
    if len(t) >= 3 and t[:2] == ['CLUB', 'PATI']:
        forms.add('CP' + ''.join(w[0] for w in t[2:]))
    # SAF/SAFB: abreviació registrada per al CHP Sant Feliu (B).
    # El sufix B es conserva, mai s'iguala SAFB amb SAF.
    if len(t) >= 3 and 'SANT' in t and 'FELIU' in t:
        ix=t.index('SANT')
        if ix+1 < len(t) and t[ix+1] == 'FELIU':
            suffix=t[-1] if t[-1] in ('A','B','C','D') else ''
            forms.add('SAF'+suffix)
    # AH C Andorra: la sigla pròpia AHC és la primera paraula.
    if t and len(t[0]) >= 3:
        forms.add(t[0])
    return forms


def team_compatible(full, short):
    """CPSC/CPSCA/CPSCB = CLUB, NO equip concret; desambigua per partit.

    Prioritza equivalències literais i abreviatures derivables; NO compara
    només el club favorit quan el rival és desconegut.
    """
    a=team(full)
    b=team(short)
    if a == b:
        return True
    c=norm(short).replace(' ', '')
    target=norm(full)
    # Variant de sigles CPSC indiferent de l'equip A/B, perquè a FECAPA
    # CPSC pot identificar tots dos. La distinció ve de la data, hora,
    # categoria, rival i lloc (local/visitant).
    if c in ('CPSC','CPSCA','CPSCB') and re.fullmatch(
        r'(?:CP|CLUB PATI|C P)? ?SANT CELONI(?: [A-D])?',target):
        return True
    if c in ('BAR','BARCA','FCB') and target in ('BARCA','FC BARCELONA','F C BARCELONA'):
        return True
    if c in ('FCBV','FCBETRANS','FCBETERANS') and target in ('FCBETRANS','FCBETERANS'):
        return True
    if c in alias_forms(full):
        return True
    # Aliases coneguts i verificats amb dates/hores de la temporada.
    # No inventem variants de rival que no es poden acreditar.
    specific = {
        'CPVA': ('CLUB PATI VOLTREGA A', 'CP VOLTREGA A'),
        'CPVB': ('CLUB PATI VOLTREGA B', 'CP VOLTREGA B'),
        'AHC': ('AHC ANDORRA',),
        'CHO': ('CH OLOT',),
        'SAF': ('CHP SANT FELIU',),
        'SAFB': ('CHP SANT FELIU B',),
    }
    return target in specific.get(c, ())


def comparable(old, new, require_comp=True):
    """Primer fem l'emparellament estricte; després, sense categoria.

    La categoria de la portada pot ser incorrecta (l'ordre del DOM pot
    barrejar seccions). El mode flexible CONTINUA exigint la mateixa data,
    hora, equip local i equip visitant. Mai accepta dues coincidències.
    """
    if not isinstance(old, dict):
        return False
    old_id = str(old.get('id') or '').strip()
    new_id = new['id']
    if old_id and new_id:
        return old_id == new_id
    if str(old.get('iso') or '') != new['iso']:
        return False
    if str(old.get('time') or '') != new['time']:
        return False
    if not (team_compatible(old.get('home'), new['home'])
            and team_compatible(old.get('away'), new['away'])):
        return False
    if require_comp and not comp_compatible(old.get('competition'), new['competition']):
        return False
    return True


def select_unique(output, incoming):
    """Retorna índex únic i mètode, o cap índex si és ambigu/inexistent."""
    strict = [i for i, old in enumerate(output)
              if comparable(old, incoming, require_comp=True)]
    if len(strict) == 1:
        return strict[0], 'categoria_confirmada', len(strict)
    if len(strict) > 1:
        return None, 'ambigu_amb_categoria', len(strict)

    # Només abandonem la categoria si el partit continua sent únic amb
    # les QUATRE condicions següents: data, hora, local i visitant.
    relaxed = [i for i, old in enumerate(output)
               if comparable(old, incoming, require_comp=False)]
    if len(relaxed) == 1:
        return relaxed[0], 'categoria_no_fiable_pero_partit_unic', len(relaxed)
    return None, ('ambigu_sense_categoria' if relaxed else 'sense_partit'), len(relaxed)


def unmatched_detail(output, r, reason, num):
    """Dades de diagnòstic, sense modificar mai l'Agenda."""
    same_day = [x for x in output if isinstance(x, dict)
                and str(x.get('iso') or '') == r['iso']]
    same_day_hour = [x for x in same_day
                     if str(x.get('time') or '') == r['time']]
    same_teams_day = [x for x in same_day
                      if team_compatible(x.get('home'), r['home'])
                      and team_compatible(x.get('away'), r['away'])]
    return {
        'dia': r['iso'], 'hora': r['time'],
        'local': r['home'], 'visitant': r['away'],
        'competicio_portada': r['competition'],
        'motiu': reason, 'coincidencies': num,
        'partits_agenda_dia': len(same_day),
        'partits_agenda_dia_hora': len(same_day_hour),
        'candidats_equips_mateix_dia': [
            {'hora':x.get('time'), 'competicio':x.get('competition'),
             'local':x.get('home'), 'visitant':x.get('away')}
            for x in same_teams_day[:4]
        ],
        'candidats_dia_hora': [
            {'competicio':x.get('competition'), 'local':x.get('home'),
             'visitant':x.get('away')}
            for x in same_day_hour[:4]
        ]
    }


def accepted_matches(output, incoming):
    """Deduplica les correspondències per ID/partit i frena conflictes.

    Si dos resultats FECAPA diferents intenten escriure al mateix partit,
    només s'accepten si els marcadors són idèntics. Si son diferents,
    parem TOTA la importació abans de modificar el JSON.
    """
    claims={}
    diagnostics=[]
    for r in incoming:
        index,mode,num=select_unique(output,r)
        diagnostics.append((r,index,mode,num))
        if index is None:
            continue
        if index in claims:
            p=claims[index]
            if (p['homeScore'],p['awayScore']) != (r['homeScore'],r['awayScore']):
                raise ValueError('Dues captures incompatibles reclamen el mateix partit Agenda: '
                                 +str(r['iso'])+' '+str(r['time'])+' '+r['home']+' vs '+r['away'])
        else:
            claims[index]=r
    return diagnostics


def merge(existing, captured, incoming):
    if not isinstance(existing,dict) or existing.get('version')!=3 or not isinstance(existing.get('data'),dict):
        raise ValueError('zonaok-data.json no té el format compatible version=3/data')
    ag=existing['data'].get('agenda')
    if not isinstance(ag,dict) or not isinstance(ag.get('rows'),list) or not ag['rows']:
        raise ValueError('Falta una Agenda publicada; no es crearà cap partit nou')
    if len(ag['rows'])>20000:
        raise ValueError('Agenda massa gran o danyada')
    doc=copy.deepcopy(existing)
    output=doc['data']['agenda']['rows']
    count_before=len(output)
    applied=matched=unchanged=outdated=match_sense_categoria=0
    unmatched=[]
    for r, index, mode, num in accepted_matches(output, incoming):
        if index is None:
            unmatched.append(unmatched_detail(output, r, mode, num))
            continue
        old=output[index]
        matched+=1
        if mode == 'categoria_no_fiable_pero_partit_unic':
            match_sense_categoria+=1
        old_stamp=utc(old.get('scoreCapturedAt'))
        if not old_stamp and goal(old.get('homeScore')) is not None and goal(old.get('awayScore')) is not None:
            old_stamp=utc(old.get('capturedAt'))
        if old_stamp and old_stamp>captured:
            outdated+=1
            continue
        if goal(old.get('homeScore'))==r['homeScore'] and goal(old.get('awayScore'))==r['awayScore']:
            unchanged+=1
            continue
        old['homeScore']=r['homeScore']
        old['awayScore']=r['awayScore']
        old['scoreCapturedAt']=captured.isoformat(timespec='seconds')
        old['scoreSource']='FECAPA En directe V29.5'
        applied+=1
    if not matched:
        raise ValueError('Cap resultat coincideix de forma unica amb l Agenda. ' +
                         'Primers casos: ' + json.dumps(unmatched[:4], ensure_ascii=False))
    if len(output)!=count_before:
        raise AssertionError('En directe ha alterat el recompte de partits')
    if applied:
        doc['data']['agenda']['scoresAt']=captured.isoformat(timespec='seconds')
        doc['publishedAt']=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    # Darrera importacio En directe, sempre visible a l'app, encara que
    # tots els marcadors ja siguin iguals. No modifica la data d'Agenda.
    # No es sobreescriu amb una captura cronologicament anterior.
    old_summary=ag.get('directeImport') if isinstance(ag.get('directeImport'), dict) else {}
    old_processed=utc(old_summary.get('capturedAt')) if old_summary else None
    if not old_processed or captured >= old_processed:
        doc['data']['agenda']['directeImport']={
            'capturedAt':captured.isoformat(timespec='seconds').replace('+00:00','Z'),
            'source':'FECAPA principal · En directe',
            'received':len(incoming),
            'matched':matched,
            'matchedWithoutCategory':match_sense_categoria,
            'changed':applied,
            'unchanged':unchanged,
            'outdated':outdated,
            'unmatched':len(unmatched),
            'totalAgenda':count_before
        }
        if doc['data']['agenda']['directeImport']!=old_summary and not applied:
            doc['publishedAt']=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    # No es canvia mai data.agenda.capturedAt ni cap altra seccio del document.
    if doc['data']['agenda'].get('capturedAt')!=ag.get('capturedAt'):
        raise AssertionError('La data general d’Agenda s’ha alterat')
    if doc['data']['agenda'].get('sourceCapturedAt')!=ag.get('sourceCapturedAt'):
        raise AssertionError('La data de la captura d’Agenda s’ha alterat')
    for name,value in existing['data'].items():
        if name!='agenda' and doc['data'].get(name)!=value:
            raise AssertionError('S’ha alterat una secció aliena a Agenda: '+name)
    for old,new in zip(ag['rows'],output):
        for key in old:
            if key not in ('homeScore','awayScore','scoreCapturedAt','scoreSource') and old[key]!=new.get(key):
                raise AssertionError('S’ha alterat informació protegida del partit: '+key)
    return doc, {'marcadors_canviats':applied,'partits_coincidents':matched,
                 'ja_iguals':unchanged,'coincidents_sense_categoria':match_sense_categoria,'descartats_per_antiguitat':outdated,
                 'sense_match_o_ambigus':len(unmatched),
                 'mostres_no_corresponents':unmatched[:15],
                 'total_agenda':count_before,'total_importat':len(incoming)}


def load_json_checked(path, description):
    """Diagnostica el fitxer exacte que no es pot descodificar.

    Quan la drecera envia un ERROR: com a Base64, GitHub desa
    un fitxer de text en comptes de JSON; no s'ha de tocar l'Agenda.
    """
    content = path.read_text(encoding='utf-8')
    if not content.strip():
        raise ValueError(
            f'{description}: fitxer buit ({path}). '
            'La drecera no ha retornat cap JSON. Revisa Resultado de JavaScript.'
        )
    if content.lstrip().startswith('ERROR:'):
        detail = content.strip().replace('\r', ' ').replace('\n', ' ')[:250]
        raise ValueError(
            f'{description}: la drecera ha publicat un ERROR en lloc del JSON. '
            f'Fitxer: {path}. Detall: {detail}. '
            'Afegeix la condicio Si Resultado de JavaScript comença per ERROR: '
            '→ Mostrar resultado → Detener este atajo.'
        )
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        preview = content[:160].replace('\r', ' ').replace('\n', ' ')
        raise ValueError(
            f'{description}: JSON invàlid al fitxer {path} '
            f'(línia {exc.lineno}, columna {exc.colno}: {exc.msg}). '
            f'Inici del contingut: {preview!r}. '
            'Cap dada modificada.'
        ) from exc
    if not isinstance(result, dict):
        raise ValueError(
            f'{description}: el fitxer {path} ha de contenir un objecte JSON, '
            f'no {type(result).__name__}. Cap dada modificada.'
        )
    return result


def run(root):
    source=root/INBOX
    names=sorted(source.glob('directe-*.json'))
    if not names:
        raise ValueError('No hi ha captures V29 a '+str(INBOX))
    path=names[-1]  # El timestamp del nom és YYYYMMDD-HHMMSS
    if path.stat().st_size>MAX_BYTES:
        raise ValueError('Paquet de resultats massa gran')
    print('CAPTURA V29 SELECCIONADA:', path.relative_to(root), 'bytes=', path.stat().st_size, flush=True)
    packet=load_json_checked(path, 'Captura En directe')
    captured,rows=read_packet(packet)
    print('FILES REBUDES:', len(rows), 'MOSTRES:',
          json.dumps(rows[:6], ensure_ascii=False), flush=True)
    dest=root/TARGET
    if not dest.exists():
        raise ValueError('Falta zonaok-data.json, no es crearà un fitxer buit')
    before=load_json_checked(dest, 'JSON compartit de ZonaOK')
    doc,stats=merge(before,captured,rows)
    if doc!=before:
        dest.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('FITXER ORIGEN:',path.relative_to(root))
    print('CAPTURAT:',packet['capturedAt'])
    print('DIAGNÒSTIC:',json.dumps(stats,ensure_ascii=False))
    return stats


if __name__=='__main__':
    try:
        run(Path(os.environ.get('GITHUB_WORKSPACE') or '.').resolve())
    except (ValueError,KeyError,TypeError,UnicodeError,json.JSONDecodeError,AssertionError) as exc:
        sys.exit('ERROR EN DIRECTE V29.5: cap dada modificada. '+str(exc))
