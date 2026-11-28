import sys,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_agenda_daily import merge,validate_publication
from zonaok_push_events import detect
from zonaok_schedule_gate import should_run
class DailyAgenda(unittest.TestCase):
    def row(self,iso='2026-11-27',home='A',away='B',**kw):
        return dict(iso=iso,time='17:00',competition='INFANTIL OR 10',home=home,away=away,homeScore=None,awayScore=None,status='',**kw)
    def run_merge(self,old,new):
        return merge({'schema':'zonaok-partits-total-v1','season':'2026/2027','matches':old},{'kind':'agenda-daily','season':'2026/2027','capturedAt':'2026-11-28T09:00:00Z','rows':new})
    def test_recover_yesterday_preserve_existing(self):
        a=self.row();b=self.row(home='C',away='D')
        b.update(homeScore=1,awayScore=2,lastDirecteAt='2026-11-27T18:00:00Z')
        out,report=self.run_merge([a,b],[dict(a,homeScore=4,awayScore=0),dict(b,homeScore=9,awayScore=9)])
        self.assertEqual(report['recoveredResultCount'],1)
        self.assertEqual(out['matches'][0]['status'],'FINAL')
        self.assertEqual(out['matches'][1]['homeScore'],1)
    def test_schedule_change_without_id_and_push(self):
        a=self.row(iso='2026-12-01')
        out,report=self.run_merge([a],[dict(a,time='19:00')])
        self.assertEqual(len(out['matches']),1)
        self.assertEqual(report['scheduleChangeCount'],1)
        before={'schema':'zonaok-partits-total-v1','season':'2026/2027','matches':[a]}
        events=detect(before,out,since=datetime(2026,11,27,9,tzinfo=timezone.utc),now=datetime(2026,11,28,9,1,tzinfo=timezone.utc),source='agenda')
        self.assertEqual([e['event'] for e in events],['scheduleChange'])
    def test_ambiguous_never_duplicate(self):
        a=self.row(iso='2026-12-01');b=dict(a,iso='2026-12-08')
        out,report=self.run_merge([a,b],[dict(a,time='19:00'),dict(b,time='20:00')])
        self.assertEqual(report['scheduleChangeCount'],0)
        self.assertEqual(len(out['matches']),2)
    def test_existing_official_slot_removes_stale_duplicate(self):
        a=dict(self.row(iso='2026-11-29',home='SHUM GRUES VIÑOLAS C',away='CH PALAFRUGELL A'),competition='PREBENJAMI PLATA GIRONA',time='09:15')
        b=dict(a,time='10:15')
        # Add an unrelated match so the existing source coverage guard remains active.
        others=[self.row(iso='2026-12-01',home='X'+str(i),away='Y'+str(i)) for i in range(5)]
        out,report=self.run_merge([a,b]+others,[b]+others)
        self.assertEqual(report['duplicatesRemoved'],1)
        self.assertEqual(report['unresolvedCount'],0)
        self.assertEqual([r['time'] for r in out['matches'] if r['home']==a['home']],['10:15'])
        self.assertEqual(report['catalogBefore']-report['catalogAfter'],1)
        out,report=self.run_merge([dict(a,matchId='12345',leagueId='4786'),dict(b,matchId='54321',leagueId='4786')]+others,[b]+others)
        self.assertEqual(report['duplicatesRemoved'],0)
        self.assertEqual(len(out['matches']),7)
        self.assertEqual(report['conflicts'][0]['possible'],[('2026-11-29','10:15')])
    def test_duplicate_pair_both_old_slots_changed(self):
        a=dict(self.row(iso='2027-01-09'),time='13:55')
        b=dict(a,iso='2027-01-10',time='10:15')
        c=dict(a,iso='2027-01-11',time='19:30')
        others=[self.row(iso='2026-12-01',home='X'+str(i),away='Y'+str(i)) for i in range(5)]
        out,report=self.run_merge([a,b]+others,[c]+others)
        self.assertEqual(report['duplicatesRemoved'],1)
        self.assertEqual(report['scheduleChangeCount'],1)
        self.assertEqual(report['unresolvedCount'],0)
        fixed=[r for r in out['matches'] if r['home']==a['home']][0]
        self.assertEqual((fixed['iso'],fixed['time']),(c['iso'],c['time']))
        self.assertEqual(fixed['agendaScheduleChange']['previousIso'],b['iso'])
        before={'schema':'zonaok-partits-total-v1','season':'2026/2027','matches':[a,b]+others}
        self.assertEqual([e['event'] for e in detect(before,out,since=datetime(2026,11,27,9,tzinfo=timezone.utc),now=datetime(2026,11,28,9,1,tzinfo=timezone.utc),source='agenda')],['scheduleChange'])
    def test_provisional_time_kept_until_official_change(self):
        a=dict(self.row(iso='2027-01-09'),time='13:55')
        out,report=self.run_merge([a],[a])
        self.assertEqual(report['scheduleChangeCount'],0)
        self.assertEqual(out['matches'][0]['time'],'13:55')
    def test_publication_allows_only_audited_removal(self):
        a=dict(self.row(iso='2026-12-01'),time='13:55')
        b=dict(a,time='17:00')
        others=[self.row(iso='2026-12-01',home='X'+str(i),away='Y'+str(i)) for i in range(5)]
        before={'schema':'zonaok-partits-total-v1','season':'2026/2027','matches':[a,b]+others}
        packet={'kind':'agenda-daily','season':'2026/2027','capturedAt':'2026-11-28T09:00:00Z','rows':[b]+others}
        out,report=merge(before,packet)
        self.assertEqual(validate_publication(before,out,packet,report),1)
        with self.assertRaises(ValueError):
            validate_publication(before,dict(out,matches=out['matches'][1:]),packet,report)
        with self.assertRaises(ValueError):
            validate_publication(before,out,packet,dict(report,duplicateRepairs=[]))
    def test_state_leagues_not_required_in_catalan_agenda(self):
        a=dict(self.row(),competition='OK LIGA MASCULINA',home='BARÇA',away='PONS LLEIDA',homeScore=4,awayScore=2)
        b=dict(a,iso='2026-12-01',homeScore=None,awayScore=None)
        c=dict(a,home='CPV',away='PONS LLEIDA')
        d=dict(a,home='SHUM FRIT RAVICH',homeScore=None,awayScore=None)
        e=dict(d,home='CH LLORET VILA ESPORTIVA',status='AJORNAT')
        others=[self.row(iso='2026-12-01',home='X'+str(i),away='Y'+str(i)) for i in range(25)]
        out,report=self.run_merge([a,b,c,d,e]+others,others)
        self.assertEqual(len(out['matches']),30)
        self.assertEqual(report['stateAcceptedCount'],3)
        self.assertEqual(sorted(r['reason'] for r in report['conflicts']),['state_ambiguous_team_code','state_missing_result'])
        self.assertFalse(any(r['reason']=='not_uniquely_found_in_agenda' for r in report['conflicts']))
    def test_official_calendar_overrides_previous_manual_choice(self):
        a=dict(self.row(iso='2026-11-29',home='CH LES FRANQUESES',away="UNIO ESPORTIVA D HORTA B"),competition='BCN BENJAMI PLATA 3',time='10:45')
        b=dict(a,iso='2026-11-28',time='17:00')
        out,report=self.run_merge([a],[b])
        self.assertEqual(report['scheduleChangeCount'],1)
        self.assertEqual(report['unresolvedCount'],0)
        self.assertEqual((out['matches'][0]['iso'],out['matches'][0]['time']),('2026-11-28','17:00'))
    def test_daily_madrid_dst(self):
        for month,utc_hour in [(1,9),(7,8)]:
            now=datetime(2026,month,10,utc_hour,12,tzinfo=timezone.utc)
            self.assertTrue(should_run('agenda',f'0 {utc_hour} * * *',now,Path('unused'))[0])
            self.assertFalse(should_run('agenda',f'0 {17-utc_hour} * * *',now,Path('unused'))[0])
if __name__=='__main__':unittest.main()
