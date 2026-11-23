#!/usr/bin/env python3
"""ZonaOK actes_total V2: incorpora URL d'acta a ambdues Agendes.

Nomes enriqueix matchId, leagueId i actaUrl en partits EXISTENTS.
Mai altera partits, marcadors, classificacions ni dades d'altres mòduls.
"""
from __future__ import annotations
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = Path(__file__).resolve().parents[1]
AGENDA = ROOT / 'zonaok-tots-agenda.json'
LEGACY_ACTES = ROOT / 'zonaok-actes.json'
INBOX = ROOT / 'imports' / 'actes-tots'
OUTPUT = ROOT / 'zonaok-tots-actes.json'
MAX_BYTES = 12_000_000
MAX_ROWS = 30_000
ID_RE = re.compile(r'\d{4,10}\Z')
LEAGUE_RE = re.compile(r'\d{3,10}\Z')
DATE_RE = re.compile(r'20\d{2}-\d{2}-\d{2}\Z')
TIME_RE = re.compile(r'(?:[01]\d|2[0-3]):[0-5]\d\Z')


def norm(v):
    s = unicodedata.normalize('NFD', str(v or '')).upper()
    s = ''.join(x for x in s if unicodedata.category(x) != 'Mn')
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


def alias(v):
    s = norm(v)
    if s in ('BAR', 'BARCA', 'FC BARCELONA', 'F C BARCELONA', 'FCBETRANS', 'FCBETERANS'):
        return 'BARCA'
    m = re.fullmatch(r'CPSC ?([AB])?', s)
    if m:
        return 'SANT CELONI' + (' ' + m[1] if m[1] else '')
    s = re.sub(r'^(?:CP|CLUB PATI|C P) ', '', s)
    return s


def match_key(r):
    return '|'.join((str(r.get('iso', '')), str(r.get('time', '')),
                     norm(r.get('competition')), norm(r.get('home')), norm(r.get('away'))))


def load_json(p, *, limit=MAX_BYTES):
    if not p.exists():
        return None
    if p.stat().st_size > limit:
        raise ValueError('Fitxer massa gran: ' + str(p))
    return json.loads(p.read_text(encoding='utf-8-sig'))


def valid_date(s):
    if not DATE_RE.fullmatch(s):
        return False
    try:
        return datetime.fromisoformat(s).strftime('%Y-%m-%d') == s
    except ValueError:
        return False


def canonical_url(league, mid):
    return 'https://www.hoqueipatins.fecapa.cat/?' + urlencode({'liga': league, 'vista': 'calendar', 'partido': mid})


def inspect_link(url, league, mid):
    try:
        u = urlparse(str(url))
        if u.scheme != 'https' or u.hostname not in ('www.hoqueipatins.fecapa.cat', 'hoqueipatins.fecapa.cat'):
            return False
        q = parse_qs(u.query)
        return q.get('liga', [''])[0] == league and q.get('partido', [''])[0] == mid
    except (TypeError, ValueError):
        return False


