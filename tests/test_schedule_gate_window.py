import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from zonaok_schedule_gate import should_run, LIVE_CRONS

class TestDirecteWindow(unittest.TestCase):
    def test_evening_window_and_delayed_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"matches.json"
            row={"iso":"2026-11-25","time":"21:00","competition":"NACIONAL CATALANA MASCULINA","status":"SENSE COMENÇAR","homeScore":0,"awayScore":0}
            def check(hour,minute,expected,day=25):
                path.write_text(json.dumps({"matches":[row]}))
                now=datetime(2026,11,day,hour,minute,tzinfo=ZoneInfo("Europe/Madrid"))
                self.assertEqual(should_run("directe",LIVE_CRONS["directe"],now,path)[0],expected)
            check(20,29,False)
            check(20,30,True)
            check(20,59,True)
            check(21,0,True)
            check(23,30,True)
            check(23,32,True)
            check(23,45,True)
            check(23,46,True)
            row["status"]="FINAL"
            check(22,0,False)
            row["homeScore"]=None
            check(22,0,True)
            row.update(time="22:15",status="EN JOC")
            check(0,45,True,26)
            check(1,1,True,26)
            check(4,0,False,26)
            row.update(iso='2026-11-25',time='21:00',competition='INFANTIL OR',status='SENSE COMENÇAR')
            check(21,39,False)
            check(21,40,True)

if __name__=="__main__":
    unittest.main()
