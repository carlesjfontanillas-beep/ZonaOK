import sys,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_live_finals import targets
class LiveFinals(unittest.TestCase):
    def test_only_affected_group_and_retry(self):
        clock=datetime(2026,11,28,12,tzinfo=timezone.utc)
        r={'iso':'2026-11-28','time':'10:00','status':'FINAL','homeScore':2,'awayScore':1,'leagueId':'4784','competition':'JUVENIL OR 6','home':'A','away':'B','finalDetectedAt':'2026-11-28T11:00:00Z'}
        groups={'competitions':{'4784:a':{'leagueId':'4784','name':'JUVENIL OR 6','standingsAt':'2026-11-28T10:00:00Z','standings':[{'team':'A'},{'team':'B'}]},'4784:b':{'leagueId':'4784','name':'JUVENIL OR 8'},'4786:c':{'leagueId':'4786','name':'INFANTIL OR 10'}}}
        self.assertEqual(targets({'matches':[r]},groups,clock),{'4784':{'JUVENIL OR 6'}})
        self.assertEqual(targets({'matches':[dict(r,leagueId='')]},groups,clock),{'4784':{'JUVENIL OR 6'}})
        self.assertEqual(targets({'matches':[dict(r,status='EN JOC'),dict(r,iso='2026-11-26')]},groups,clock),{})
        groups['competitions']['4784:a']['standingsAt']='2026-11-28T11:10:00Z'
        self.assertEqual(targets({'matches':[r]},groups,clock),{})
if __name__=='__main__':unittest.main()
