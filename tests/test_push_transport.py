import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from zonaok_push_transport import deliver,safe_summary
class TransportTest(unittest.TestCase):
    def test_isolate_invalid_event(self):
        batch={'events':[{'eventId':'a','event':'start'},{'eventId':'b','event':'finish'}]}
        def send(b,t):
            return (400,{'error':'invalid_event'}) if len(b['events'])>1 or b['events'][0]['eventId']=='a' else (200,{'ok':True,'accepted':1})
        r,ok=deliver(batch,'secret',send)
        self.assertFalse(ok);self.assertEqual(len(r['rejected']),1)
        self.assertEqual(r['rejected'][0]['eventId'],'a')
        self.assertEqual(r['individual'][1]['response']['accepted'],1)
    def test_no_sensitive_response(self):
        self.assertEqual(safe_summary('{"ok":true,"accepted":2,"token":"secret","endpoint":"https://private","error":"private data here"}'),{'ok':True,'accepted':2})
    def test_empty_batch_is_not_delivery(self):
        r,ok=deliver({'events':[]},'secret',lambda b,t:(200,{'ok':True,'accepted':0,'pending':0}))
        self.assertTrue(ok);self.assertEqual(r['batchSize'],0)
if __name__=='__main__':unittest.main()
