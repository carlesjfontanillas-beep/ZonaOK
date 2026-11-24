import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_reparar_agenda_legacy import repair, invalid_legacy
from zonaok_fecapa_unificat import merge_unified


def suspect(**kw):
    return dict(iso='2026-11-20',time='19:00',home='BAR',away='HSCA',
        competition='ALEVÍ ORFEDERACIÓN CATALANA DE PATINAJE',
        leagueId='4775',matchId='',actaUrl='',venue='',homeScore=2,awayScore=1,
        status='FINAL',lastAgendaAt='2026-11-23T23:33:03Z',**kw)


def doc(rows):
    return {'schema':'zonaok-partits-total-v1','season':'2026/2027','sources':{},'matches':rows}


class TestRepair(unittest.TestCase):
    def test_real_example_and_protection(self):
        bad=suspect()
        good={**bad,'home':'BARÇA','away':'VICIO PHC SANT CUGAT A',
              'competition':'ALEVÍ OR 3','leagueId':'4789','matchId':'152563',
              'venue':'CAMPUS DE MUNDET UB'}
        generic={**bad,'leagueId':'','home':'ALTRE EQUIP'}
        checked={**bad,'actaState':'available'}
        fresh={**bad,'lastAgendaAt':'2026-11-24T16:20:26Z'}
        legacy={**bad,'agendaUpdatedAt':'2026-11-23T16:33:40.914Z'}
        before=doc([bad,good,generic,checked,fresh,legacy])
        after,quarantine,report=repair(before)
        self.assertEqual(quarantine,[bad])
        self.assertEqual(after['matches'],[good,generic,checked,fresh,legacy])
        self.assertEqual(report['sameDateTimeScoreCandidate'],1)
        self.assertEqual(repair(after)[2]['quarantined'],0)

    def test_reject_incomplete_league_in_new_agenda(self):
        good={**suspect(),'leagueId':'','home':'BARÇA','away':'VICIO PHC SANT CUGAT A'}
        capture={'schema':'zonaok-captura-v1','kind':'agenda','season':'2026/2027',
                 'capturedAt':'2026-11-24T18:00:00Z','rows':[suspect()]}
        after,report=merge_unified(capture,doc([good]),'agenda')
        self.assertEqual(report['new'],0)
        self.assertEqual(report['ambiguousOrInvalid'],1)
        self.assertEqual(len(after['matches']),1)

    def test_unverified_not_conflated_with_legitimate_no_id(self):
        self.assertFalse(invalid_legacy({**suspect(),'leagueId':''}))
        self.assertFalse(invalid_legacy({**suspect(),'venue':'PISTA'}))
        self.assertFalse(invalid_legacy({**suspect(),'matchId':'152563'}))
        self.assertFalse(invalid_legacy({**suspect(),'lastAgendaAt':''}))
