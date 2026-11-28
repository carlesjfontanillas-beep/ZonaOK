import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import zonaok_fecapa_unificat as m
class StateAliases(unittest.TestCase):
    def test_screenshots_and_conflicts(self):
        rows=m.load_equivalence_catalog()['stateAliases']
        self.assertEqual(len([r for r in rows if r.get('source')=='RFEP-classificacions-captura-usuari-20261128']),96)
        self.assertEqual(m.state_team_names('BAR','OK LIGA MASCULINA'),{'BARCA'})
        self.assertEqual(m.state_team_names('BAR','OK LIGA PLATA NORTE'),{'BARCA ATLETIC'})
        self.assertEqual(len(m.state_team_names('CPV','OK LIGA MASCULINA')),2)
        self.assertEqual(len(m.state_team_names('CHM','OK LIGA PLATA SUR')),2)
        self.assertEqual(len(m.state_team_names('CPA','OK LIGA BRONCE SUR')),2)
        self.assertFalse(any(r['shortTeam']=='DES' for r in rows))
    def test_match_with_rival_and_ambiguity(self):
        a=dict(iso='2026-11-28',time='18:00',competition='OK LIGA MASCULINA',home='CP VOLTREGA MOVENTO STERN',away='BARÇA')
        b=dict(a,home='AMETLLER ORIGEN CP VILAFRANCA',away='PONS LLEIDA')
        incoming=dict(a,home='CPV',away='BAR')
        self.assertEqual(m.match_index([a,b],incoming,'directe'),0)
        self.assertIsNone(m.match_index([a,dict(b,away='BARÇA')],incoming,'directe'))
        self.assertIsNone(m.match_index([dict(a,competition='OK LIGA PLATA NORTE')],incoming,'directe'))
if __name__=='__main__':unittest.main()
