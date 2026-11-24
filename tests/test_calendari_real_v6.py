import importlib.util
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright, Error

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'zonaok_fecapa_unificat.py'
spec=importlib.util.spec_from_file_location('zonaok_v6',SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def fixture(lid='4789',mid='153067'):
    return f'''<tr class="sidgad-calendario-partido team-11329 team-11328">
      <td class="sidgad-col-dia">26/09/2026</td><td class="sidgad-col-hora">11:15</td>
      <td class="sidgad-col-equipo sidgad-col-equipo-home"><a href="/?liga={lid}&amp;vista=calendar&amp;equipo=11329">GENERALI HC PALAU B</a></td>
      <td class="sidgad-col-equipo sidgad-col-equipo-away"><a href="/?liga={lid}&amp;vista=calendar&amp;equipo=11328">GENERALI HC PALAU A</a></td>
      <td class="sidgad-col-resultado"><span class="sidgad-resultado-badge">4:9</span></td>
      <td class="sidgad-col-accion-details"><button data-calendar-action="details" data-match-id="{mid}">Detalls</button></td>
      </tr>'''

class TestRealCalendarV6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        try:cls.browser=cls.pw.chromium.launch(headless=True,args=['--no-sandbox'])
        except Error:cls.browser=cls.pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()
    def parse(self,body,lid='4789'):
        page=self.browser.new_page()
        page.set_content('<base href="https://www.hoqueipatins.fecapa.cat/">'+body,wait_until='domcontentloaded')
        out=page.evaluate(m.JS_CALENDAR,lid)
        page.close()
        return out
    def test_match_id_is_on_details_button_not_agenda(self):
        data=self.parse('<h2 class="sidgad-calendario-fase">ALEVÍ OR 3</h2><table>'+fixture()+'</table>')
        self.assertEqual(len(data['rows']),1)
        r=data['rows'][0]
        self.assertEqual((r['leagueId'],r['matchId']),('4789','153067'))
        self.assertEqual((r['homeScore'],r['awayScore']),(4,9))
        self.assertEqual(r['competition'],'ALEVÍ OR 3')
        accepted,status=m.verified_league_rows('4789',data['rows'],[])
        self.assertTrue(status['verified'])
        self.assertIn('partido=153067',accepted[0]['actaUrl'])
    def test_foreign_league_rejected(self):
        data=self.parse('<table>'+fixture('4774','146327')+'</table>')
        accepted,status=m.verified_league_rows('4789',data['rows'],[])
        self.assertFalse(accepted)
        self.assertEqual(status['foreignRows'],1)
    def test_no_ids_are_invented(self):
        data=self.parse('<table>'+fixture().replace('data-match-id="153067"','')+'</table>')
        self.assertEqual(data['rows'][0]['matchId'],'')
        accepted,status=m.verified_league_rows('4789',data['rows'],[])
        self.assertFalse(accepted)
        self.assertFalse(status['verified'])
    def test_hidden_live_module_ignored(self):
        html='<div style="display:none"><div class="sidgad-partido-fila">NOT THE CALENDAR</div></div>'
        data=self.parse(html+'<table>'+fixture()+'</table>')
        self.assertEqual(data['count'],1)
        self.assertEqual(data['rows'][0]['matchId'],'153067')
    def test_league_not_inferred_from_location(self):
        data=self.parse('<table>'+fixture().replace('liga=4789','lliga=4789')+'</table>')
        self.assertEqual(data['rows'][0]['leagueId'],'')
        accepted,status=m.verified_league_rows('4789',data['rows'],[])
        self.assertFalse(accepted)
        self.assertFalse(status['verified'])

if __name__=='__main__':unittest.main()
