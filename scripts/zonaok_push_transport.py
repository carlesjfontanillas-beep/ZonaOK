#!/usr/bin/env python3
"""Authenticated push transport: diagnose rejected events without subscriber data."""
import json, os, re, sys, time, subprocess, tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

URL='https://zonaok-push.carles-j-fontanillas.workers.dev/sports-events'
def safe_summary(body):
    try:
        d=json.loads(body)
    except (ValueError,TypeError):
        return {'response':'non_json'}
    if not isinstance(d,dict):return {'response':'non_object'}
    out={k:d[k] for k in ('ok','accepted','duplicates','pending','sent','failed','matched','delivered') if type(d.get(k)) in (bool,int)}
    for k in ('error','code','reason'):
        if isinstance(d.get(k),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',d[k]):out[k]=d[k]
    return out

def send(payload,token):
    # Use the same curl HTTP client that previously reached the Worker.
    # Authorization is passed on stdin and never appears in logs or arguments.
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'batch.json'
        path.write_text(json.dumps(payload,ensure_ascii=False))
        for attempt in range(3):
            try:
                r=subprocess.run(['curl','--silent','--show-error','--max-time','30','--request','POST','--header','Content-Type: application/json','--header','@-','--data-binary','@'+str(path),'--write-out','\n%{http_code}',URL],input=('Authorization: Bearer '+token+'\n').encode(),capture_output=True,timeout=35)
                body,sep,code=r.stdout.rpartition(b'\n')
                status=int(code) if sep and code.isdigit() else 0
                summary=safe_summary(body) if status else {'error':'network_failure'}
                if status and status!=429 and status<500:return status,summary
            except (OSError,subprocess.TimeoutExpired):
                status=0;summary={'error':'network_failure'}
            if attempt<2:time.sleep(2**attempt)
        return status,summary

def deliver(batch,token,sender=send):
    events=batch['events'];status,result=sender(batch,token)
    report={'batchSize':len(events),'http':status,'response':result,'rejected':[],'individual':[]}
    if 200<=status<300 and result.get('ok') is True:return report,True
    if status==400 and len(events)>1:
        all_ok=True
        for e in events:
            st,summary=sender({**batch,'events':[e]},token)
            entry=event_summary(e,st,summary)
            report['individual'].append(entry)
            if not (200<=st<300 and summary.get('ok') is True):
                all_ok=False;report['rejected'].append(entry)
        return report,all_ok
    report['rejected']=[event_summary(e,status,result) for e in events]
    return report,False

def event_summary(e,status,result):
    f=e.get('fixture',{})
    return {'eventId':e.get('eventId'),'type':e.get('event'),'competition':f.get('competition'),'iso':f.get('iso'),'time':f.get('time'),'hasOfficialId':bool(f.get('leagueId') and f.get('matchId')),'http':status,'response':result}

if __name__=='__main__':
    batch=json.loads(Path(sys.argv[1]).read_text())
    report,ok=deliver(batch,os.environ['ZONAOK_PUSH_TOKEN'])
    Path('push-transport-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    sys.exit(0 if ok else 1)
