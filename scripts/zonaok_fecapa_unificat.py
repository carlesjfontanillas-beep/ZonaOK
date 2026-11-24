#!/usr/bin/env python3
"""ZonaOK: capturadors independents FECAPA via Chromium/Playwright.

  collect --mode {agenda,directe,actes} --capture ... --report ...
  merge   --mode {agenda,directe,actes} --capture ... --output ...

No depèn de Safari ni API privada. Genera enllaços oficials com a candidats,
mai afirma que una acta estigui publicada sense verificar-la.
Publicació explícita i separada per GitHub Actions, amb diagnòstics.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import subprocess
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlparse

ROOT = 'https://www.hoqueipatins.fecapa.cat/'
CANONICAL = Path('zonaok-tots-partits.json')
AGENDA_URL = ROOT+'ag/'
SEASON = '2026/2027'
SEASON_FROM, SEASON_TO = '2026-07-01', '2027-06-30'
VALID_HOSTS = {'www.hoqueipatins.fecapa.cat', 'hoqueipatins.fecapa.cat'}
LOOKBACK_DAYS = 7
DIRECTE_LOOKAHEAD_DAYS = 2
FAVOURITE_LEAGUES = ('4789','4786','4784')
# Mateix màxim que admet el lector d'index.html. Permet tota la temporada.
MAX_LEGACY_ACTA_FIXTURES = 20000


def local_today():
    return datetime.now(ZoneInfo('Europe/Madrid')).date()


def recent_start():
    return (local_today()-timedelta(days=LOOKBACK_DAYS)).isoformat()


def in_recent_window(row):
    return recent_start() <= clean(row.get('iso')) <= (local_today()+timedelta(days=DIRECTE_LOOKAHEAD_DAYS)).isoformat()


def archived_complete(row):
    # Només es congela un partit quan el marcador és numèric i l'acta
    # ha estat verificada realment. Un simple enllaç NO és una acta.
    return (clean(row.get('iso')) < recent_start() and score_tuple(row)
            and row.get('actaState')=='available')


def parse_integer(text, name):
    try:
        n=int(str(text))
    except ValueError as exc:
        raise ValueError(f'{name} ha de ser un enter') from exc
    if n < 0:raise ValueError(f'{name} no pot ser negatiu')
    return n


def select_league_batch(ids, args, previous, diagnostic):
    ids=sorted(set(ids),key=int)
    if args.scope=='full':
        old_state=previous.get('sources',{}).get('agenda',{})
        # The V2 cursor was advanced even for generic, unverified 532-row
        # pages. Do not trust that historical cursor without V3 verification.
        trustworthy='pendingLeagueIds' in old_state or 'verifiedLeagues' in old_state
        offset=(int(old_state.get('nextFullOffset') or 0) if trustworthy else 0) if args.offset=='auto' else parse_integer(args.offset,'offset')
        if offset>=len(ids) and args.offset=='auto':
            pending=[x for x in old_state.get('pendingLeagueIds',[]) if x in ids]
            selected=pending[:args.limit] if args.limit else pending
            cursor=offset
            retry_pending=True
        else:
            selected=ids[offset:offset+args.limit] if args.limit else ids[offset:]
            cursor=min(len(ids),offset+len(selected))
            retry_pending=False
        meta={'scope':'full','offset':offset,'selectedLeagueIds':selected,'catalogueLeagues':len(ids),
              'nextFullOffset':cursor,'fullCompleted':False,'retryPending':retry_pending}
    else:
        open_ids={clean(r.get('leagueId')) for r in previous.get('matches',[])
                  if clean(r.get('iso')) >= recent_start()}
        active=[x for x in ids if x in open_ids]
        other=[x for x in ids if x not in open_ids]
        # Els finals sense IDP són els pendents prioritaris: tornar a llegir
        # aquestes lligues permet descobrir l'ID només al calendari oficial.
        pending_idp={}
        for row in previous.get('matches',[]):
            if not isinstance(row,dict):continue
            lid=clean(row.get('leagueId'))
            status=clean(row.get('status'))
            is_final=bool(re.search(r'\b(FINAL|FINALITZAT|FINALIZADO|ACABAT|ACABADO|FINISHED|FULL TIME)\b',status,re.I))
            if (lid in ids and not clean(row.get('matchId')) and score_tuple(row)
                    and is_final and clean(row.get('iso'))<=local_today().isoformat()):
                pending_idp[lid]=max(clean(row.get('iso')),pending_idp.get(lid,''))
        idp_priority=[lid for lid,_ in sorted(pending_idp.items(),key=lambda item:item[1],reverse=True)]
        pinned=idp_priority+[x for x in FAVOURITE_LEAGUES if x in ids and x not in idp_priority]
        pool=[x for x in active+other if x not in pinned]
        offset=int(previous.get('sources',{}).get('agenda',{}).get('nextFastOffset') or 0)
        if pool:offset%=len(pool)
        take=max(0,args.limit-len(pinned)) if args.limit else len(pool)
        selected=pinned+(pool[offset:offset+take] + pool[:max(0,offset+take-len(pool))]
                         if pool and take else [])
        next_offset=(offset+take)%len(pool) if pool else 0
        meta={'scope':'fast','offset':offset,'selectedLeagueIds':selected,
              'catalogueLeagues':len(ids),'nextFastOffset':next_offset,
              'activeLeagues':len(active)}
    diagnostic['selection']=meta
    return selected,meta


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def norm(s):
    return re.sub(r'[^A-Z0-9]+', ' ', ''.join(ch for ch in unicodedata.normalize('NFD',clean(s)) if unicodedata.category(ch)!='Mn').upper()).strip()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def check_when(s):
    if not isinstance(s, str): raise ValueError('capturedAt absent')
    try:
        d = datetime.fromisoformat(s.replace('Z','+00:00'))
        if d.utcoffset() is None: raise ValueError('capturedAt sense zona horària')
        return d
    except (ValueError, TypeError): raise ValueError('capturedAt invàlid') from None


def check_iso(d):
    try:
        v=datetime.fromisoformat(d).date()
        return v.isoformat()==d and SEASON_FROM<=d<=SEASON_TO
    except (TypeError, ValueError): return False


def check_time(t):
    return isinstance(t,str) and bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t))


def valid_url(value):
    try:
        parsed=urlparse(str(value))
        return parsed.scheme=='https' and parsed.hostname in VALID_HOSTS
    except Exception: return False


def make_match_url(league, matchid):
    if not re.fullmatch(r'\d{4,6}',str(league)) or not re.fullmatch(r'\d{4,10}',str(matchid)):
        return ''
    # Ruta ja usada per ZonaOK amb FECAPA; la presència no prova que hi hagi acta.
    return ROOT+f'?liga={league}&vista=calendar&partido={matchid}'


def official_match_url(url, league='', matchid=''):
    if not valid_url(url):return False
    parsed=urlparse(url)
    q=parse_qs(parsed.query)
    if not re.fullmatch(r'\d{4,10}', str(q.get('partido',[''])[0])): return False
    if not re.fullmatch(r'\d{4,6}', str(q.get('liga',[''])[0])): return False
    if league and q.get('liga',[''])[0]!=str(league):return False
    if matchid and q.get('partido',[''])[0]!=str(matchid):return False
    return True


# DOM de /ag/. Inspirat en el lector real de la drecera de ZonaOK; no fa cap
# suposició sobre la quantitat de clubs, ni sobre la posició de les columnes.
JS_AGENDA = r"""() => {
  const C=x=>String(x??'').replace(/\s+/g,' ').trim();
  const N=x=>C(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();
  const txt=x=>C(x?.innerText||x?.textContent||'');
  const clubLogos=Object.create(null);
  const addClubLogo=(name,src)=>{
    const label=C(name);if(!label||!src)return;
    try{
      const u=new URL(src,location.href);
      if(u.protocol!=='https:'||u.hostname!=='sidgad.cloud'||
         !/^\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(u.pathname))return;
      clubLogos[label]=u.href;
    }catch(_){}
  };
  // FECAPA relaciona els escuts amb els noms complets als atributs alt/title.
  for(const img of document.querySelectorAll('img[src]'))
    addClubLogo(img.getAttribute('alt')||img.getAttribute('title'),img.getAttribute('src'));
  const isoDate=v=>{
    v=C(v); let m, iso='';
    if(m=v.match(/\b(20\d{2})-(\d\d)-(\d\d)\b/))iso=m[0];
    else if(m=v.match(/\b(\d{1,2})[/.\-](\d{1,2})[/.\-](20\d{2})\b/))iso=`${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`;
    else if(m=v.match(/\b(\d{1,2})[/.\-](\d{1,2})\b/)){
      const y=+m[2]>=7?'2026':'2027';
      iso=`${y}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`;
    }
    const d=new Date(iso+'T12:00:00Z');
    return !Number.isNaN(+d) && d.toISOString().slice(0,10)===iso &&
      iso>='2026-07-01' && iso<='2027-06-30'?iso:'';
  };
  const time=v=>{const m=C(v).match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);return m?m[1].padStart(2,'0')+':'+m[2]:'';};
  const score=v=>{const m=C(v).match(/(?:^|\s)(\d{1,3})\s*[-–:]\s*(\d{1,3})(?:\s|$)/);return m?[+m[1],+m[2]]:[null,null];};
  // La taula /ag/ té capçaleres amb colspan: "Local" i "Visitant"
  // ocupen dues cel·les cadascun (logo buit + nom). Indexar les 7
  // capçaleres com si fossin 7 <td> desplaça totes les dades.
  const headerColumns=tr=>{
    let start=0;
    return [...tr.querySelectorAll(':scope > th, :scope > td')].map(h=>{
      const span=Math.max(1,Number(h.colSpan)||1);
      const item={header:N(txt(h)),start,end:start+span};start+=span;return item;
    });
  };
  const rowColumns=tr=>{
    const values=[];
    for(const cell of tr.querySelectorAll(':scope > th, :scope > td')){
      const span=Math.max(1,Number(cell.colSpan)||1);
      values.push(cell);
      // Les cel·les combinades del cos es repeteixen per cobrir l'índex visual.
      for(let j=1;j<span;j++)values.push(cell);
    }
    return values;
  };
  const choose=(cells,header)=>{
    if(!header)return '';
    const contents=cells.slice(header.start,header.end).map(txt).filter(Boolean);
    // En grups logo+nom, no prenem el <td> buit de la imatge.
    return contents.length?contents[contents.length-1]:'';
  };
  const logo=(cells,header)=>{
    if(!header)return '';
    const src=cells.slice(header.start,header.end).map(x=>x?.querySelector('img[src]')?.getAttribute('src')).find(Boolean)||'';
    try{const u=new URL(src,location.href);return u.protocol==='https:'&&u.hostname==='sidgad.cloud'&&
      /^\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(u.pathname)?u.href:'';}catch(_){return '';}
  };
  // /ag/ és ÚNICAMENT la font d'horaris, equips, pista i marcadors.
  // No es llegeixen IDP, lliga ni actes de cap URL, atribut o clic d'aquesta taula.
  // Per fer-ho s'usen EXCLUSIVAMENT les vistes de calendari de competició.
  const rows=[],sampleValidAttributes=[];
  let recognized=0,examined=0,invalid=0,invalidDate=0,invalidTeams=0;
  for(const table of document.querySelectorAll('table')){
    const trs=[...table.querySelectorAll('tr')];
    const head=table.querySelector('thead tr')||trs.find(tr=>tr.querySelector('th'));
    if(!head)continue;
    const h=headerColumns(head),find=re=>h.find(v=>re.test(v.header));
    const date=find(/^(DATA|DIA|DATE|FECHA)/),hour=find(/^(HORA|HOUR)/);
    const home=find(/(^| )(EQUIP LOCAL|EQUIPO LOCAL|LOCAL|CASA|HOME)( |$)/);
    const away=find(/VISITANT|VISITANTE|VISITOR|AWAY/);
    const comp=find(/COMPET|CATEG|LLIGA|LIGA/),result=find(/RESULT|MARCADOR|SCORE/);
    const venue=find(/PISTA|PAVELL|INSTAL|LLOC|SEU|PABELL/);
    if(!home||!away||!date||!hour)continue;
    recognized++;
    const group=txt(table.closest('.sidgad-liga-grupo,section')?.querySelector('h2,h3,.sidgad-liga-header-separador')||table.caption);
    for(const tr of trs.slice(trs.indexOf(head)+1)){
      const cells=rowColumns(tr);if(!cells.length)continue;
      examined++;
      const homeName=choose(cells,home),awayName=choose(cells,away);
      if(!homeName||!awayName||N(homeName)===N(awayName)){invalid++;invalidTeams++;continue;}
      const iso=isoDate(choose(cells,date)),start=time(choose(cells,hour));
      if(!iso||!start){invalid++;invalidDate++;continue;}
      const s=score(choose(cells,result));
      if(sampleValidAttributes.length<8)sampleValidAttributes.push({
        iso,competition:choose(cells,comp)||group,
        param_game:C(tr.getAttribute('param_game')).slice(0,120),
        fecha:C(tr.getAttribute('fecha')).slice(0,80),
        hasOnclick:tr.hasAttribute('onclick')
      });
      const homeLogo=logo(cells,home),awayLogo=logo(cells,away);
      addClubLogo(homeName,homeLogo);addClubLogo(awayName,awayLogo);
      rows.push({iso,time:start,competition:choose(cells,comp)||group,
        home:homeName,away:awayName,homeScore:s[0],awayScore:s[1],
        venue:choose(cells,venue),homeLogo,awayLogo,
        leagueId:'',matchId:'',actaUrl:'',status:''});
    }
  }
  return {rows,clubLogos,counts:{tables:document.querySelectorAll('table').length,
    recognizedTables:recognized,examined,invalid,invalidDate,invalidTeams,
    exported:rows.length,withReliableIDs:0,sampleValidAttributes}};
}"""

JS_CLUB_LOGOS = r"""() => {
  const C=x=>String(x??'').replace(/\s+/g,' ').trim();
  const out=Object.create(null);
  for(const img of document.querySelectorAll('img[src]')){
    const name=C(img.getAttribute('alt')||img.getAttribute('title')||'');
    const src=img.getAttribute('src')||'';
    if(!name||!src)continue;
    try{
      const u=new URL(src,location.href);
      if(u.protocol==='https:'&&u.hostname==='sidgad.cloud'&&
         /^\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(u.pathname))
        out[name]=u.href;
    }catch(_){}
  }
  return out;
}"""


JS_DIRECTE = r"""() => {

JS_DIRECTE = r"""() => {
  const C=x=>String(x??'').replace(/\s+/g,' ').trim(),T=x=>C(x?.innerText||x?.textContent||'');
  const N=x=>C(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();
  const root=document.querySelector('#sidgad-seccion-partidos');
  const seasonText=T(document.querySelector('#sidgad-season-selector')?.selectedOptions?.[0]);
  const m=seasonText.match(/(20\d{2})\s*[\/-]\s*(20\d{2})/);
  if(!root)return {rows:[],errors:['No apareix la secció En directe'],seasonText};
  if(!m||m[1]!=='2026'||m[2]!=='2027')return {rows:[],errors:['Temporada no verificada: '+seasonText],seasonText};
  const logo=side=>{const src=side?.querySelector('img[src]')?.getAttribute('src')||'';try{const u=new URL(src,location.href);return u.protocol==='https:'&&u.hostname==='sidgad.cloud'&&/^\/fecapa\/images\/logos_clubes\/\d+\.png$/i.test(u.pathname)?u.href:'';}catch(_){return '';}};
  const rows=[],errors=[];let examined=0,invalid=0;
  for(const el of root.querySelectorAll('.sidgad-partido-fila')){
    examined++;
    const h=el.querySelector('.sidgad-local'),a=el.querySelector('.sidgad-visitante');
    const home=T(h?.querySelector('.sidgad-equipo-nombre')),away=T(a?.querySelector('.sidgad-equipo-nombre'));
    const dt=T(h?.querySelector('.sidgad-equipo-sub')).match(/^(\d{1,2})\/(\d{1,2})\s+(\d{1,2}):([0-5]\d)$/);
    if(!home||!away||N(home)===N(away)||!dt||+dt[1]>31||+dt[2]>12||+dt[3]>23){invalid++;continue;}
    const y=+dt[2]>=7?'2026':'2027',iso=`${y}-${dt[2].padStart(2,'0')}-${dt[1].padStart(2,'0')}`;
    const d=new Date(iso+'T12:00:00Z');if(Number.isNaN(+d)||d.toISOString().slice(0,10)!==iso){invalid++;continue;}
    const raw=T(el.querySelector('.sidgad-resultado-texto'));
    const sm=raw.match(/^(\d{1,3})\s*[-–:]\s*(\d{1,3})$/);
    const header=el.closest('.sidgad-liga-grupo')?.querySelector('.sidgad-liga-header-separador');
    const competition=C([...header?.childNodes||[]].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' '))||T(header);
    let matchId='',leagueId='',actaUrl='';
    for(const attr of ['idp','partidoId','partitId'])if(/^\d{4,10}$/.test(el.dataset?.[attr]||''))matchId=el.dataset[attr];
    for(const anchor of el.querySelectorAll('a[href]')){
      const raw=anchor.getAttribute('href')||'';
      const match=raw.match(/fecapa_gr_(\d{4,10})_|(?:idp|partido|partit|match)(?:=|\/|_)(\d{4,10})/i);
      if(match&&!matchId)matchId=match[1]||match[2];
      try{const u=new URL(raw,location.href);if(u.protocol!=='https:'||!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname))continue;
        if(/^\d{4,6}$/.test(u.searchParams.get('liga')||''))leagueId=u.searchParams.get('liga');
        if(/^\d{4,10}$/.test(u.searchParams.get('partido')||'')&&/^\d{4,6}$/.test(u.searchParams.get('liga')||''))actaUrl=u.href;
      }catch(_){}
    }
    rows.push({iso,time:dt[3].padStart(2,'0')+':'+dt[4],competition,home,away,
      homeScore:sm?+sm[1]:null,awayScore:sm?+sm[2]:null,
      homeLogo:logo(h),awayLogo:logo(a),matchId,leagueId,actaUrl,venue:'',
      round:T(a?.querySelector('.sidgad-equipo-sub')),status:T(el.querySelector('.sidgad-status-tag'))});
  }
  return {rows,counts:{examined,invalid,exported:rows.length},errors,seasonText};
}"""

# A calendari recuperem ÚNICAMENT URLs reals que el DOM de FECAPA enllaça;
# no generem links amb IDs trobats a scripts ni suposem que un partit té acta.
JS_ACTES = r"""() => {
  const C=x=>String(x??'').replace(/\s+/g,' ').trim();
  const out=[];
  for(const a of document.querySelectorAll('a[href]')){
    try {
      const u=new URL(a.getAttribute('href')||'',location.href);
      if(u.protocol!=='https:'||!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname))continue;
      const league=u.searchParams.get('liga')||'',id=u.searchParams.get('partido')||'';
      if(!/^\d{4,6}$/.test(league)||!/^\d{4,10}$/.test(id))continue;
      const tr=a.closest('tr,.sidgad-partido-fila,.sidgad-partido');
      const cells=tr?[...tr.querySelectorAll('td')].map(x=>C(x.innerText||x.textContent)):[];
      out.push({league,id,url:u.href,context:C(tr?.innerText||'').slice(0,350),cells});
    }catch(_){}
  }
  return {rows:out};
}"""

JS_LEAGUES = r"""() => {
  const ids=new Set();
  const parse=x=>{try{const u=new URL(x,location.href);if(!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname))return;
    const id=u.searchParams.get('liga');if(/^\d{4,6}$/.test(id||''))ids.add(id);}catch(_){}};
  for(const a of document.querySelectorAll('a[href]'))parse(a.href);
  for(const s of document.querySelectorAll('select')){
    const label=((s.id||'')+' '+(s.name||'')).toLowerCase();
    for(const o of s.options){parse(o.value);if(/liga|league|competi/.test(label)&&/^\d{4,6}$/.test(o.value||''))ids.add(o.value);}
  }
  return [...ids];
}"""


# Vista de calendari individual: suport per files SIDGAD i taules HTML.
# Si la pàgina no mostra partits, el diagnòstic ho indica i no inventa dades.
JS_CALENDAR = r"""(league) => {
  const C=x=>String(x??'').replace(/\s+/g,' ').trim();
  const T=x=>C(x?.innerText||x?.textContent||'');
  const N=x=>C(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();
  const parsed=x=>{let m;const text=C(x);let iso='';
    if(m=text.match(/\b(20\d\d)-(\d\d)-(\d\d)\b/))iso=m[0];
    else if(m=text.match(/\b(\d{1,2})[\/.](\d{1,2})[\/.](20\d\d)\b/))iso=m[3]+'-'+m[2].padStart(2,'0')+'-'+m[1].padStart(2,'0');
    else if(m=text.match(/\b(\d{1,2})[\/.](\d{1,2})\b/))iso=(+m[2]>=7?'2026':'2027')+'-'+m[2].padStart(2,'0')+'-'+m[1].padStart(2,'0');
    const d=new Date(iso+'T12:00:00Z');return iso>='2026-07-01'&&iso<='2027-06-30'&&!Number.isNaN(+d)&&d.toISOString().slice(0,10)===iso?iso:'';};
  const clock=x=>{const m=C(x).match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);return m?m[1].padStart(2,'0')+':'+m[2]:'';};
  const score=x=>{const m=C(x).match(/\b(\d{1,3})\s*[-–:]\s*(\d{1,3})\b/);return m?[+m[1],+m[2]]:[null,null];};
  // IDs ONLY from the fixture element, never from the page's ?liga= route.
  const idsFromFixture=el=>{
    const pairs=new Set();
    for(const node of [el,...el.querySelectorAll('[data-liga],[data-league-id],[data-idp],[data-partido-id],[onclick],a[href]')]){
      const ds=node.dataset||{},lid=ds.liga||ds.leagueId||ds.ligaId||'',mid=ds.idp||ds.partidoId||ds.partido||ds.idPartido||ds.matchId||'';
      if(/^\d{4,6}$/.test(lid)&&/^\d{4,10}$/.test(mid))pairs.add(lid+':'+mid);
      for(const k of ['href','onclick','data-url','data-href']){
        const raw=node.getAttribute?.(k)||'';
        const li=raw.match(/[?&]liga=(\d{4,6})\b/i),mi=raw.match(/(?:[?&]partido=|[?&]idp=|fecapa_gr_)(\d{4,10})(?:\b|_)/i);
        if(li&&mi)pairs.add(li[1]+':'+mi[1]);
        try{const u=new URL(raw,location.href);if(u.protocol==='https:'&&/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname)){
          const l=u.searchParams.get('liga')||'',m=u.searchParams.get('partido')||'';
          if(/^\d{4,6}$/.test(l)&&/^\d{4,10}$/.test(m))pairs.add(l+':'+m);
        }}catch(_){}
      }
    }
    if(pairs.size!==1)return {leagueId:'',matchId:'',ambiguous:pairs.size>1};
    const [leagueId,matchId]=[...pairs][0].split(':');
    return {leagueId,matchId,ambiguous:false};
  };
  const rows=[];let examined=0,invalid=0,ambiguousIds=0;
  const leaguesFound=new Set();
  // El calendari REAL es troba a sidgad-calendario-table. En directe és
  // un mòdul global amb sidgad-partido-fila que sovint és ocult.
  const calendarRows=[...document.querySelectorAll('tr.sidgad-calendario-partido')];
  let phase='';
  for(const node of document.querySelectorAll('.sidgad-calendario-fase,tr.sidgad-calendario-partido')){
    if(node.matches('.sidgad-calendario-fase')){phase=T(node);continue;}
    if(!node.matches('tr.sidgad-calendario-partido'))continue;
    examined++;
    const home=T(node.querySelector('.sidgad-col-equipo-home'));
    const away=T(node.querySelector('.sidgad-col-equipo-away'));
    const date=parsed(T(node.querySelector('.sidgad-col-dia')));
    const time=clock(T(node.querySelector('.sidgad-col-hora')));
    if(!home||!away||N(home)===N(away)||!date||!time){invalid++;continue;}
    // Lliga independent del paràmetre de la pàgina: dos links dels equips
    // dins de la mateixa fila. L'IDP surt del botó de detalls de la fila.
    const teamLinks=[...node.querySelectorAll('.sidgad-col-equipo-home a[href],.sidgad-col-equipo-away a[href]')];
    const linkedLeagues=new Set();
    for(const a of teamLinks){
      try{
        const u=new URL(a.getAttribute('href'),document.baseURI);
        if(u.protocol==='https:'&&/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname)&&
            /^\d{4,6}$/.test(u.searchParams.get('liga')||''))linkedLeagues.add(u.searchParams.get('liga'));
      }catch(_){}
    }
    const matchIds=[...new Set([...node.querySelectorAll('[data-calendar-action="details"][data-match-id]')]
      .map(x=>x.getAttribute('data-match-id')).filter(x=>/^\d{4,10}$/.test(x||'')))];
    if(linkedLeagues.size>1||matchIds.length>1)ambiguousIds++;
    const leagueId=linkedLeagues.size===1&&teamLinks.length>=2?[...linkedLeagues][0]:'';
    const matchId=matchIds.length===1?matchIds[0]:'';
    if(leagueId)leaguesFound.add(leagueId);
    const sc=score(T(node.querySelector('.sidgad-col-resultado')));
    const competition=phase||T(document.querySelector('.sidgad-calendario-fase'))||'';
    rows.push({iso:date,time,home,away,competition,leagueId,matchId,
      homeScore:sc[0],awayScore:sc[1],actaUrl:'',status:'',
      venue:T(node.querySelector('.sidgad-col-pista'))});
  }
  // Compatibilitat amb calendaris de format antic, només quan no hi ha
  // taules del calendari real. Mai agafem targetes globals ocultes.
  if(!calendarRows.length){
    for(const el of document.querySelectorAll('.sidgad-partido-fila')){
      const css=getComputedStyle(el),box=el.getBoundingClientRect();
      if(css.display==='none'||css.visibility==='hidden'||box.width<1||box.height<1)continue;
      examined++;
      const home=T(el.querySelector('.sidgad-local .sidgad-equipo-nombre'));
      const away=T(el.querySelector('.sidgad-visitante .sidgad-equipo-nombre'));
      const sub=T(el.querySelector('.sidgad-local .sidgad-equipo-sub'));
      const date=parsed(sub),time=clock(sub);
      if(!home||!away||N(home)===N(away)||!date||!time){invalid++;continue;}
      const meta=idsFromFixture(el);
      if(meta.ambiguous)ambiguousIds++;
      if(meta.leagueId)leaguesFound.add(meta.leagueId);
      const sc=score(T(el.querySelector('.sidgad-resultado-texto')));
      const comp=T(el.closest('.sidgad-liga-grupo')?.querySelector('.sidgad-liga-header-separador'))||T(document.querySelector('h1,h2'));
      rows.push({iso:date,time,home,away,competition:comp,leagueId:meta.leagueId,matchId:meta.matchId,
        homeScore:sc[0],awayScore:sc[1],actaUrl:'',status:'',venue:''});
    }
  }
  return {rows,count:rows.length,examined,invalid,ambiguousIds,leaguesFound:[...leaguesFound],requestedLeague:league};
}"""


# Captura forense mínima del DOM de FECAPA: útil quan la web canvia de
# components (taules en lloc de targetes), sense guardar el contingut complet.
JS_DOM_DIAGNOSTIC = r"""() => {
  const C=x=>String(x??'').replace(/\s+/g,' ').trim();
  const short=(x,n=300)=>C(x).slice(0,n);
  const tables=[...document.querySelectorAll('table')];
  const cards=[...document.querySelectorAll('.sidgad-partido-fila')];
  const tableBrief=t=>({
    headers:[...t.querySelectorAll('thead tr:first-child th,thead tr:first-child td')].map(x=>short(x.textContent,60)).slice(0,16),
    rows:t.querySelectorAll('tr').length,
    sample:[...t.querySelectorAll('tr')].slice(0,3).map(tr=>({text:short(tr.innerText||tr.textContent,300),
      html:short(tr.outerHTML,1800)}))
  });
  const anchors=[...document.querySelectorAll('a[href]')]
    .filter(a=>/partido|liga=|fecapa_gr_|acta/i.test((a.getAttribute('href')||'')+' '+(a.getAttribute('onclick')||'')))
    .slice(0,12).map(a=>({text:short(a.textContent,80),href:short(a.getAttribute('href'),240),onclick:short(a.getAttribute('onclick'),180)}));
  const onclicks=[...document.querySelectorAll('[onclick]')].slice(0,8)
    .map(a=>({tag:a.tagName,onclick:short(a.getAttribute('onclick'),180)}));
  return {url:location.href,title:short(document.title,140),ready:document.readyState,
    headings:[...document.querySelectorAll('h1,h2,h3,.sidgad-liga-header-separador')].slice(0,10).map(x=>short(x.textContent,120)),
    tables:tables.length,firstTables:tables.slice(0,2).map(tableBrief),cards:cards.length,
    firstCards:cards.slice(0,2).map(x=>short(x.outerHTML,1800)),anchors,onclicks,
    selectors:[...document.querySelectorAll('select')].slice(0,6).map(s=>({id:s.id,name:s.name,value:s.value,selected:short(s.selectedOptions?.[0]?.textContent,120)})),
    bodyPreview:short(document.body?.innerText,360)};
}"""


def verified_league_rows(league_id, card_rows, table_rows):
    """Fail-closed: accept a per-league match only with BOTH official IDs in
    the fixture itself. A generic match list must never be relabelled with the
    requested league merely because its page URL contains ?liga=... .

    The result distinguishes safe rows from foreign or unlinked rows and
    whether the returned DOM is actually scoped to the requested league.
    """
    seen_leagues=set()
    accepted=[]
    missing=foreign=0
    for row in list(card_rows)+list(table_rows):
        if not isinstance(row,dict):continue
        lid=clean(row.get('leagueId'));mid=clean(row.get('matchId'))
        if lid and re.fullmatch(r'\d{4,6}',lid):seen_leagues.add(lid)
        if not mid or not lid:
            missing+=1
            continue
        if lid!=str(league_id):
            foreign+=1
            continue
        copied=dict(row)
        if validate_row(copied,'agenda'):
            if not copied.get('actaUrl'):
                copied['actaUrl']=make_match_url(lid,mid)
            accepted.append(copied)
    # A generic multi-league listing may contain correct matches, but it is
    # never proof that we have traversed the whole league calendar.
    mixed=bool(seen_leagues-{str(league_id)}) or bool(foreign)
    # A specific league has been fully verified only when EVERY extracted
    # fixture can be identified; one tagged match among 532 generic rows is
    # not a league-wide calendar.
    verified=bool(accepted) and not mixed and not missing
    status=('verified' if verified else 'mixed-league-list' if mixed
            else 'partial-identifiers' if accepted else 'unverified')
    return accepted,{'verified':verified,'withIDs':len(accepted),'withoutIDs':missing,
                     'foreignRows':foreign,'seenLeagueIds':sorted(seen_leagues,key=int),
                     'status':status}


def finalize_agenda_selection(selection, checked, previous_sources):
    """Persist a scan cursor AND a separate backlog of unverified leagues.

    Scanning an ID is not the same as verifying a league. We can progress to
    later IDs without silently claiming completeness, and retry unresolved
    IDs after the initial catalogue scan.
    """
    verified={x['leagueId'] for x in checked if x.get('verified')}
    attempted={x['leagueId'] for x in checked}
    previous_pending={str(x) for x in previous_sources.get('pendingLeagueIds',[])
                      if re.fullmatch(r'\d{4,6}',str(x))}
    pending=(previous_pending-verified)|(attempted-verified)
    selection['verifiedLeagueIds']=sorted(verified,key=int)
    selection['failedLeagueIds']=sorted(attempted-verified,key=int)
    selection['pendingLeagueIds']=sorted(pending,key=int)
    selection['verifiedLeagues']=len(verified)
    selection['unverifiedLeagues']=len(attempted-verified)
    if selection.get('scope')=='full':
        selection['fullCompleted']=(selection.get('nextFullOffset',0)>=selection.get('catalogueLeagues',0)
                                     and not pending)
    return selection

def record_key(row):
    mid=clean(row.get('matchId'))
    lid=clean(row.get('leagueId'))
    if mid and lid: return 'ID:'+lid+':'+mid
    return '|'.join([row.get('iso',''),row.get('time',''),norm(row.get('competition')),norm(row.get('home')),norm(row.get('away'))])


def validate_row(row, mode):
    if not isinstance(row,dict):return False
    if not check_iso(row.get('iso')) or not check_time(row.get('time')): return False
    if not clean(row.get('home')) or not clean(row.get('away')) or norm(row['home'])==norm(row['away']):return False
    for k in ('homeScore','awayScore'):
        n=row.get(k)
        if n is not None and (not isinstance(n,int) or isinstance(n,bool) or not 0<=n<=199):return False
    if (row.get('homeScore') is None)!=(row.get('awayScore') is None):return False
    # No rebutgem un partit perquè FECAPA publica un enllaç parcial o extern.
    # Es descarta només aquest enllaç; la fila continua sent aprofitable.
    if row.get('actaUrl') and not official_match_url(row['actaUrl'],str(row.get('leagueId') or ''),str(row.get('matchId') or '')):row['actaUrl']=''
    if row.get('leagueId') and not re.fullmatch(r'\d{4,6}',str(row['leagueId'])):return False
    if row.get('matchId') and not re.fullmatch(r'\d{4,10}',str(row['matchId'])):return False
    return True


def unique_rows(rows, mode):
    out={}
    for r in rows:
        if not validate_row(r,mode):continue
        key=record_key(r)
        old=out.get(key)
        if not old or (r.get('matchId') and not old.get('matchId')) or (r.get('homeScore') is not None and old.get('homeScore') is None):out[key]=r
    return sorted(out.values(),key=lambda r:(r['iso'],r['time'],norm(r.get('competition')),norm(r['home'])))


async def chromium_context(p):
    browser=await p.chromium.launch(headless=False,args=['--no-sandbox'])
    ctx=await browser.new_context(locale='ca-ES',timezone_id='Europe/Madrid',viewport={'width':1420,'height':960})
    ctx.set_default_timeout(12000)
    return browser,ctx


async def page_ready(page,selector,ms=18000):
    try:await page.wait_for_selector(selector,timeout=ms)
    except Exception:pass
    await page.wait_for_timeout(1400)


async def set_agenda_filters(page,diagnostic,scope='full'):
    # Mai establim un filtre d'un club concret: només TOTAL/TODOS/TOTS.
    # Si el formulari del portal canvia, cal provar-lo: NO s'inventa cap opció.
    filters=[]
    try:
        sels=await page.locator('select').all()
        for select in sels[:25]:
            info=await select.evaluate('s=>({name:(s.id+" "+s.name+" "+(s.getAttribute("aria-label")||"")),options:[...s.options].map(o=>({value:o.value,text:o.textContent}))})')
            name=norm(info['name'])
            if not re.search(r'CLUB|EQUIP|EQUIPO|TEAM',name):continue
            opts=[x for x in info['options'] if re.search(r'^(TOTS|TODOS|TODAS|ALL|TOTES|TOTS ELS CLUBS)$',norm(x['text']))]
            if opts:
                await select.select_option(value=opts[0]['value']);filters.append('select '+info['name']+'=TOTS')
    except Exception as e:diagnostic['warnings'].append('No es pot modificar el selector de clubs: '+str(e)[:130])
    # Només dates explícitament reconeixibles; no fem clic a cap selector ambigu.
    try:
        for inp in await page.locator('input[type=date]').all():
            info=await inp.evaluate('e=>({name:(e.id+" "+e.name+" "+(e.getAttribute("placeholder")||"") ).toLowerCase()})')
            name=info['name']
            value=(recent_start() if scope=='fast' else SEASON_FROM) if re.search('desde|from|inici|desde|start',name) else SEASON_TO if re.search('hasta|to|fi|end',name) else ''
            if value:
                await inp.fill(value)
                filters.append('date '+name+'='+value)
    except Exception as e:diagnostic['warnings'].append('Dates de /ag/ no configurables: '+str(e)[:130])
    diagnostic['filters']=filters
    if filters:
        # Intentem el botó de recerca només quan hem canviat filtres explícits.
        for name in ('Buscar','Cercar','Filtrar','Consultar','Aplicar','Ver partidos'):
            b=page.get_by_role('button',name=re.compile('^'+name+'$',re.I))
            if await b.count():
                try:await b.first.click(timeout=1800)
                except Exception:pass
                break
        await page.wait_for_timeout(1200)


async def next_page(page):
    selectors=["a[rel='next']",'.paginate_button.next:not(.disabled)',
               "button[aria-label='Next']","a[aria-label='Next']",
               "button[aria-label='Següent']", "a[aria-label='Siguiente']"]
    for css in selectors:
        loc=page.locator(css)
        if await loc.count():
            el=loc.first
            try:
                if await el.is_visible() and await el.is_enabled():
                    await el.click(timeout=2500);await page.wait_for_timeout(1000);return True
            except Exception:pass
    return False


async def collect_agenda(ctx,args,diagnostic):
    """Llegeix /ag/ i un lot de calendaris. A full, el cursor es desa
    al JSON publicat; a fast, només guardem partits recents/futurs.
    """
    page=await ctx.new_page();rows=[];counts=[];errors=[];club_logos={}
    try:
        catalogue=set(league_ids_from_files())
        # Els escuts i els noms s'extreuen del catàleg oficial FECAPA,
        # tal com apareixen associats a la pàgina de competicions.
        try:
            await page.goto(ROOT,wait_until='domcontentloaded',timeout=30000)
            await page_ready(page,'img[src*="logos_clubes"]',12000)
            club_logos.update(await page.evaluate(JS_CLUB_LOGOS))
        except Exception as exc:
            diagnostic['warnings'].append('Catàleg d’escuts FECAPA no disponible: '+str(exc)[:120])
        try:
            await page.goto(AGENDA_URL,wait_until='domcontentloaded',timeout=40000)
            await page_ready(page,'table',19000)
            diagnostic.setdefault('domEvidence',{})['agenda'] = await page.evaluate(JS_DOM_DIAGNOSTIC)
            # Inspecció no destructiva d'una fila existent (després de parsejar
            # la taula es provarà un clic per veure si SIDGAD exposa liga+IDP).
            # No convertim mai el valor param_game en IDP: és un token intern.
            # IDs de selectors i enllaços de l'Agenda REAL, no d'XHR genèrics.
            catalogue.update(await page.evaluate(JS_LEAGUES))
            await set_agenda_filters(page,diagnostic,args.scope)
            catalogue.update(await page.evaluate(JS_LEAGUES))
            seen=set()
            for ix in range(args.pages):
                data=await page.evaluate(JS_AGENDA)
                signature=tuple(record_key(r) for r in data['rows'][:3])+(str(len(data['rows'])),)
                if signature in seen:break
                seen.add(signature)
                chunk=data['rows']
                if args.scope=='fast':chunk=[r for r in chunk if clean(r.get('iso'))>=recent_start()]
                club_logos.update(data.get('clubLogos',{}));rows.extend(chunk);counts.append(data['counts'])
                if not await next_page(page):break
        except Exception as exc:
            errors.append('Agenda /ag/: '+str(exc)[:160])
        # No fem clic ni busquem actes/IDP a /ag/. Només captura horaris.
        prev=load_unified(CANONICAL)
        ids=[lid for lid in catalogue if re.fullmatch(r'\d{4,6}',str(lid))]
        leagues,meta=select_league_batch(ids,args,prev,diagnostic)
        checked=[]
        for lid in leagues:
            try:
                await page.goto(ROOT+f'?liga={lid}&vista=calendar',wait_until='domcontentloaded',timeout=28000)
                # Esperem les files reals de calendari, mai les targetes ocultes.
                await page_ready(page,'tr.sidgad-calendario-partido',20000)
                data=await page.evaluate(JS_CALENDAR,lid)
                if len(diagnostic.setdefault('domEvidence',{}).get('leagues',[])) < 5:
                    diagnostic['domEvidence'].setdefault('leagues',[]).append({
                        'leagueId':lid, **(await page.evaluate(JS_DOM_DIAGNOSTIC))})
                # IDs/actes provenen NOMÉS de les targetes del calendari de lliga.
                # Mai no fem servir la taula de l'Agenda general com a substitut.
                accepted,status=verified_league_rows(lid,data['rows'],[])
                status.update({'leagueId':lid,'rows':len(accepted),'rawRows':data['count'],
                               'tableRows':0,
                               'examined':data.get('examined',0),
                               'ambiguousIds':data.get('ambiguousIds',0),
                               'pageUrl':page.url})
                if args.scope=='fast':accepted=[r for r in accepted if clean(r.get('iso'))>=recent_start()]
                rows.extend(accepted)
                checked.append(status)
                if not status['verified']:
                    diagnostic['warnings'].append(f'Lliga {lid}: no verificada ({status["status"]}); '+
                        f'files {data["count"]}, amb IDs fiables {status["withIDs"]}, '+
                        f'altres lligues {status["foreignRows"]}. No s\'atribueix cap fila genèrica.')
            except Exception as exc:
                errors.append('Lliga '+lid+': '+str(exc)[:100])
                checked.append({'leagueId':lid,'verified':False,'rows':0,'rawRows':0,
                                'tableRows':0,'status':'navigation-error','error':str(exc)[:160]})
        finalize_agenda_selection(meta,checked,prev.get('sources',{}).get('agenda',{}))
        rows=unique_rows(rows,'agenda')
        diagnostic['sourceUrl']=AGENDA_URL
        diagnostic['clubLogos']=club_logos
        diagnostic['idpSources=['competicio-calendar']
        diagnostic['checkedLeagues']=checked
        diagnostic['warnings'].extend(errors)
        diagnostic['counts']={'agendaTables':sum(x.get('recognizedTables',0) for x in counts),
                              'checkedLeagues':len(checked),'verifiedLeagues':meta['verifiedLeagues'],
                              'unverifiedLeagues':meta['unverifiedLeagues'],
                              'validRows':len(rows),
                              'withIDs':sum(bool(r.get('matchId') and r.get('leagueId')) for r in rows),
                              'genericAgendaRows':sum(x.get('exported',0) for x in counts)}
        diagnostic['coverage']='La taula /ag/ només aporta agenda; no s’hi busquen ni IDP ni actes. Les actes es busquen a calendaris de lliga.'
        # A full schedule can be published independently of acta identification.
        # IDP coverage is NOT a precondition to capture genuine /ag/ fixtures.
        generic_count=sum(x.get('exported',0) for x in counts)
        diagnostic['publishSafe']=bool(generic_count or meta['verifiedLeagues'])
        diagnostic['agendaVerified']=bool(generic_count)
        diagnostic['actaIdCoverageVerified']=bool(meta['verifiedLeagues'])
        if generic_count and not meta['verifiedLeagues']:
            diagnostic['warnings'].append('Agenda general llegida sense IDP (correcte). Les actes s’han de vincular des dels calendaris per lliga.')
        if not rows:
            diagnostic['errors'].append('Cap partit vàlid recuperat de /ag/ ni calendaris FECAPA')
            diagnostic['publishSafe']=False
        return rows
    finally:await page.close()

async def collect_directe(ctx,args,diagnostic):
    page=await ctx.new_page()
    try:
        await page.goto(ROOT,wait_until='domcontentloaded',timeout=40000)
        await page_ready(page,'#sidgad-seccion-partidos',20000)
        # La pestanya En directe pot estar tancada; fem clic només si cal.
        if not await page.locator('#sidgad-seccion-partidos .sidgad-partido-fila').count():
            for name in ('EN DIRECTO','EN DIRECTE','DIRECTO'):
                found=page.get_by_text(name,exact=True)
                if await found.count():
                    try:await found.first.click(timeout=2400);break
                    except Exception:pass
        season=page.locator('#sidgad-season-selector')
        if await season.count():
            options=await season.locator('option').all()
            for o in options:
                t=clean(await o.inner_text())
                if re.search(r'2026\s*[/-]\s*2027',t):
                    value=await o.get_attribute('value');await season.select_option(value=value)
                    await page.wait_for_timeout(2000);break
        await page_ready(page,'#sidgad-seccion-partidos .sidgad-partido-fila',22000)
        data=await page.evaluate(JS_DIRECTE)
        diagnostic['counts']=data.get('counts',{})
        diagnostic['warnings'].extend(data.get('errors',[]))
        diagnostic['seasonText']=data.get('seasonText','')
        rows=unique_rows(data.get('rows',[]),'directe')
        if args.scope=='fast':rows=[r for r in rows if in_recent_window(r)]
        diagnostic['counts']['validRows']=len(rows)
        diagnostic['sourceUrl']=page.url
        if not rows and args.scope=='full':raise ValueError('En directe sense partits vàlids o temporada 2026/27 no seleccionada')
        return rows
    finally:await page.close()


def league_ids_from_files():
    ids=set()
    for path in (Path('zonaok-classificacions.json'),Path('zonaok-tots-agenda.json'),CANONICAL):
        if not path.exists():continue
        try:
            doc=json.loads(path.read_text(encoding='utf-8'))
            if 'classificacions' in path.name:
                for value in doc.get('competitions',{}).values():
                    if isinstance(value,dict):ids.add(str(value.get('leagueId','')))
            else:
                for row in doc.get('matches',doc.get('rows',[])):
                    if isinstance(row,dict):ids.add(str(row.get('leagueId') or row.get('league') or ''))
        except (ValueError,TypeError):continue
    return sorted((x for x in ids if re.fullmatch(r'\d{4,6}',x)),key=int)


def eligible_acta(row,scope,now=None):
    """Pendent: reintentar menys sovint com més antic sigui; verificat: congelar.
    El mode full permet una passada històrica, sense tornar a obrir les verificades.
    """
    if not make_match_url(row.get('leagueId',''),row.get('matchId','')):return False
    if not clean(row.get('iso')) or clean(row.get('iso'))>local_today().isoformat():return False
    if archived_complete(row):return False
    if scope=='full':return True
    last=row.get('actaCheckedAt')
    if not last:return True
    try:delta=(now or datetime.now(timezone.utc))-check_when(last)
    except ValueError:return True
    if row.get('actaState')=='available':return delta>=timedelta(days=1)
    cadence=timedelta(days=1 if clean(row.get('iso'))>=recent_start() else 7)
    return delta>=cadence


async def collect_actes(ctx,args,diagnostic):
    doc=load_unified(CANONICAL)
    all_rows=[r for r in doc.get('matches',[]) if eligible_acta(r,args.scope)]
    if args.scope=='full':
        # Cursor per clau estable; així no saltem files quan una acta
        # passa a 'available' i desapareix de la cua pendent.
        key=lambda r:(r.get('iso') or '',str(r.get('leagueId')),str(r.get('matchId')))
        all_rows.sort(key=key)
        last=doc.get('sources',{}).get('actes',{}).get('nextFullKey') or []
        if args.offset=='auto' and len(last)==3:
            offset=next((i for i,r in enumerate(all_rows) if key(r)>tuple(last)),len(all_rows))
        elif args.offset=='auto':offset=0
        else:offset=parse_integer(args.offset,'offset')
        rows=all_rows[offset:offset+args.limit] if args.limit else all_rows[offset:]
        completed=offset+len(rows)>=len(all_rows)
        diagnostic['selection']={'scope':'full','offset':offset,'candidates':len(all_rows),
            'nextFullOffset':min(len(all_rows),offset+len(rows)),
            'nextFullKey':list(key(rows[-1])) if rows else last,
            'fullCompleted':completed}
    else:
        all_rows.sort(key=lambda r:(r.get('actaCheckedAt') or '',r.get('iso') or ''))
        rows=all_rows[:args.limit] if args.limit else all_rows
        diagnostic['selection']={'scope':'fast','candidates':len(all_rows)}
    diag=[];out=[];page=await ctx.new_page()
    try:
        for i,row in enumerate(rows,1):
            league=clean(row['leagueId']);mid=clean(row['matchId']);url=make_match_url(league,mid)
            item={'leagueId':league,'matchId':mid,'actaUrl':url,'actaState':'pending','actaCheckedAt':utc_now()}
            try:
                res=await page.goto(url,wait_until='domcontentloaded',timeout=14000)
                await page.wait_for_timeout(650)
                info=await page.evaluate("""() => ({
                    urls:[...document.querySelectorAll('a[href],iframe[src]')].map(a=>a.href||a.src||''),
                    text:(document.querySelector('main,#sidgad-contenido,.sidgad-contenedor')?.innerText||'').slice(0,1500)
                })""")
                has_report=any(re.search(r'fecapa_gr_'+re.escape(mid)+r'_|/acta(?:/|\?|$)',x,re.I) for x in info['urls'])
                if res and res.status==200 and has_report:item['actaState']='available'
                diag.append({'liga':league,'idp':mid,'http':res.status if res else None,'estat':item['actaState']})
            except Exception as exc:
                diag.append({'liga':league,'idp':mid,'error':str(exc)[:100]})
            out.append(item)
            if i%10==0:print(f'Actes [{i}/{len(rows)}] revisades',flush=True)
    finally:await page.close()
    diagnostic['counts']={'candidates':len(all_rows),'checked':len(rows),
                          'available':sum(x['actaState']=='available' for x in out),
                          'pending':sum(x['actaState']!='available' for x in out)}
    diagnostic['checks']=diag
    return out

async def collect(args):
    from playwright.async_api import async_playwright
    diagnostic={'mode':args.mode,'source':'FECAPA-PLAYWRIGHT','checkedAt':utc_now(),
                'season':SEASON,'warnings':[],'errors':[], 'version':6,'scope':args.scope}
    async with async_playwright() as p:
        browser,ctx=await chromium_context(p)
        try:
            if args.mode=='agenda':rows=await collect_agenda(ctx,args,diagnostic)
            elif args.mode=='directe':rows=await collect_directe(ctx,args,diagnostic)
            else:rows=await collect_actes(ctx,args,diagnostic)
        finally:
            await ctx.close();await browser.close()
    packet={'schema':'zonaok-captura-v1',
            'kind':args.mode,'season':SEASON,'source':'FECAPA-PLAYWRIGHT',
            'capturedAt':utc_now(), 'sourceUrl':diagnostic.get('sourceUrl',AGENDA_URL),
            'counts':diagnostic.get('counts',{}), 'scope':args.scope,
            'clubLogos':diagnostic.get('clubLogos',{}),
            'selection':diagnostic.get('selection',{}), 'rows':rows}
    return packet,diagnostic


def load_unified(path):
    if path.exists():
        doc=json.loads(path.read_text(encoding='utf-8'))
        if doc.get('schema')!='zonaok-partits-total-v1' or not isinstance(doc.get('matches'),list):
            raise ValueError('JSON unificat preexistent incompatible: es conserva sense modificar')
        return doc
    # Primera execució: recuperar tota l'Agenda publicada (evitar pèrdua de dades).
    old=Path('zonaok-tots-agenda.json')
    rows=[]
    if old.exists():
        doc=json.loads(old.read_text(encoding='utf-8'))
        if not isinstance(doc.get('rows'),list):raise ValueError('Agenda existent no reconeguda; no sobreescriure')
        rows=[dict(x) for x in doc['rows'] if isinstance(x,dict)]
    return {'schema':'zonaok-partits-total-v1','season':SEASON,'updatedAt':'',
            'sources':{},'matches':rows}


def score_tuple(r):
    a=r.get('homeScore');b=r.get('awayScore')
    return a is not None and b is not None and all(isinstance(x,int) and not isinstance(x,bool) for x in (a,b))


def same_fixture(a,b):
    return a.get('iso')==b.get('iso') and a.get('time')==b.get('time') and \
        norm(a.get('home'))==norm(b.get('home')) and norm(a.get('away'))==norm(b.get('away')) and \
        (not a.get('competition') or not b.get('competition') or norm(a['competition'])==norm(b['competition']))


def canonicalize(r):
    row=dict(r)
    if row.get('league') and not row.get('leagueId'):row['leagueId']=str(row['league'])
    if row.get('id') and not row.get('matchId'):row['matchId']=str(row['id'])
    row['leagueId']=clean(row.get('leagueId'))
    row['matchId']=clean(row.get('matchId'))
    if row['leagueId'] and row['matchId']:
        if not row.get('actaUrl'):row['actaUrl']=make_match_url(row['leagueId'],row['matchId'])
        row.setdefault('actaState','pending')
    return row


def match_index(rows,incoming,mode):
    lid=clean(incoming.get('leagueId'));mid=clean(incoming.get('matchId'))
    if lid and mid:
        exact=[i for i,r in enumerate(rows) if clean(r.get('leagueId'))==lid and clean(r.get('matchId'))==mid]
        if len(exact)==1:return exact[0]
        if len(exact)>1:return None
    def compatible_id(r):
        return ((not mid or not r.get('matchId') or clean(r.get('matchId'))==mid) and
                (not lid or not r.get('leagueId') or clean(r.get('leagueId'))==lid))
    candidates=[i for i,r in enumerate(rows) if same_fixture(r,incoming) and compatible_id(r)]
    if len(candidates)==1:return candidates[0]
    if not candidates and (mid or lid):
        # Lliga/calendari poden tenir noms diferents per a la mateixa categoria.
        # L'única equivalència permesa sense nom de competició és un partit
        # ÚNIC amb data/hora/equips exactament iguals i cap ID contradictori.
        weak=[i for i,r in enumerate(rows) if compatible_id(r) and
              r.get('iso')==incoming.get('iso') and r.get('time')==incoming.get('time')
              and norm(r.get('home'))==norm(incoming.get('home'))
              and norm(r.get('away'))==norm(incoming.get('away'))]
        if len(weak)==1:return weak[0]
    return None


def merge_unified(packet,previous,mode):
    if packet.get('schema')!='zonaok-captura-v1' or packet.get('kind')!=mode or packet.get('season')!=SEASON:
        raise ValueError('Captura incompatible: no publicar')
    timestamp=check_when(packet.get('capturedAt'))
    incoming=packet.get('rows')
    if not isinstance(incoming,list):raise ValueError('Captura no reconeguda')
    if mode=='agenda' and packet.get('scope')=='full' and not (
        packet.get('counts',{}).get('genericAgendaRows',0)>0
        or packet.get('selection',{}).get('verifiedLeagues',0)>0
    ):
        raise ValueError('Ni Agenda general amb partits ni calendaris de lliga verificats: publicació bloquejada')
    if not incoming and packet.get('scope')!='fast':raise ValueError('Captura buida en mode full: no publicar')
    if previous.get('schema')!='zonaok-partits-total-v1':raise ValueError('Esquema unificat desconegut')
    if previous.get('season')!=SEASON:raise ValueError('Temporada inesperada al JSON')
    if not incoming:
        return previous,{'new':0,'updated':0,'unmatched':0,'unchanged':0,
                         'ambiguousOrInvalid':0,'skipEmpty':True}
    rows=[canonicalize(r) for r in previous['matches']]
    counts={'new':0,'updated':0,'unmatched':0,'ambiguousOrInvalid':0,'unchanged':0}
    for raw in incoming:
        if not isinstance(raw,dict):counts['ambiguousOrInvalid']+=1;continue
        r=dict(raw)
        if mode!='actes' and not validate_row(r,mode):counts['ambiguousOrInvalid']+=1;continue
        if mode=='actes':
            lid=clean(r.get('leagueId'));mid=clean(r.get('matchId'))
            if not official_match_url(r.get('actaUrl',''),lid,mid):counts['ambiguousOrInvalid']+=1;continue
            indexes=[i for i,x in enumerate(rows) if clean(x.get('leagueId'))==lid and clean(x.get('matchId'))==mid]
            if len(indexes)!=1:counts['unmatched']+=1;continue
            idx=indexes[0];old=rows[idx]
            previous_time=old.get('actaCheckedAt')
            if previous_time and check_when(previous_time)>timestamp:counts['unchanged']+=1;continue
            old['actaUrl']=r['actaUrl']
            if old.get('actaState')!='available' or r.get('actaState')=='available':
                old['actaState']='available' if r.get('actaState')=='available' else 'pending'
            old['actaCheckedAt']=r['actaCheckedAt'];counts['updated']+=1
            continue
        idx=match_index(rows,r,mode)
        if idx is None:
            if mode!='agenda':counts['unmatched']+=1;continue
            rows.append(canonicalize(r));counts['new']+=1;continue
        old=rows[idx]
        if archived_complete(old):
            counts['unchanged']+=1
            continue
        prop='lastAgendaAt' if mode=='agenda' else 'lastDirecteAt'
        previous_time=old.get(prop)
        if previous_time and check_when(previous_time)>timestamp:counts['unchanged']+=1;continue
        if mode=='agenda':
            for field in ('iso','time','competition','home','away','venue','homeLogo','awayLogo','matchId','leagueId','round'):
                if r.get(field) not in (None,''):old[field]=r[field]
            if score_tuple(r) and not (old.get('lastDirecteAt') or old.get('directeUpdatedAt') or
                                           norm(old.get('scoreSource')) in ('EN DIRECTE','DIRECTE')):
                old['homeScore']=r['homeScore'];old['awayScore']=r['awayScore']
                old['scoreSource']='Agenda';old['scoreUpdatedAt']=packet['capturedAt']
            if r.get('status') and not (old.get('lastDirecteAt') or old.get('directeUpdatedAt')):
                old['status']=r['status']
        else:
            # Marcadors només sobre partits coneguts i amb identificació inequívoca.
            for field in ('leagueId','matchId'):
                if not old.get(field) and r.get(field):old[field]=r[field]
            if score_tuple(r):
                old['homeScore']=r['homeScore'];old['awayScore']=r['awayScore']
                old['scoreSource']='En directe';old['scoreUpdatedAt']=packet['capturedAt']
            if r.get('status'):old['status']=r['status']
            old['directeUpdatedAt']=packet['capturedAt']
        old[prop]=packet['capturedAt']
        rows[idx]=canonicalize(old);counts['updated']+=1
    for i,row in enumerate(rows):rows[i]=canonicalize(row)
    rows.sort(key=lambda r:(r.get('iso',''),r.get('time',''),norm(r.get('competition')),norm(r.get('home'))))
    sources=dict(previous.get('sources',{}))
    prev_mode=dict(sources.get(mode,{}))
    selection=packet.get('selection',{})
    progress={k:selection[k] for k in ('nextFullOffset','nextFullKey','nextFastOffset','fullCompleted',
                                       'catalogueLeagues','pendingLeagueIds','verifiedLeagueIds',
                                       'failedLeagueIds','verifiedLeagues','unverifiedLeagues')
              if k in selection}
    sources[mode]={**prev_mode,'capturedAt':packet['capturedAt'],'mergedAt':utc_now(),**counts,**progress}
    # Full per lots: reiniciar només quan realment s'ha acabat el catàleg.
    # El cursor viatja al JSON final, no a un fitxer de control extern.
    club_logos=dict(previous.get('clubLogos') or {})
    raw_logos=packet.get('clubLogos')
    if isinstance(raw_logos,dict):
        for name,url in raw_logos.items():
            if (clean(name) and isinstance(url,str) and
                re.fullmatch(r'https://sidgad\.cloud/fecapa/images/logos_clubes/\d+(?:_\d+)?\.(?:png|gif)',url,re.I)):
                club_logos[clean(name)]=url
    result={**previous,'schema':'zonaok-partits-total-v1','season':SEASON,'updatedAt':utc_now(),
            'sources':sources,'matches':rows,'clubLogos':club_logos,'stats':{'total':len(rows),'withScores':sum(score_tuple(x) for x in rows),
                      'withActaLinks':sum(bool(x.get('actaUrl')) for x in rows),
                      'verifiedActes':sum(x.get('actaState')=='available' for x in rows)}}
    return result,counts


def write_compatibility(doc):
    """Miralls temporals: l'app antiga encara llegeix JSON separats."""
    rows=doc['matches'];now=utc_now()
    base={'schema':'zonaok-all-v1','season':SEASON,'publishedAt':now,'source':'FECAPA-PLAYWRIGHT'}
    agenda={**base,'kind':'agenda','rows':rows,'capturedAt':now,'clubLogos':doc.get('clubLogos',{})}
    Path('zonaok-tots-agenda.json').write_text(json.dumps(agenda,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    today_local=datetime.now(ZoneInfo('Europe/Madrid'))
    cutoff=(today_local-timedelta(days=7)).strftime('%Y-%m-%d')
    today=today_local.strftime('%Y-%m-%d')
    done=[r for r in rows if cutoff<=r.get('iso','')<=today and score_tuple(r) and \
          not re.search(r'EN JOC|EN DIRECTE|PLAYING|LIVE|IN PROGRESS',clean(r.get('status')),re.I)]
    results={**base,'kind':'resultats-7dies','agendaCount':len(rows),'rows':done}
    Path('zonaok-tots-resultats-7dies.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Mirall compatible amb index.html (l'aplicació admet fins a 20.000 fitxes).
    # El JSON unificat continua sent la font completa, sense límit de 1.200.
    fixtures=[]
    for r in rows:
        if not (check_iso(r.get('iso')) and check_time(r.get('time')) and r.get('home') and r.get('away')):continue
        lid=clean(r.get('leagueId'));mid=clean(r.get('matchId'))
        url=make_match_url(lid,mid)
        if url:fixtures.append({'league':lid,'id':mid,'iso':r['iso'],'time':r['time'],
                                'home':r['home'],'away':r['away'],'actaUrl':url})
    prior=Path('zonaok-actes.json')
    if prior.exists():
        try:
            old=json.loads(prior.read_text(encoding='utf-8'))
            if old.get('version')==1 and isinstance(old.get('fixtures'),list):
                by_id={(x['league'],x['id']):x for x in fixtures}
                for x in old['fixtures']:
                    if isinstance(x,dict) and x.get('league') and x.get('id') and (x['league'],x['id']) not in by_id:by_id[(x['league'],x['id'])]=x
                fixtures=list(by_id.values())
            else:return {'legacyActes':'Esquema antic desconegut; conservat'}
        except (ValueError,KeyError):return {'legacyActes':'Fitxer antic malformat; conservat'}
    if len(fixtures)>MAX_LEGACY_ACTA_FIXTURES:return {'legacyActes':f'Conservat: {len(fixtures)} supera límit de {MAX_LEGACY_ACTA_FIXTURES}'}
    prior.write_text(json.dumps({'version':1,'generatedAt':now,'source':'FECAPA-PLAYWRIGHT',
                                 'fixtures':fixtures},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'legacyActes':len(fixtures),'resultsLast7Days':len(done)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('collect');a.add_argument('--mode',choices=['agenda','directe','actes'],required=True)
    a.add_argument('--scope',choices=['fast','full'],default='fast',help='fast=actualitzacio rapida; full=històric per lots')
    a.add_argument('--offset',default='auto',help='full: desplacament de lot, o auto (cursor guardat al JSON)')
    a.add_argument('--pages',type=int,default=10,help='Nombre maxim de pagines de /ag/')
    a.add_argument('--limit',type=int,default=20,help='Agenda: lligues; Actes: partits; Directe: ignorat. 0=totes.')
    a.add_argument('--capture',required=True);a.add_argument('--report',required=True)
    v=sub.add_parser('validate',help='Verificar que no es perden partits davant del HEAD de GitHub')
    v.add_argument('--output',default=str(CANONICAL))
    b=sub.add_parser('merge');b.add_argument('--mode',choices=['agenda','directe','actes'],required=True)
    b.add_argument('--capture',required=True);b.add_argument('--output',default=str(CANONICAL));b.add_argument('--report',required=True)
    b.add_argument('--compat',action='store_true',help='Generar miralls dels JSON que encara usa l’app')
    args=parser.parse_args()
    if args.command=='validate':
        new=load_unified(Path(args.output))
        count=len(new['matches'])
        try:
            text=subprocess.check_output(['git','show',f'HEAD:{args.output}'],stderr=subprocess.DEVNULL)
            old=json.loads(text)
            if old.get('schema')!='zonaok-partits-total-v1':raise ValueError('HEAD: esquema desconegut')
            if count<len(old.get('matches',[])):
                raise ValueError(f'ERROR: {count} partits nous, {len(old["matches"])} antics: no publicar')
        except subprocess.CalledProcessError:
            pass   # Primera publicació sense JSON anterior.
        print('Validació correcta: ',count,'partits conservats')
        return 0
    if args.command=='collect':
        if args.limit<0 or args.pages<1 or args.pages>100:parser.error('limit >= 0 i pages entre 1 i 100')
        packet,diag=asyncio.run(collect(args))
        Path(args.capture).write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        Path(args.report).write_text(json.dumps(diag,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(diag,ensure_ascii=False,indent=2))
        if args.mode=='agenda' and (not packet['rows'] or not diag.get('publishSafe',True)):
            print('ERROR: Agenda no publicable; revisar registres de liga+IDP. Diagnòstic DESAT a '+args.report,file=sys.stderr)
            return 2
        return 0
    packet=json.loads(Path(args.capture).read_text(encoding='utf-8'))
    previous=load_unified(Path(args.output))
    doc,diagnostic=merge_unified(packet,previous,args.mode)
    if not diagnostic.get('skipEmpty'):
        Path(args.output).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if args.compat:diagnostic.update(write_compatibility(doc))
    Path(args.report).write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(diagnostic,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:sys.exit('ERROR ZonaOK AUTO (no publicat): '+str(exc))
