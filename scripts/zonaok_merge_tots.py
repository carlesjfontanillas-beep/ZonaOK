#!/usr/bin/env python3
"""ZonaOK · Tots els clubs · consolidació independent (v2).

L'AGENDA és l'únic catàleg de partits. EN DIRECTE només actualitza les
seves files si la coincidència és única. No crea partits nous.

Entrades (captures manuals de Safari pujades a GitHub):
  imports/tots-agenda-import.json
  imports/tots-directe-import.json
Publicacions:
  zonaok-tots-agenda.json
  zonaok-tots-resultats-7dies.json
No modifica el JSON antic de Barça/Sant Celoni, les actes ni altres menús.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Europe/Madrid')
SCHEMA = 'zonaok-all-v1'
MAX_ROWS = 60000
DATE = re.compile(r'20\d{2}-\d{2}-\d{2}\Z')
HOUR = re.compile(r'(?:[01]\d|2[0-3]):[0-5]\d\Z')
FIELDS = ('iso', 'time', 'competition', 'home', 'away', 'homeScore', 'awayScore',
          'venue', 'homeLogo', 'awayLogo', 'matchId', 'leagueId', 'actaUrl', 'status', 'round')
TEXT_FIELDS = tuple(f for f in FIELDS if f not in ('homeScore', 'awayScore'))
LIVE_STATUSES = ('EN JOC', 'EN DIRECTE', 'LIVE', 'PLAYING', 'IN PROGRESS', 'DESCANS',
                 'PRIMERA PART', 'SEGONA PART', '1A PART', '2A PART', 'HALF TIME')


def norm(value):
    s = unicodedata.normalize('NFD', str(value or ''))
    return re.sub(r'[^A-Z0-9]+', ' ', ''.join(c for c in s if not unicodedata.combining(c)).upper()).strip()


def alias(name):
    n = norm(name)
    # Equivalències documentades de ZonaOK. Sense aproximacions genèriques.
    if re.fullmatch(r'(?:BAR|BARCA|FC BARCELONA|F C BARCELONA|FCBETRANS|FCBETERANS)(?: [AB])?', n):
        suffix = n[-1] if n.endswith((' A', ' B')) else ''
        return 'BARCA' + (' ' + suffix if suffix else '')
    m = re.fullmatch(r'CPSC ?([AB])?', n)
    if m:
        return 'SANT CELONI' + (' ' + m[1] if m[1] else '')
    m = re.fullmatch(r'(?:CP )?SANT CELONI(?: ([AB]))?', n)
    if m:
        return 'SANT CELONI' + (' ' + m[1] if m[1] else '')
    return n


def stamp(s):
    try:
        d = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc).timestamp() if d.tzinfo else -1
    except (TypeError, ValueError, OverflowError):
        return -1


def season_for(now):
    first = now.year if now.month >= 7 else now.year - 1
    return f'{first}/{first+1}'


def validate_row(raw):
    if not isinstance(raw, dict):
        raise ValueError('Fila no és objecte JSON')
    iso, time = str(raw.get('iso') or ''), str(raw.get('time') or '')
    if not DATE.fullmatch(iso) or not HOUR.fullmatch(time):
        raise ValueError(f'Data/hora invàlida: {iso!r} {time!r}')
    try:
        if datetime.fromisoformat(iso).strftime('%Y-%m-%d') != iso:
            raise ValueError('Data invàlida')
    except ValueError:
        raise ValueError(f'Data invàlida: {iso}') from None
    row = {f: str(raw.get(f) or '').strip()[:400] for f in TEXT_FIELDS}
    row['iso'], row['time'] = iso, time
    row['home'], row['away'] = row['home'][:180], row['away'][:180]
    if not row['home'] or not row['away'] or norm(row['home']) == norm(row['away']):
        raise ValueError('Equips buits o iguals')
    for f in ('homeScore', 'awayScore'):
        value = raw.get(f)
        row[f] = value if type(value) is int and 0 <= value <= 199 else None
    if (row['homeScore'] is None) != (row['awayScore'] is None):
        row['homeScore'] = row['awayScore'] = None
    if not re.fullmatch(r'\d{4,10}', row['matchId']):
        row['matchId'] = ''
    if not re.fullmatch(r'\d{3,10}', row['leagueId']):
        row['leagueId'] = ''
    if not re.fullmatch(r'https://(?:www\.)?hoqueipatins\.fecapa\.cat/[^\s]*', row['actaUrl']):
        row['actaUrl'] = ''
    for logo in ('homeLogo', 'awayLogo'):
        if not re.fullmatch(r'https://sidgad\.cloud/fecapa/images/logos_clubes/\d+\.png', row[logo]):
            row[logo] = ''
    row['agendaUpdatedAt'] = str(raw.get('agendaUpdatedAt') or '')
    row['scoreUpdatedAt'] = str(raw.get('scoreUpdatedAt') or '')
    row['scoreSource'] = str(raw.get('scoreSource') or '')
    row['directeUpdatedAt'] = str(raw.get('directeUpdatedAt') or '')
    return row


def strict_key(r):
    return r['iso'], r['time'], norm(r.get('competition')), norm(r['home']), norm(r['away'])


def team_key(r):
    return r['iso'], r['time'], alias(r['home']), alias(r['away'])


class AgendaIndex:
    """Indexa partits un sol cop: cerca per ID, clau exacta o equips+hora.

    Reprodueix la prioritat i els vetos originals de search_target, però
    evita fer 12.000 * 12.000 recorreguts durant la importació completa.
    """
    def __init__(self, agenda):
        self.agenda = agenda
        self.ids = defaultdict(set)
        self.strict = defaultdict(set)
        self.teams = defaultdict(set)
        for i, row in enumerate(agenda):
            self.add(i, row)

    def add(self, i, row):
        if row['matchId']:
            self.ids[row['matchId']].add(i)
        self.strict[strict_key(row)].add(i)
        self.teams[team_key(row)].add(i)

    def remove(self, i, row):
        if row['matchId']:
            self.ids[row['matchId']].discard(i)
        self.strict[strict_key(row)].discard(i)
        self.teams[team_key(row)].discard(i)

    def find(self, source_row, *, allow_alias):
        ident = source_row['matchId']
        if ident:
            by_id = self.ids.get(ident, ())
            if len(by_id) == 1:
                return next(iter(by_id))
            if len(by_id) > 1:
                return None

        def id_ok(i):
            other = self.agenda[i]['matchId']
            return not (ident and other and ident != other)

        strict = [i for i in self.strict.get(strict_key(source_row), ()) if id_ok(i)]
        if len(strict) == 1:
            return strict[0]
        if strict or not allow_alias:
            return None

        comp = norm(source_row['competition'])
        candidates = [i for i in self.teams.get(team_key(source_row), ())
                      if id_ok(i) and
                      (not comp or not norm(self.agenda[i]['competition']) or
                       norm(self.agenda[i]['competition']) == comp)]
        return candidates[0] if len(candidates) == 1 else None


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def capture(kind, current_season):
    path = ROOT / 'imports' / f'tots-{kind}-import.json'
    packet = load(path)
    if packet is None:
        return None
    if not isinstance(packet, dict) or packet.get('schema') != SCHEMA or packet.get('kind') != kind:
        raise ValueError(f'Captura {kind}: esquema o tipus incorrectes')
    raw = packet.get('rows')
    if not isinstance(raw, list) or len(raw) > MAX_ROWS:
        raise ValueError(f'Captura {kind}: nombre de files incorrecte')
    if not raw:  # marcadors buits que venen dins del ZIP: no alteren res
        return None
    if packet.get('season') != current_season:
        raise ValueError(f'Captura {kind}: temporada {packet.get("season")} ≠ {current_season}')
    moment = str(packet.get('capturedAt') or '')
    if stamp(moment) < 0:
        raise ValueError(f'Captura {kind}: capturedAt invàlid')
    rows = []
    for index, r in enumerate(raw, 1):
        try:
            rows.append(validate_row(r))
        except ValueError as ex:
            raise ValueError(f'Captura {kind}: fila {index}: {ex}') from ex
    return rows, moment


def search_target(agenda, source_row, *, allow_alias):
    """Retorna l'índex NOMÉS si existeix un sol partit compatible.

    Dos ID diferents són un veto: un marcador no ha de saltar de partit.
    La comparació abreujada necessita categoria compatible i unicitat.
    """
    ident = source_row['matchId']
    if ident:
        by_id = [i for i, a in enumerate(agenda) if a['matchId'] == ident]
        if len(by_id) == 1:
            return by_id[0]
        if len(by_id) > 1:
            return None
    candidates = []
    for i, a in enumerate(agenda):
        if ident and a['matchId'] and ident != a['matchId']:
            continue
        if strict_key(a) == strict_key(source_row):
            candidates.append(i)
    if len(candidates) == 1:
        return candidates[0]
    if candidates or not allow_alias:
        return None
    candidates = []
    for i, a in enumerate(agenda):
        if ident and a['matchId'] and ident != a['matchId']:
            continue
        if team_key(a) != team_key(source_row):
            continue
        ca, cb = norm(a['competition']), norm(source_row['competition'])
        if ca and cb and ca != cb:
            continue
        candidates.append(i)
    return candidates[0] if len(candidates) == 1 else None


def merge_agenda(existing, incoming):
    """Només AGENDA pot crear partits. La captura posterior enriqueix, no esborra."""
    if incoming is None:
        return existing, {'added': 0, 'updated': 0}
    rows, captured = incoming
    added = updated = 0
    index = AgendaIndex(existing)
    for r in rows:
        found = index.find(r, allow_alias=False)
        if found is None:
            item = dict(r)
            item['agendaUpdatedAt'] = captured
            if item['homeScore'] is not None:
                item['scoreUpdatedAt'] = captured
                item['scoreSource'] = 'Agenda'
            existing.append(item)
            index.add(len(existing)-1, item)
            added += 1
            continue
        previous = existing[found]
        if stamp(captured) < stamp(previous.get('agendaUpdatedAt')):
            continue
        item = dict(previous)
        for field in TEXT_FIELDS:
            if r.get(field):
                # No deixar que Agenda esborri un estat EN DIRECTE més recent.
                if field == 'status' and stamp(captured) < stamp(previous.get('directeUpdatedAt')):
                    continue
                item[field] = r[field]
        if r['homeScore'] is not None and stamp(captured) >= stamp(previous.get('scoreUpdatedAt')):
            item['homeScore'] = r['homeScore']
            item['awayScore'] = r['awayScore']
            item['scoreUpdatedAt'] = captured
            item['scoreSource'] = 'Agenda'
        item['agendaUpdatedAt'] = captured
        index.remove(found, previous)
        existing[found] = item
        index.add(found, item)
        updated += 1
    return existing, {'added': added, 'updated': updated}


def merge_directe(agenda, incoming):
    """Llegeix EN DIRECTE; no afegeix MAI cap fila."""
    stats = {'read': 0, 'matched': 0, 'unmatchedOrAmbiguous': 0, 'updatedScores': 0}
    if incoming is None:
        return stats
    rows, captured = incoming
    # Unicitat també a la captura: dues files amb mateix ID/parella no són segures.
    matched = defaultdict(list)
    index = AgendaIndex(agenda)
    for r in rows:
        stats['read'] += 1
        i = index.find(r, allow_alias=True)
        if i is None:
            stats['unmatchedOrAmbiguous'] += 1
        else:
            matched[i].append(r)
    for i, options in matched.items():
        if len(options) != 1:
            stats['unmatchedOrAmbiguous'] += len(options)
            continue
        d = options[0]
        old = agenda[i]
        if stamp(captured) < stamp(old.get('directeUpdatedAt')):
            continue
        new = dict(old)
        for f in ('homeLogo', 'awayLogo', 'matchId', 'leagueId', 'actaUrl', 'round', 'status'):
            if d.get(f) and (f != 'matchId' or not old.get('matchId')):
                new[f] = d[f]
        if d['homeScore'] is not None and stamp(captured) >= stamp(old.get('scoreUpdatedAt')):
            new['homeScore'], new['awayScore'] = d['homeScore'], d['awayScore']
            new['scoreUpdatedAt'], new['scoreSource'] = captured, 'En directe'
            stats['updatedScores'] += 1
        new['directeUpdatedAt'] = captured
        agenda[i] = new
        stats['matched'] += 1
    return stats


def public_agenda(agenda, season, now, original):
    rows = sorted(agenda, key=lambda r: (r['iso'], r['time'], norm(r['competition']), norm(r['home']), norm(r['away']), r['matchId']))
    old_rows = original.get('rows', []) if original else []
    old_rows = [validate_row(r) for r in old_rows]
    data = {'schema': SCHEMA, 'kind': 'agenda', 'season': season, 'source': 'FECAPA-SAFARI',
            'publishedAt': now.isoformat(timespec='seconds'), 'count': len(rows), 'rows': rows}
    if rows != old_rows:
        write(ROOT / 'zonaok-tots-agenda.json', data)
    return rows


def is_live(status):
    return any(s in norm(status) for s in LIVE_STATUSES)


def seven_days(agenda, season, now):
    from_time = now - timedelta(days=7)
    window = []
    for row in agenda:
        event = datetime.fromisoformat(row['iso'] + 'T' + row['time']).replace(tzinfo=TZ)
        if not (from_time <= event <= now):
            continue
        if row['homeScore'] is None or row['awayScore'] is None or is_live(row.get('status')):
            continue
        window.append(row)
    window.sort(key=lambda r: (r['iso'], r['time']), reverse=True)
    packet = {'schema': SCHEMA, 'kind': 'resultats-7dies', 'season': season,
              'publishedAt': now.isoformat(timespec='seconds'), 'agendaCount': len(agenda),
              'range': {'from': from_time.isoformat(timespec='minutes'),
                        'to': now.isoformat(timespec='minutes')}, 'rows': window}
    old = load(ROOT / 'zonaok-tots-resultats-7dies.json')
    # Comparar files (i dates del període a precisió de dia): evita commit cada execució sense canvis.
    if old is None or old.get('rows') != window or old.get('agendaCount') != len(agenda) or \
       old.get('range', {}).get('to', '')[:10] != packet['range']['to'][:10]:
        write(ROOT / 'zonaok-tots-resultats-7dies.json', packet)
    return len(window)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    now = datetime.now(TZ)
    season = season_for(now)
    original = load(ROOT / 'zonaok-tots-agenda.json')
    if original and (original.get('schema') != SCHEMA or original.get('kind') != 'agenda' or
                     not isinstance(original.get('rows'), list)):
        raise ValueError('JSON públic de l’Agenda té un format invàlid')
    agenda = [validate_row(r) for r in (original.get('rows', []) if original else [])]
    imported_agenda = capture('agenda', season)
    imported_directe = capture('directe', season)
    agenda, stats_a = merge_agenda(agenda, imported_agenda)
    stats_d = merge_directe(agenda, imported_directe)
    agenda = public_agenda(agenda, season, now, original)
    count = seven_days(agenda, season, now)
    print(f'AGENDA: {len(agenda)} partits · nous {stats_a["added"]} · revisats {stats_a["updated"]}')
    print(f'EN DIRECTE: examinats {stats_d["read"]} · coincidències {stats_d["matched"]} '
          f'· sense coincidència/ambigus {stats_d["unmatchedOrAmbiguous"]} '
          f'· marcadors actualitzats {stats_d["updatedScores"]}')
    print(f'RESULTATS: {count} partits dins dels darrers 7 dies')
    return stats_a, stats_d


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        sys.exit('IMPORTACIÓ REBUTJADA: ' + str(exc))
