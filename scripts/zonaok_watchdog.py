#!/usr/bin/env python3
"""Watchdog for the current operational workflows, no cancellations or forced writes."""
import json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from zonaok_schedule_gate import directe_followup_count,MADRID

WORKFLOWS={
 'zonaok-auto-directe.yml':['scope=fast','publish=true'],
 'zonaok-auto-agenda.yml':['scope=daily','publish=true'],
 'zonaok-actes-live.yml':[],
 'zonaok-auto-actes.yml':['scope=full','publish=true'],
 'zonaok-classificacions-auto.yml':['scope=live','publish=true'],
 'jugadors-public.yml':['mode=retry'],
 'zonaok-equivalencies-fecapa.yml':[],
 'zonaok-recuperacio-temporada.yml':[],
 'zonaok-push-events.yml':['test_scenario=scheduled_now'],
 'zonaok-push-plan-inicial.yml':[],
}
FAIL={'failure','cancelled','timed_out','startup_failure','action_required','stale'}
PUSH='zonaok-push-events.yml'
def retry_args(workflow,run):
    if workflow!=PUSH:return WORKFLOWS[workflow]
    title=run.get('displayTitle','')
    # Only genuine events may be retried. Never replay fictitious notifications.
    if re.match(r'^ZonaOK Push (empty|barca_nc)( |$)',title):return None
    m=re.fullmatch(r'ZonaOK Push production (agenda|directe) ([0-9a-f]{40}) ([0-9a-f]{40})',title)
    if m:
        source,before,after=m.groups()
        return ['test_scenario=production','event_source='+source,'before_sha='+before,'after_sha='+after]
    # Legacy run names did not record their input; run the live schedule safely.
    return WORKFLOWS[PUSH]

def age_seconds(run,now):
    try:return (now-datetime.fromisoformat(run['updatedAt'].replace('Z','+00:00'))).total_seconds()
    except (ValueError,TypeError,KeyError):return 0

def decide(workflow,runs,now,due=False):
    if any(r.get('status')!='completed' for r in runs):return None,'actiu o en cua'
    if workflow==PUSH:
        runs=[r for r in runs if retry_args(workflow,r) is not None]
    latest=runs[0] if runs else None
    if latest and latest.get('conclusion') in FAIL:
        consecutive=0
        for r in runs:
            if r.get('conclusion') not in FAIL:break
            consecutive+=1
        # Unlimited cycles, but escalating delay prevents a tight error loop.
        delay=(120,300,600,900)[min(consecutive-1,3)]
        if age_seconds(latest,now)<delay:return None,f'pausa de reintent {delay}s'
        return retry_args(workflow,latest),f'error {latest["databaseId"]}, nou cicle després de {delay}s'
    if due and (not latest or age_seconds(latest,now)>=300):
        return WORKFLOWS[workflow],'cicle previst no activat'
    return None,'sense error pendent'

def gh(*args):
    return subprocess.check_output(['gh',*args],text=True).strip()

def main():
    now=datetime.now(timezone.utc)
    catalog=Path('zonaok-tots-partits.json')
    due_directe=bool(directe_followup_count(catalog,now))
    # Do not rely on an arbitrary scheduled success to prove the 10 h import ran.
    try:
        cap=json.loads(Path('imports/agenda-daily-report.json').read_text()).get('capturedAt')
        last=datetime.fromisoformat(cap.replace('Z','+00:00')).astimezone(MADRID)
        local=now.astimezone(MADRID)
        agenda_due=local.hour>=10 and (last.date()!=local.date() or last.hour<10)
    except (OSError,ValueError,TypeError,AttributeError):agenda_due=now.astimezone(MADRID).hour>=10
    errors=0
    for workflow in WORKFLOWS:
        try:
            runs=json.loads(gh('run','list','--workflow',workflow,'--branch','main','--limit','30','--json','databaseId,status,conclusion,updatedAt,displayTitle'))
            args,reason=decide(workflow,runs,now,due=(workflow=='zonaok-auto-directe.yml' and due_directe) or (workflow=='zonaok-auto-agenda.yml' and agenda_due))
            print(f'{workflow}: {reason}',flush=True)
            if args is None:continue
            # Recheck just before dispatch. Existing workflow concurrency groups
            # also serialize publications and never cancel existing jobs.
            current=json.loads(gh('run','list','--workflow',workflow,'--branch','main','--limit','30','--json','status'))
            if any(r.get('status')!='completed' for r in current):continue
            cmd=['workflow','run',workflow,'--ref','main']
            for a in args:cmd+=['-f',a]
            gh(*cmd)
            print(f'{workflow}: reactivació sol·licitada',flush=True)
        except (subprocess.CalledProcessError,ValueError,KeyError) as e:
            errors+=1
            print(f'::warning::No es pot supervisar {workflow}: {type(e).__name__}',flush=True)
    return 1 if errors else 0
if __name__=='__main__':sys.exit(main())
