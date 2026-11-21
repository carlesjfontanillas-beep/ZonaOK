"""Proves del consolidador. Executar: python -m unittest discover -s tests -v"""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'zonaok_merge_tots.py'
spec = importlib.util.spec_from_file_location('zonaok_merge', SCRIPT)
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)


class MergeTotsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'imports').mkdir()
        patcher = patch.object(merge, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.now = datetime.now(ZoneInfo('Europe/Madrid'))
        self.past = self.now - timedelta(days=1)
        self.date = self.past.strftime('%Y-%m-%d')
        self.hour = self.past.strftime('%H:%M')
        self.ts = self.now.isoformat()

    def match(self, **kw):
        data = dict(iso=self.date, time=self.hour, competition='ALEVÍ OR 3',
                    home='FC Barcelona', away='CP Sant Celoni', matchId='123456',
                    homeScore=None, awayScore=None, status='', venue='Pavelló')
        data.update(kw)
        return data

    def capture(self, kind, rows, at=None, season=None):
        data = dict(schema=merge.SCHEMA, kind=kind, season=season or merge.season_for(self.now),
                    source='FECAPA-SAFARI', capturedAt=at or self.ts, rows=rows)
        (self.root / 'imports' / f'tots-{kind}-import.json').write_text(json.dumps(data), encoding='utf8')

    def rows(self, name='zonaok-tots-agenda.json'):
        return json.loads((self.root / name).read_text(encoding='utf8'))['rows']

    def test_only_agenda_creates_matches(self):
        self.capture('agenda', [self.match()])
        self.capture('directe', [self.match(homeScore=3, awayScore=2, status='ACABAT'),
                                 self.match(home='Club A', away='Club B', matchId='999999', homeScore=1, awayScore=1)])
        _, live = merge.main()
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual((self.rows()[0]['homeScore'], self.rows()[0]['awayScore']), (3, 2))
        self.assertEqual(live['matched'], 1)
        self.assertEqual(live['unmatchedOrAmbiguous'], 1)
        self.assertFalse((self.root / 'zonaok-tots-directe.json').exists())

    def test_agenda_covers_any_club(self):
        self.capture('agenda', [self.match(), self.match(home='Club Diferent A', away='Club Diferent B', matchId='987654')])
        merge.main()
        self.assertEqual(len(self.rows()), 2)

    def test_recent_results_only(self):
        self.capture('agenda', [self.match(homeScore=1, awayScore=0),
                                self.match(home='Club X',away='Club Y',matchId='111111',
                                           iso=(self.now-timedelta(days=9)).strftime('%Y-%m-%d'),
                                           homeScore=2,awayScore=0)])
        merge.main()
        self.assertEqual(len(self.rows('zonaok-tots-resultats-7dies.json')), 1)

    def test_live_match_does_not_enter_results(self):
        self.capture('agenda', [self.match()])
        self.capture('directe', [self.match(homeScore=2,awayScore=3,status='EN JOC')])
        merge.main()
        self.assertEqual(self.rows()[0]['homeScore'], 2)  # Agenda s'actualitza
        self.assertEqual(len(self.rows('zonaok-tots-resultats-7dies.json')), 0)

    def test_prior_agenda_not_deleted_on_partial_import(self):
        self.capture('agenda', [self.match(homeScore=1, awayScore=1)])
        merge.main()
        later = (self.now + timedelta(minutes=1)).isoformat()
        self.capture('agenda', [self.match(matchId='234567', home='Club X', away='Club Y')], at=later)
        merge.main()
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(next(r for r in self.rows() if r['matchId']=='123456')['homeScore'], 1)

    def test_conflicting_ids_never_match(self):
        self.capture('agenda', [self.match()])
        self.capture('directe', [self.match(matchId='654321', homeScore=4, awayScore=4)])
        merge.main()
        self.assertIsNone(self.rows()[0]['homeScore'])

    def test_abbreviation_aliases_match_with_unique_category(self):
        self.capture('agenda', [self.match()])
        self.capture('directe', [self.match(home='BAR',away='CPSC',matchId='',homeScore=5,awayScore=1,status='ACABAT')])
        merge.main()
        self.assertEqual(self.rows()[0]['homeScore'], 5)

    def test_ambiguous_teams_without_category_never_match(self):
        self.capture('agenda', [self.match(matchId='',competition='ALEVI A'),
                                self.match(matchId='',competition='JUVENIL')])
        self.capture('directe', [self.match(matchId='',competition='',home='BAR',away='CPSC',homeScore=5,awayScore=1)])
        merge.main()
        self.assertTrue(all(r['homeScore'] is None for r in self.rows()))

    def test_id_wins_when_same_teams_time_other_category(self):
        self.capture('agenda', [self.match(competition='ALEVI A'),self.match(matchId='123457',competition='JUVENIL')])
        self.capture('directe', [self.match(matchId='123457',homeScore=6,awayScore=4,competition='')])
        merge.main()
        rows=self.rows()
        self.assertIsNone(next(r for r in rows if r['matchId']=='123456')['homeScore'])
        self.assertEqual(next(r for r in rows if r['matchId']=='123457')['homeScore'], 6)

    def test_stale_live_does_not_overwrite_fresh_agenda_score(self):
        future = (self.now + timedelta(minutes=2)).isoformat()
        self.capture('agenda', [self.match(homeScore=7,awayScore=1)], at=future)
        self.capture('directe', [self.match(homeScore=1,awayScore=0)], at=self.ts)
        merge.main()
        self.assertEqual(self.rows()[0]['homeScore'],7)

    def test_stale_agenda_does_not_overwrite_newer_live_score(self):
        self.capture('agenda', [self.match(homeScore=1,awayScore=1)],at=self.ts)
        self.capture('directe',[self.match(homeScore=4,awayScore=0,status='ACABAT')],
                     at=(self.now+timedelta(minutes=2)).isoformat())
        merge.main()
        self.capture('agenda',[self.match(homeScore=0,awayScore=0)],at=self.ts)
        merge.main()
        self.assertEqual(self.rows()[0]['homeScore'],4)

    def test_invalid_capture_does_not_write_public_files(self):
        self.capture('agenda', [self.match()])
        merge.main()
        previous = (self.root/'zonaok-tots-agenda.json').read_bytes()
        self.capture('agenda', [self.match(iso='2026-02-30')])
        with self.assertRaises(ValueError): merge.main()
        self.assertEqual((self.root/'zonaok-tots-agenda.json').read_bytes(), previous)

    def test_wrong_season_rejected(self):
        self.capture('agenda', [self.match()],season='2024/2025')
        with self.assertRaises(ValueError): merge.main()

    def test_empty_import_placeholder_is_safe(self):
        self.capture('agenda', [self.match()])
        merge.main()
        self.capture('agenda', [], at='')
        merge.main()
        self.assertEqual(len(self.rows()), 1)


if __name__ == '__main__':
    unittest.main()
