#!/usr/bin/env python3
"""Public fixture-only plan, local Madrid 10:00 to next 10:00. No delivery."""
import argparse,json
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zonaok_push_events import MADRID,scheduled_candidates

def build_plan(catalog, now):
    local=now.astimezone(MADRID)
    start=local.replace(hour=10,minute=0,second=0,microsecond=0)
    if local<start:start-=timedelta(days=1)
    end=start+timedelta(days=1)
    events=[]
    for kickoff,eid,fixture,nc in scheduled_candidates(catalog):
        if not start<=kickoff<end:continue
        events.append({'eventId':eid,'event':'start','mode':'live_confirmation' if nc else 'scheduled','scheduledAt':kickoff.isoformat(),'fixture':fixture})
    events.sort(key=lambda e:(e['scheduledAt'],e['eventId']))
    return {'schema':'zonaok-push-plan-v1','season':catalog['season'],'from':start.isoformat(),'until':end.isoformat(),'agendaCapturedAt':catalog.get('sources',{}).get('agenda',{}).get('capturedAt'),'eventCount':len(events),'scheduledCount':sum(e['mode']=='scheduled' for e in events),'liveConfirmationCount':sum(e['mode']=='live_confirmation' for e in events),'events':events}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--catalog',default='zonaok-tots-partits.json',type=Path)
    p.add_argument('--output',default='imports/push-plan.json',type=Path)
    p.add_argument('--at')
    a=p.parse_args()
    now=datetime.fromisoformat(a.at.replace('Z','+00:00')) if a.at else datetime.now(timezone.utc)
    result=build_plan(json.loads(a.catalog.read_text()),now)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='events'},ensure_ascii=False))
if __name__=='__main__':main()
