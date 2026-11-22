import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from scripts import zonaok_merge_actes_tots as m


def f(iso='2026-11-21', time='16:30', home='CP SANT CELONI B', away='MOLLET HC A', competition='INFANTIL OR 10', **other):
    return {'iso': iso, 'time': time, 'home': home, 'away': away, 'competition': competition,
            'homeScore': 12, 'awayScore': 0, 'venue': '', 'matchId': '', 'leagueId': '', 'actaUrl': '', **other}


def link(lid='4786', mid='152399', **other):
    return {'iso': '2026-11-21', 'time': '16:30', 'home': 'CP SANT CELONI B', 'away': 'MOLLET HC A',
            'competition': 'INFANTIL OR 10', 'leagueId': lid, 'matchId': mid,
            'actaUrl': m.canonical_url(lid, mid), **other}


class ActesTotsTests(unittest.TestCase):
    def test_verificacio_url(self):
        self.assertTrue(m.inspect_link(m.canonical_url('4786','152399'),'4786','152399'))
        self.assertFalse(m.inspect_link('https://evil.example/?liga=4786&partido=152399','4786','152399'))
        self.assertFalse(m.inspect_link(m.canonical_url('4786','152399'),'4789','152399'))

    def test_match_exact_els_dos_equips(self):
        out, reasons=m.build_overlay([f()], [link()])
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['leagueId'],'4786')
        self.assertEqual(reasons['strict'],1)

    def test_match_id_permet_canvi_de_nom_del_rival(self):
        r=f(matchId='152399', leagueId='4786', away='MOLLET CLUB HOQUEI A')
        out,reasons=m.build_overlay([r],[link()])
        self.assertEqual(len(out),1)
        self.assertEqual(reasons['id'],1)

    def test_same_competition_different_match_no_false_merge(self):
        r1=f();r2=f(competition='BENJAMÍ OR 5')
        out,reasons=m.build_overlay([r1,r2],[link()])
        self.assertEqual(len(out),0)
        self.assertGreater(reasons['ambiguous'],0)

    def test_duplicate_id_different_teams_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'imports/actes-tots').mkdir(parents=True)
            rows=[link(),link(home='HC CASTELLAR')]
            packet={'schema':'zonaok-actes-total-v1','kind':'actes-total-v1','source':'FECAPA-SAFARI',
                    'sourceUrl':'https://www.hoqueipatins.fecapa.cat/?liga=4786&vista=calendar',
                    'capturedAt':'2026-11-22T13:00:00Z','rows':rows}
            (root/'imports/actes-tots/one.json').write_text(json.dumps(packet))
            found, stats=m.collect_sources(root)
            self.assertEqual(found,[])
            self.assertEqual(stats['conflictingIds'],1)

    def test_preserve_old_acta_conflicting(self):
        old=f(actaUrl=m.canonical_url('4786','111111'))
        out,reasons=m.build_overlay([old],[link()])
        self.assertEqual(out,[])
        self.assertEqual(reasons['existingActaPreserved'],1)

    def test_unmatched_never_adds_fixture(self):
        out,reasons=m.build_overlay([f()],[link(iso='2026-11-22',time='17:00')])
        self.assertEqual(out,[])
        self.assertEqual(reasons['notFound'],1)

    def test_alias_ambiguous_rejected(self):
        a=f(home='CP SANT CELONI B',away='CLUB A')
        b=f(home='CP SANT CELONI B',away='CLUB B')
        r=link(away='MOLLET HC A')
        out,reasons=m.build_overlay([a,b],[r])
        self.assertEqual(out,[])
        self.assertEqual(reasons['notFound'],1)

    def test_existing_legacy_fixture_accepted(self):
        old={'league':'4786','id':'152399','iso':'2026-11-21','time':'16:30',
             'home':'CP SANT CELONI B','away':'MOLLET HC A','competition':'INFANTIL OR 10',
             'actaUrl':m.canonical_url('4786','152399')}
        self.assertIsNotNone(m.source_row(old))

    def test_persistent_overlay_not_erased(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            ag={'schema':'zonaok-all-v1','kind':'agenda','season':'2026/2027','rows':[f()]}
            (root/'zonaok-tots-agenda.json').write_text(json.dumps(ag))
            orig={'schema':'zonaok-actes-total-v1','kind':'actes-total','rows':[
                {'key':m.match_key(f()),'leagueId':'4786','matchId':'152399','actaUrl':m.canonical_url('4786','152399')} ]}
            (root/'zonaok-tots-actes.json').write_text(json.dumps(orig))
            (root/'zonaok-data.json').write_text(json.dumps({'version':3,'data':{'agenda':{'rows':[f()]}}}))
            data=m.generate(root,now=datetime(2026,11,22,tzinfo=timezone.utc))
            self.assertEqual(data['count'],1)
            self.assertEqual(data['rows'][0]['matchId'],'152399')
            self.assertEqual(data['agendaCount'],1)

    def test_actualitza_les_dues_agendes_sense_tocar_marcadors(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'imports/actes-tots').mkdir(parents=True)
            r=f()
            (root/'zonaok-tots-agenda.json').write_text(json.dumps({'schema':'zonaok-all-v1','kind':'agenda','season':'2026/2027','rows':[r]}))
            (root/'zonaok-data.json').write_text(json.dumps({'version':3,'data':{'agenda':{'rows':[r]},'other':{'unmodified':True}}}))
            (root/'zonaok-tots-resultats-7dies.json').write_text(json.dumps({'schema':'zonaok-all-v1','kind':'resultats-7dies','rows':[r]}))
            capture={'schema':'zonaok-actes-total-v1','kind':'actes-total-v1','source':'FECAPA-SAFARI',
                     'sourceUrl':'https://www.hoqueipatins.fecapa.cat/?liga=4786&vista=calendar',
                     'capturedAt':'2026-11-22T12:00:00Z','rows':[link()]}
            (root/'imports/actes-tots/actes-4786.json').write_text(json.dumps(capture))
            result=m.generate(root)
            self.assertEqual(result['count'],1)
            total=json.loads((root/'zonaok-tots-agenda.json').read_text())
            legacy=json.loads((root/'zonaok-data.json').read_text())
            recent=json.loads((root/'zonaok-tots-resultats-7dies.json').read_text())
            for row in (total['rows'][0],legacy['data']['agenda']['rows'][0],recent['rows'][0]):
                self.assertEqual(row['actaUrl'],m.canonical_url('4786','152399'))
                self.assertEqual(row['homeScore'],12)
                self.assertEqual(row['awayScore'],0)
            self.assertEqual(legacy['data']['other'],{'unmodified':True})
            orig=legacy['data']['agenda']['rows'][0]
            self.assertEqual(orig['id'],'152399')
            self.assertEqual(orig['league'],'4786')
            self.assertEqual(result['stats']['agendaUpdated'],1)

    def test_conflictes_no_sobreescriuen(self):
        agenda=[f(actaUrl=m.canonical_url('4786','123456'),matchId='123456',leagueId='4786')]
        ov=[{'key':m.match_key(agenda[0]),'actaUrl':m.canonical_url('4786','152399'),'matchId':'152399','leagueId':'4786'}]
        changed,_=m.apply_overlay_to_rows(agenda,ov)
        self.assertEqual(changed,0)
        self.assertEqual(agenda[0]['matchId'],'123456')

    def test_large_agenda_index(self):
        rows=[f(iso='2026-11-21',time=f'{i//60:02d}:{i%60:02d}',home=f'CLUB {i} A',away=f'CLUB {i} B')
              for i in range(900)]
        src=[link(home='CLUB 430 A',away='CLUB 430 B',time='07:10')]
        out,reasons=m.build_overlay(rows,src)
        self.assertEqual(len(out),1)
        self.assertEqual(reasons['strict'],1)

    def test_conflicting_agenda_id(self):
        r=f(matchId='888888')
        out,reasons=m.build_overlay([r],[link()])
        self.assertEqual(out,[])


if __name__ == '__main__':unittest.main()
