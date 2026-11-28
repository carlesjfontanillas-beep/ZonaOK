"""Regressions del DOM real /ag/: <th colspan=2> Local/Visitant.
Proves headless amb Chromium, sense connexió externa.
"""
import importlib.util
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright, Error

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'zonaok_fecapa_unificat.py'
spec=importlib.util.spec_from_file_location('zok_v5',SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PAGE='''<html><body><table>
<tr><th>Competició</th><th>Data</th><th>Hora</th>
<th colspan="2">Local</th><th colspan="2">Visitant</th><th>Result.</th><th>Pista</th></tr>
<tr class="fila_agenda" fecha="1795535100" param_game="1_-1_328_323_5043">
<td>ALEVÍ OR 3</td><td>24/11/2026</td><td>16:45</td>
<td width="20"></td><td>BARÇA</td><td width="20"></td><td>CP SANT CELONI</td>
<td>3 - 2</td><td>PALAU BLAUGRANA</td></tr>
<tr class="fila_agenda" fecha="-1" param_game="1_-1_328_323_5043">
<td>TARRAGONA BENJAMÍ</td><td>00/00/0000</td><td>00:00</td>
<td></td><td>REUS DEPORTIU</td><td></td><td>CAMBRILS CH</td><td></td><td>REUS</td></tr>
<tr class="fila_agenda" fecha="1795535100">
<td>ALEVÍ OR 3</td><td>24/11/2026</td><td>18:00</td>
<td></td><td>CH MATARÓ</td><td></td><td>CE NOIA</td><td></td><td>MATARÓ
<a href="https://www.hoqueipatins.fecapa.cat/?liga=4789&amp;vista=calendar&amp;partido=151001"></a></td></tr>
</table></body></html>'''

class TestAgendaV5DOM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        try:
            cls.browser=cls.pw.chromium.launch(headless=True,args=['--no-sandbox'])
        except Error:
            cls.browser=cls.pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()
    def test_colspan_respects_two_team_name_columns(self):
        page=self.browser.new_page()
        page.set_content(PAGE)
        result=page.evaluate(m.JS_AGENDA)
        page.close()
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(result['counts']['recognizedTables'],1)
        self.assertEqual(result['counts']['examined'],3)
        self.assertEqual(result['counts']['invalidDate'],1)
        a=result['rows'][0]
        self.assertEqual((a['home'],a['away']),('BARÇA','CP SANT CELONI'))
        self.assertEqual(a['venue'],'PALAU BLAUGRANA')
        self.assertEqual((a['homeScore'],a['awayScore']),(3,2))
        self.assertEqual(a['iso'],'2026-11-24')
        self.assertEqual(a['matchId'],'')
        self.assertEqual(a['leagueId'],'')
        self.assertEqual(result['counts']['sampleValidAttributes'][0]['param_game'],'1_-1_328_323_5043')
    def test_withdrawn_team_is_never_replaced_by_venue(self):
        page=self.browser.new_page()
        page.set_content("""<table><tr><th>Competició</th><th>Data</th><th>Hora</th><th colspan="2">Local</th><th colspan="2">Visitant</th><th>Result.</th><th>Pista</th></tr>
        <tr><td>PREBENJAMI PLATA GIRONA</td><td>29/11/2026</td><td>10:00</td><td></td><td>CP CALDES C</td><td></td><td></td><td></td><td>PAVELLÓ MUNICIPAL CALDES DE MALAVELLA</td></tr>
        <tr><td>PREBENJAMI PLATA GIRONA</td><td>29/11/2026</td><td>10:00</td><td></td><td>CP CALDES C</td><td></td><td>PAVELLÓ MUNICIPAL CALDES DE MALAVELLA</td><td></td><td></td></tr>
        <tr><td>PREBENJAMI PLATA GIRONA</td><td>29/11/2026</td><td>10:00</td><td></td><td>CP CALDES C</td><td></td><td>CH FIGUERES</td><td></td><td>PAVELLÓ MUNICIPAL CALDES DE MALAVELLA</td></tr></table>""")
        result=page.evaluate(m.JS_AGENDA);page.close()
        self.assertEqual(len(result['rows']),1)
        self.assertEqual(result['rows'][0]['away'],'CH FIGUERES')
        self.assertEqual(result['counts']['invalidTeams'],2)
    def test_agenda_ignores_even_official_match_links(self):
        page=self.browser.new_page()
        page.set_content(PAGE)
        result=page.evaluate(m.JS_AGENDA)
        page.close()
        self.assertEqual(result['counts']['withReliableIDs'],0)
        b=result['rows'][1]
        self.assertEqual(b['leagueId'],'')
        self.assertEqual(b['matchId'],'')
        self.assertEqual(b['actaUrl'],'')
    def test_official_competition_calendar_can_supply_match_id(self):
        page=self.browser.new_page()
        page.set_content('''<html><body><h2>ALEVÍ OR 3</h2>
          <div class="sidgad-partido-fila">
            <div class="sidgad-local"><span class="sidgad-equipo-nombre">BARÇA</span>
              <span class="sidgad-equipo-sub">24/11 16:45</span></div>
            <div class="sidgad-visitante"><span class="sidgad-equipo-nombre">CP SANT CELONI</span></div>
            <a href="https://www.hoqueipatins.fecapa.cat/?liga=4789&amp;vista=calendar&amp;partido=151001">Fitxa</a>
          </div></body></html>''')
        data=page.evaluate(m.JS_CALENDAR,'4789');page.close()
        self.assertEqual(len(data['rows']),1)
        extracted=data['rows'][0]
        self.assertEqual((extracted['leagueId'],extracted['matchId']),('4789','151001'))
        accepted,status=m.verified_league_rows('4789',data['rows'],[])
        self.assertTrue(status['verified'])
        self.assertEqual(len(accepted),1)
        self.assertIn('partido=151001',accepted[0]['actaUrl'])

    def test_unverified_league_is_never_certified_by_general_table(self):
        page=self.browser.new_page();page.set_content(PAGE)
        result=page.evaluate(m.JS_AGENDA);page.close()
        accepted,status=m.verified_league_rows('4789',[],result['rows'])
        self.assertEqual(len(accepted),0)
        self.assertFalse(status['verified'])
        self.assertEqual(status['withoutIDs'],2)

if __name__=='__main__':unittest.main()