def read_capture(path):
    packet = load_json(path)
    if not isinstance(packet, dict) or packet.get('source') != 'FECAPA-SAFARI' or packet.get('kind') != 'actes-total-v1' or packet.get('schema') != 'zonaok-actes-total-v1':
        raise ValueError('Captura Actes TOTAL invàlida: ' + str(path))
    rows = packet.get('rows')
    if not isinstance(rows, list) or not (1 <= len(rows) <= MAX_ROWS):
        raise ValueError('Captura buida o massa gran: ' + str(path))
    captured = str(packet.get('capturedAt') or '')
    try:
        dt = datetime.fromisoformat(captured.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError()
    except ValueError as exc:
        raise ValueError('capturedAt invàlid: ' + str(path)) from exc
    src = urlparse(str(packet.get('sourceUrl') or ''))
    if src.scheme != 'https' or src.hostname not in ('www.hoqueipatins.fecapa.cat', 'hoqueipatins.fecapa.cat'):
        raise ValueError('Origen no FECAPA: ' + str(path))
    return rows


def source_row(raw):
    if not isinstance(raw, dict):
        return None
    lid = str(raw.get('leagueId') or raw.get('league') or '').strip()
    mid = str(raw.get('matchId') or raw.get('id') or '').strip()
    iso = str(raw.get('iso') or '').strip()
    time = str(raw.get('time') or '').strip()
    home = str(raw.get('home') or '').strip()[:180]
    away = str(raw.get('away') or '').strip()[:180]
    if not (LEAGUE_RE.fullmatch(lid) and ID_RE.fullmatch(mid) and valid_date(iso) and TIME_RE.fullmatch(time) and home and away and norm(home) != norm(away)):
        return None
    link = raw.get('actaUrl') or canonical_url(lid, mid)
    if not inspect_link(link, lid, mid):
        return None
    return {'leagueId': lid, 'matchId': mid, 'iso': iso, 'time': time,
            'competition': str(raw.get('competition') or '').strip()[:180],
            'home': home, 'away': away, 'actaUrl': canonical_url(lid, mid)}


def collect_sources(root=ROOT):
    sources = {}
    conflicts = set()
    invalid = 0
    files = sorted((root / 'imports' / 'actes-tots').glob('*.json'))
    # Les actes antigues verificades són la primera capa, sense substituir-les mai.
    legacy = load_json(root / 'zonaok-actes.json')
    entries = []
    if isinstance(legacy, dict):
        for r in legacy.get('fixtures', []):
            if isinstance(r, dict):
                entries.append(r)
    for f in files:
        entries.extend(read_capture(f))
    for raw in entries:
        r = source_row(raw)
        if r is None:
            invalid += 1
            continue
        k = (r['leagueId'], r['matchId'])
        if k in conflicts:
            continue
        previous = sources.get(k)
        if previous and (previous['iso'] != r['iso'] or alias(previous['home']) != alias(r['home']) or alias(previous['away']) != alias(r['away'])):
            conflicts.add(k)
            sources.pop(k, None)
        elif previous:
            # No substituïm un enllaç verificat, però podem enriquir la categoria.
            if not previous['competition'] and r['competition']:
                previous['competition'] = r['competition']
        else:
            sources[k] = r
    return list(sources.values()), {'captures': len(files), 'invalidRows': invalid, 'conflictingIds': len(conflicts)}


def find_target(r, agenda, by_id, by_strict, by_dayteams):
    id_matches = by_id.get(r['matchId'], [])
    if id_matches:
        id_matches = [i for i in id_matches if not agenda[i].get('leagueId') or str(agenda[i].get('leagueId')) == r['leagueId']]
        if len(id_matches) == 1:
            return id_matches[0], 'id'
        return None, 'ambiguous'
    strict = (r['iso'], r['time'], norm(r['home']), norm(r['away']))
    options = by_strict.get(strict, [])
    options = [i for i in options if not agenda[i].get('matchId') or str(agenda[i]['matchId']) == r['matchId']]
    options = [i for i in options if not agenda[i].get('leagueId') or str(agenda[i]['leagueId']) == r['leagueId']]
    if len(options) == 1:
        return options[0], 'strict'
    if len(options) > 1:
        return None, 'ambiguous'
    # Opció si l'hora ha canviat: exigim data, ambdós equips i competició compatible.
    # No coincidim només per data o només per club, a diferència dels marcadors.
    if r['competition']:
        key = (r['iso'], alias(r['home']), alias(r['away']))
        possibles = [i for i in by_dayteams.get(key, [])
                     if norm(agenda[i].get('competition')) == norm(r['competition'])
                     and (not agenda[i].get('matchId') or str(agenda[i]['matchId']) == r['matchId'])]
        if len(possibles) == 1:
            return possibles[0], 'dateTeamsCategory'
        if len(possibles) > 1:
            return None, 'ambiguous'
    return None, 'notFound'


def build_overlay(agenda, sources):
    by_id = defaultdict(list)
    by_strict = defaultdict(list)
    by_dayteams = defaultdict(list)
    key_counts = Counter(match_key(r) for r in agenda)
    for i, row in enumerate(agenda):
        mid = str(row.get('matchId') or '')
        if mid:
            by_id[mid].append(i)
        by_strict[(row['iso'], row['time'], norm(row['home']), norm(row['away']))].append(i)
        by_dayteams[(row['iso'], alias(row['home']), alias(row['away']))].append(i)
    assigned = defaultdict(list)
    reasons = Counter()
    for r in sources:
        i, why = find_target(r, agenda, by_id, by_strict, by_dayteams)
        reasons[why] += 1
        if i is not None:
            assigned[i].append(r)
    result = []
    for i, sources_for_row in assigned.items():
        row = agenda[i]
        if len(sources_for_row) != 1 or key_counts[match_key(row)] != 1:
            reasons['ambiguousAssignment'] += 1
            continue
        s = sources_for_row[0]
        # No permetem sobreescriure una acta existent amb un ID diferent.
        oldid = str(row.get('matchId') or '')
        oldurl = str(row.get('actaUrl') or '')
        if oldid and oldid != s['matchId']:
            reasons['conflictingAgendaId'] += 1
            continue
        if oldurl and oldurl != s['actaUrl']:
            reasons['existingActaPreserved'] += 1
            continue
        result.append({'key': match_key(row), 'leagueId': s['leagueId'],
                       'matchId': s['matchId'], 'actaUrl': s['actaUrl']})
    result.sort(key=lambda r: r['key'])
    return result, dict(reasons)


def _augment(row, acta, *, legacy=False):
    """Proteccio contra IDs i URLs incompatibles. Només omple camps buits."""
    for field in ('matchId', 'leagueId'):
        old = str(row.get(field) or '').strip()
        if old and old != acta[field]:
            return False
    old_url = str(row.get('actaUrl') or '').strip()
    if old_url and old_url != acta['actaUrl']:
        return False
    if legacy:
        for field, value in (('id', acta['matchId']), ('league', acta['leagueId'])):
            old = str(row.get(field) or '').strip()
            if old and old != value:
                return False
    changed = False
    for field in ('matchId', 'leagueId', 'actaUrl'):
        if not row.get(field):
            row[field] = acta[field]
            changed = True
    if legacy:
        for field, value in (('id', acta['matchId']), ('league', acta['leagueId'])):
            if not row.get(field):
                row[field] = value
                changed = True
    return changed


def apply_overlay_to_rows(rows, overlay, *, legacy=False):
    """Relaciona els enllaços amb els partits de la taula, sempre un a un."""
    by_key = defaultdict(list)
    by_short = defaultdict(list)
    for i, row in enumerate(rows):
        by_key[match_key(row)].append(i)
        key = (str(row.get('iso') or ''), str(row.get('time') or ''),
               alias(row.get('home')), alias(row.get('away')))
        by_short[key].append(i)
    changed = 0
    rejected = 0
    for a in overlay:
        # La key de l'overlay està construïda des de l'agenda original.
        candidates = by_key.get(a['key'], [])
        if not candidates:
            tokens = a['key'].split('|', 4)
            if len(tokens) == 5:
                # Fallback només si tots dos equips i l'hora coincideixen,
                # sense usar mai un sol club com a identificador.
                key = (tokens[0], tokens[1], alias(tokens[3]), alias(tokens[4]))
                candidates = by_short.get(key, [])
        if len(candidates) != 1:
            rejected += 1
            continue
        row = rows[candidates[0]]
        if _augment(row, a, legacy=legacy):
            changed += 1
    return changed, rejected


def generate(root=ROOT, *, now=None):
    root = Path(root)
    total_path = root / 'zonaok-tots-agenda.json'
    data = load_json(total_path)
    if not isinstance(data, dict) or data.get('schema') != 'zonaok-all-v1' or data.get('kind') != 'agenda' or not isinstance(data.get('rows'), list):
        raise ValueError('Falta Agenda TOTAL valida; no es toca cap fitxer')
    agenda = data['rows']
    legacy_path = root / 'zonaok-data.json'
    legacy = load_json(legacy_path)
    if not isinstance(legacy, dict) or legacy.get('version') != 3 or not isinstance(legacy.get('data', {}).get('agenda', {}).get('rows'), list):
        raise ValueError('Falta zonaok-data.json V3 valid; no es toca cap fitxer')
    classic_actes_path = root / 'zonaok-actes.json'
    classic_actes = load_json(classic_actes_path)
    if not isinstance(classic_actes, dict) or not isinstance(classic_actes.get('fixtures'), list):
        raise ValueError('Falta zonaok-actes.json amb fixtures vàlides; no es toca cap fitxer')
    if any(not isinstance(r, dict) for r in classic_actes['fixtures']):
        raise ValueError('zonaok-actes.json conté una fitxa invàlida; no es toca cap fitxer')
    recent_path = root / 'zonaok-tots-resultats-7dies.json'
    recent = load_json(recent_path)
    if recent is not None and (not isinstance(recent, dict) or recent.get('kind') != 'resultats-7dies' or not isinstance(recent.get('rows'), list)):
        raise ValueError('JSON resultats 7 dies invalid; no es toca cap fitxer')
    sources, stats = collect_sources(root)
    overlay, reasons = build_overlay(agenda, sources)
    previous = load_json(root / 'zonaok-tots-actes.json')
    current_keys = Counter(match_key(r) for r in agenda)
    new_by_key = {r['key']: r for r in overlay}
    if isinstance(previous, dict) and previous.get('schema') == 'zonaok-actes-total-v1':
        for old in previous.get('rows', []):
            if not isinstance(old, dict):
                continue
            key = str(old.get('key') or '')
            lid, mid = str(old.get('leagueId') or ''), str(old.get('matchId') or '')
            if key not in new_by_key and current_keys[key] == 1 and LEAGUE_RE.fullmatch(lid) and ID_RE.fullmatch(mid) and inspect_link(old.get('actaUrl'), lid, mid):
                new_by_key[key] = {k: old[k] for k in ('key', 'leagueId', 'matchId', 'actaUrl')}
    overlay = sorted(new_by_key.values(), key=lambda r: r['key'])
    changed_total, missed_total = apply_overlay_to_rows(agenda, overlay)
    changed_legacy, missed_legacy = apply_overlay_to_rows(legacy['data']['agenda']['rows'], overlay, legacy=True)
    changed_recent, missed_recent = (0, 0)
    if recent is not None:
        changed_recent, missed_recent = apply_overlay_to_rows(recent['rows'], overlay)

    # L'Actes TOTAL també alimenta la llista d'actes del menú clàssic.
    agenda_by_key = {match_key(r): r for r in agenda if current_keys[match_key(r)] == 1}
    fixtures = [dict(r) for r in classic_actes['fixtures']]
    fixture_index = {(str(r.get('league') or ''), str(r.get('id') or '')): i
                     for i, r in enumerate(fixtures)}
    changed_classic = False
    for acta in overlay:
        row = agenda_by_key.get(acta['key'])
        if row is None:
            continue
        if not any(alias(row.get(side)).startswith(('BARCA', 'SANT CELONI'))
                   for side in ('home', 'away')):
            continue
        k = (acta['leagueId'], acta['matchId'])
        item = {'league': acta['leagueId'], 'id': acta['matchId'],
                'iso': row['iso'], 'time': row['time'], 'home': row['home'],
                'away': row['away'], 'competition': row.get('competition', ''),
                'actaUrl': acta['actaUrl']}
        if k in fixture_index:
            i = fixture_index[k]
            old = fixtures[i]
            if old.get('iso') and old['iso'] != item['iso']:
                raise ValueError(f"Conflicte de data a Actes {acta['matchId']}; no es toca cap fitxer")
            if any(old.get(side) and norm(old[side]) != norm(item[side]) for side in ('home', 'away')):
                raise ValueError(f"Conflicte d'equips a Actes {acta['matchId']}; no es toca cap fitxer")
            merged = {**old, **item}
            if merged != old:
                fixtures[i] = merged
                changed_classic = True
        else:
            fixture_index[k] = len(fixtures)
            fixtures.append(item)
            changed_classic = True
    if changed_classic:
        classic_actes['fixtures'] = sorted(fixtures, key=lambda r: (
            str(r.get('iso') or ''), str(r.get('time') or ''),
            str(r.get('league') or ''), str(r.get('id') or '')))
        classic_actes['version'] = 1
        classic_actes['generatedAt'] = (now or datetime.now(timezone.utc)).isoformat(timespec='seconds')
    packet = {'schema': 'zonaok-actes-total-v1', 'kind': 'actes-total',
              'season': data.get('season', ''), 'source': 'FECAPA-SAFARI',
              'publishedAt': (now or datetime.now(timezone.utc)).isoformat(timespec='seconds'),
              'agendaCount': len(agenda), 'count': len(overlay), 'rows': overlay,
              'stats': {'sourceLinks': len(sources), 'captures': stats['captures'],
                        'invalidRows': stats['invalidRows'], 'conflictingIds': stats['conflictingIds'],
                        **reasons, 'agendaTotalUpdated': changed_total,
                        'agendaUpdated': changed_legacy, 'resultsUpdated': changed_recent,
                        'agendaTotalNotFound': missed_total,
                        'agendaNotFound': missed_legacy, 'resultsNotFound': missed_recent}}
    writes = []
    if changed_total:
        writes.append((total_path, data))
    if changed_legacy:
        writes.append((legacy_path, legacy))
    if changed_recent:
        writes.append((recent_path, recent))
    if changed_classic:
        writes.append((classic_actes_path, classic_actes))
    if previous is None or previous.get('rows') != packet['rows'] or previous.get('agendaCount') != packet['agendaCount']:
        writes.append((root / 'zonaok-tots-actes.json', packet))
    # Validacio completa abans de crear cap fitxer, preservant la resta del JSON.
    encodings = [(p, json.dumps(obj, ensure_ascii=False, indent=2) + '\n') for p, obj in writes]
    for path, content in encodings:
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(content, encoding='utf-8')
        temp.replace(path)
    print('ACTES TOTAL:', len(overlay), 'fitxes | TOTAL', changed_total,
          '| Agenda', changed_legacy, '| Resultats', changed_recent,
          '| Actes clàssiques', int(changed_classic),
          '| fonts', len(sources), '| detall', packet['stats'])
    return packet


if __name__ == '__main__':
    try:
        generate()
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        sys.exit('ACTES TOTAL REBUTJAT: ' + str(exc))
