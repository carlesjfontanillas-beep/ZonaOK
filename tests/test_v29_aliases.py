# -*- coding: utf-8 -*-
"""Proves amb el conciliador V29 real, disponible al repositori GitHub."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import zonaok_import_directe_v29 as v29
from zonaok_import_directe_v29_compat import alias_verificat, installa_equivalencies

installa_equivalencies(v29)


def agenda(iso, time, comp, home, away, hs=None, ass=None):
    return {
        'iso': iso, 'time': time, 'competition': comp,
        'home': home, 'away': away, 'homeScore': hs, 'awayScore': ass,
        'venue': 'PISTA', 'capturedAt': '2026-11-21T09:51:21.447Z'
    }


def directe(iso, time, comp, home, away, hs, ass):
    return {
        'iso': iso, 'time': time, 'competition': comp,
        'home': home, 'away': away, 'homeScore': hs, 'awayScore': ass, 'id': ''
    }


class ConciliacioV29(unittest.TestCase):
    def setUp(self):
        self.existing = [
            agenda('2026-11-21', '11:15', 'FEM 15 OR', 'INNOAESTHETICS HC SANT JUST', 'SANT CELONI'),
            agenda('2026-11-21', '16:30', 'INFANTIL OR 10', 'CP SANT CELONI B', 'MOLLET HC A'),
            agenda('2026-11-21', '16:30', 'BCN BENJAMÍ OR 5', 'CLUB PATÍ VOLTREGÀ B', 'SANT CELONI'),
            agenda('2026-11-21', '19:45', 'NACIONAL CATALANA MASCULINA', 'CLUB HOQUEI CADÍ', 'BARÇA'),
            agenda('2026-11-20', '19:00', 'ALEVÍ OR 3', 'BARÇA', 'VICIO PHC SANT CUGAT A', 2, 1),
            agenda('2026-11-20', '22:00', 'LCV GRUP C', 'GENERALI HC PALAU', 'CLUB PATI SANT CELONI', 4, 3),
            agenda('2026-11-21', '18:45', 'INFANTIL OR 5', 'FARNERS A', 'CP SANT CELONI A'),
        ]
        self.rows = [
            directe('2026-11-21', '11:15', 'FEM 15 OR', 'HCSJ', 'CPSC', 2, 1),
            directe('2026-11-21', '16:30', 'INFANTIL OR', 'CPSC', 'MHCA', 12, 0),
            directe('2026-11-21', '19:45', 'NACIONAL CATALANA MASCULINA', 'CADÍ', 'BAR', 5, 4),
        ]

    def test_aliases_exactes(self):
        self.assertTrue(alias_verificat('INNOAESTHETICS HC SANT JUST', 'HCSJ'))
        self.assertTrue(alias_verificat('MOLLET HC A', 'MHCA'))
        self.assertTrue(alias_verificat('CLUB HOQUEI CADÍ', 'CADÍ'))
        self.assertTrue(alias_verificat('VICIO PHC SANT CUGAT A', 'HSCA'))
        self.assertTrue(alias_verificat('GENERALI HC PALAU', 'PAL'))
        self.assertFalse(alias_verificat('MOLLET HC B', 'MHCA'))
        self.assertFalse(alias_verificat('FARNERS A', 'LUBA'))

    def test_tres_correspondencies_univoces(self):
        for expected, row in zip([0, 1, 3], self.rows):
            index, mode, n = v29.select_unique(self.existing, row)
            self.assertEqual(expected, index, (row, mode, n))
            self.assertEqual(1, n)

    def test_partit_ambigu_descartat(self):
        data = self.existing + [copy.deepcopy(self.existing[1])]
        index, mode, n = v29.select_unique(data, self.rows[1])
        self.assertIsNone(index)
        self.assertGreater(n, 1)

    def test_rival_desconegut_no_impedeix_equivalencia_unica(self):
        # Només club, data, hora i costat; el rival LUBA no és a l'Agenda.
        self.assertEqual(6, v29.select_unique(self.existing, directe(
            '2026-11-21', '18:45', 'INFANTIL OR', 'LUBA', 'CPSC', 3, 1))[0])

    def test_CPSC_CPSCA_CPSCB_tots_el_mateix_club(self):
        for abreviatura in ('CPSC', 'CPSCA', 'CPSCB'):
            self.assertEqual(1, v29.select_unique(self.existing, directe(
                '2026-11-21','16:30','INFANTIL OR',abreviatura,'RIVAL NO RECONEGUT',12,0))[0])

    def test_bar_data_hora_ignorant_rival(self):
        self.assertEqual(3, v29.select_unique(self.existing, directe(
            '2026-11-21','19:45','NACIONAL CATALANA MASCULINA', 'RIVAL DESCONEGUT','BAR',5,4))[0])

    def test_no_mou_marcador_al_costat_contrari(self):
        self.assertIsNone(v29.select_unique(self.existing, directe(
            '2026-11-21','19:45','NACIONAL CATALANA MASCULINA', 'BAR','RIVAL',5,4))[0])

    def test_ambigu_no_modifica_marcadors(self):
        altre = agenda('2026-11-21', '16:30', 'JUVENIL', 'CP SANT CELONI A','FC ALTRE')
        dades = self.existing + [altre]
        self.assertIsNone(v29.select_unique(dades, directe(
            '2026-11-21', '16:30', '', 'CPSC', 'EQUIP DESCONEGUT', 1, 1))[0])

    def test_workflow_executa_el_conciliador_amb_club_data_hora(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'zonaok-v29-directe-automatic.yml').read_text(encoding='utf-8')
        self.assertIn("python3 scripts/zonaok_import_directe_v29_compat.py", workflow)
        self.assertNotIn("\n            python3 scripts/zonaok_import_directe_v29.py\n", workflow)

    def test_mescla_només_marcadors(self):
        source = {
            'version': 3, 'publishedAt': '2026-11-21T20:06:05Z',
            'data': {
                'agenda': {'capturedAt': '2026-11-21T09:51:21.447Z', 'rows': self.existing},
                'classificacions': {'rows': [{'nom': 'PRESERVAR'}]},
                'actes': {'rows': [{'id': 123}]},
            }
        }
        capture = datetime.fromisoformat('2026-11-22T09:56:43+00:00')
        result, stats = v29.merge(source, capture, self.rows)
        self.assertEqual(3, stats['marcadors_canviats'])
        self.assertEqual((2, 1), (result['data']['agenda']['rows'][0]['homeScore'], result['data']['agenda']['rows'][0]['awayScore']))
        self.assertEqual((12, 0), (result['data']['agenda']['rows'][1]['homeScore'], result['data']['agenda']['rows'][1]['awayScore']))
        self.assertEqual((5, 4), (result['data']['agenda']['rows'][3]['homeScore'], result['data']['agenda']['rows'][3]['awayScore']))
        for section in ('classificacions', 'actes'):
            self.assertEqual(source['data'][section], result['data'][section])
        for old, new in zip(source['data']['agenda']['rows'], result['data']['agenda']['rows']):
            for key, value in old.items():
                if key not in ('homeScore', 'awayScore', 'scoreCapturedAt', 'scoreSource'):
                    self.assertEqual(value, new.get(key))
        self.assertEqual(len(source['data']['agenda']['rows']), len(result['data']['agenda']['rows']))


if __name__ == '__main__':
    unittest.main()
