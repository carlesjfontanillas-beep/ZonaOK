#!/usr/bin/env python3
"""Catàleg acumulatiu de sigles FECAPA. No modifica partits ni resultats."""
import argparse
import json
import re
import unicodedata
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / 'zonaok-equivalencies-equips.json'
SCHEMA = 'zonaok-equivalencies-equips-v1'
SOURCE = 'FECAPA-classificacions-vertical'

def norm(s):
    return re.sub(r'[^A-Z0-9]+',' ',''.join(c for c in unicodedata.normalize('NFD',str(s or '')) if unicodedata.category(c)!='Mn').upper()).strip()

def load_catalog(path=CATALOG):
    doc=json.loads(Path(path).read_text(encoding='utf-8'))
    if doc.get('schema')!=SCHEMA or doc.get('season')!='2026/2027':
        raise ValueError('Catàleg d’equivalències incompatible')
    return doc

def valid_pair(r):
    a,b=norm(r.get('team')),norm(r.get('shortTeam'))
    return (r.get('source')==SOURCE and bool(a and b and a!=b)
            and bool(re.fullmatch(r'\d{4,6}',str(r.get('leagueId',''))))
            and bool(norm(r.get('group'))))

def collect_pairs(doc):
    for g in doc.get('competitions',{}).values():
        if not isinstance(g,dict):continue
        for r in g.get('standings',[]):
            if not isinstance(r,dict):continue
            item={'leagueId':str(g.get('leagueId','')),'group':g.get('name',''),
                  'category':g.get('category',''),'team':r.get('team',''),
                  'shortTeam':r.get('shortTeam',''),'source':r.get('shortTeamSource','')}
            if valid_pair(item):yield item

def merge_catalog(catalog,standings):
    # Conservem també conflictes, perquè mai es resolguin per ordre d'arribada.
    entries={}
    for r in list(catalog.get('teamAliases',[]))+list(collect_pairs(standings)):
        if not isinstance(r,dict) or not valid_pair(r):continue
        key=(str(r['leagueId']),norm(r['group']),norm(r['team']),norm(r['shortTeam']))
        entries[key]=r
    return {**catalog,'teamAliases':[entries[k] for k in sorted(entries)]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--standings',default='zonaok-classificacions.json')
    p.add_argument('--catalog',default=str(CATALOG))
    args=p.parse_args()
    path=Path(args.catalog)
    catalog=load_catalog(path)
    merged=merge_catalog(catalog,json.loads(Path(args.standings).read_text(encoding='utf-8')))
    data=json.dumps(merged,ensure_ascii=False,indent=2)+'\n'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(data,encoding='utf-8')
    tmp.replace(path)
    print('Equivalències FECAPA diferenciades i contextualitzades:',len(merged['teamAliases']))
if __name__=='__main__':main()
