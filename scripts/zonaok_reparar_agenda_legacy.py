"""Reparació acotada de la captura antiga del calendari global (novembre 2026).

No inventa correspondències ni altera cap partit sa. Els registres amb lliga
4775 atribuïda per la URL, sense IDP ni pista, de la versió antiga, es desen
en quarantena. No es traslladen marcadors sobre un altre partit per inferència.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from zonaok_fecapa_unificat import (
    canonicalize, check_when, clean, load_unified, norm, score_tuple,
    utc_now, write_compatibility,
)

CUTOFF = '2026-11-24T10:13:20Z'


def invalid_legacy(row):
    # El capturador anterior llegia .sidgad-partido-fila globals i posava
    # leagueId=league (paràmetre de la pàgina), sense verificar-lo.
    if (clean(row.get('leagueId')) != '4775' or clean(row.get('matchId'))
        or clean(row.get('venue')) or clean(row.get('agendaUpdatedAt'))
        or clean(row.get('actaUrl')) or row.get('actaState') == 'available'
        or clean(row.get('actaCheckedAt')) or clean(row.get('directeUpdatedAt'))
        or clean(row.get('lastDirecteAt'))):
        return False
    try:
        return check_when(row.get('lastAgendaAt')) < check_when(CUTOFF)
    except (ValueError, TypeError, AttributeError):
        return False


def candidate_key(row):
    if not score_tuple(row):
        return None
    return (row.get('iso'), row.get('time'), row['homeScore'], row['awayScore'])


def repair(doc):
    rows = doc['matches']
    retained, quarantined = [], []
    for row in rows:
        (quarantined if invalid_legacy(row) else retained).append(row)
    if not retained:
        raise ValueError('Reparació bloquejada: cap partit sa')
    # Tots els partits amb identificador i la resta de files originals
    # es conserven íntegrament, en el mateix ordre.
    assert len(retained) + len(quarantined) == len(rows)
    assert all(not clean(x.get('matchId')) for x in quarantined)
    by_score = defaultdict(list)
    for row in retained:
        key = candidate_key(row)
        if key is not None:
            by_score[key].append(row)
    possible = sum(bool(by_score.get(candidate_key(x))) for x in quarantined)
    report = {
        'before': len(rows), 'after': len(retained),
        'quarantined': len(quarantined),
        'sameDateTimeScoreCandidate': possible,
        'withoutSameDateTimeScoreCandidate': len(quarantined) - possible,
        'byCapture': dict(Counter(x.get('lastAgendaAt') for x in quarantined)),
        'note': 'Les coincidències de data, hora i marcador són indicis, no equivalències verificades. No es modifica cap marcador o acta dels partits conservats.',
    }
    if not quarantined:
        return doc, [], report
    out = {**doc, 'matches': retained, 'updatedAt': utc_now(),
           'stats': {**doc.get('stats', {}), 'total': len(retained),
                     'withScores': sum(score_tuple(x) for x in retained),
                     'withActaLinks': sum(bool(x.get('actaUrl')) for x in retained),
                     'verifiedActes': sum(x.get('actaState') == 'available' for x in retained)}}
    return out, quarantined, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='zonaok-tots-partits.json')
    p.add_argument('--report', default='reparacio-agenda-report.json')
    p.add_argument('--quarantine', default='reparacio-agenda-quarantena.json')
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    path = Path(args.output)
    old = load_unified(path)
    new, quarantined, report = repair(old)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    Path(args.quarantine).write_text(json.dumps({'season': old['season'], 'report': report, 'rows': quarantined}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.apply and quarantined:
        # Verificació de partició independent abans d'escriure.
        assert new['matches'] == [x for x in old['matches'] if not invalid_legacy(x)]
        assert repair(new)[2]['quarantined'] == 0
        path.write_text(json.dumps(new, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        write_compatibility(new)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
