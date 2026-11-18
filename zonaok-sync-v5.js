/* ZonaOK V6 — Agenda com a font de partits, En directe nomes com a font de marcadors.
   Carregar ABANS d'app.js. Conserva V2 (classificacions) i les dades existents.
   No consulta FECAPA des del web: les dues dreceres Safari llegeixen el DOM.
*/
(() => {
  'use strict';
  const KEY='ZONAOK_FECAPA_SAFARI_V2';
  const ROOT='https://www.hoqueipatins.fecapa.cat/';
  const AGENDA=ROOT+'ag/';
  const $=s=>document.querySelector(s);
  const text=s=>String(s??'').replace(/\s+/g,' ').trim().slice(0,180);
  const norm=s=>text(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-zA-Z0-9]+/g,' ').trim().toUpperCase();
  const validDate=s=>/^20\d\d-\d\d-\d\d$/.test(String(s||''));
  const validTime=s=>/^([01]\d|2[0-3]):[0-5]\d$/.test(String(s||''));
  const validScore=n=>Number.isInteger(n)&&n>=0&&n<200;
  const isBarca=s=>/^(?:BAR|BARCA|FC BARCELONA|F C BARCELONA|FCBETRANS|FCBETERANS)(?: [A-Z0-9]+)?$/.test(norm(s));
  const isCeloni=s=>norm(s).includes('CELONI');
  const isClub=s=>isBarca(s)||isCeloni(s);
  const read=()=>{try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{}}catch(_){return {}}};
  const write=s=>{try{localStorage.setItem(KEY,JSON.stringify(s));return true}catch(_){return false}};
  const rowKey=r=>[r.iso,r.time,norm(r.competition),norm(r.home),norm(r.away)].join('|');
  const plus=(date,amount)=>{const d=new Date(date+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+amount);return d.toISOString().slice(0,10)};
  const monday=()=>{const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const iso=['year','month','day'].map(t=>p.find(a=>a.type===t).value).join('-');const d=new Date(iso+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));return d.toISOString().slice(0,10)};
  const nice=iso=>{try{return new Intl.DateTimeFormat('ca-ES',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(iso+'T12:00:00Z'))}catch(_){return iso}};
  const timestamp=t=>{try{return new Intl.DateTimeFormat('ca-ES',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Madrid'}).format(new Date(t))}catch(_){return ''}};
  const savedStamp=r=>String(r.capturedAt||'');
  const cleanAgenda=a=>{
    if(!Array.isArray(a)||a.length!==8)return null;
    const [iso,time,competition,home,away,scoreH,scoreA,venue]=a;
    if(!validDate(iso)||!validTime(time)||!text(home)||!text(away)||!isClub(home)&&!isClub(away))return null;
    if((scoreH!==null||scoreA!==null)&&(!validScore(scoreH)||!validScore(scoreA)))return null;
    return {iso,time,competition:text(competition),home:text(home),away:text(away),homeScore:scoreH,awayScore:scoreA,venue:text(venue)};
  };
  const cleanScore=a=>{
    if(!Array.isArray(a)||a.length!==7)return null;
    const [iso,time,competition,home,away,homeScore,awayScore]=a;
    if(!validDate(iso)||!validTime(time)||!text(home)||!text(away)||!validScore(homeScore)||!validScore(awayScore)||!isClub(home)&&!isClub(away))return null;
    return {iso,time,competition:text(competition),home:text(home),away:text(away),homeScore,awayScore};
  };
  const mergeRows=(prior=[],next=[])=>{
    const map=new Map();
    for(const r of [...prior,...next]){
      if(!r||!validDate(r.iso)||!validTime(r.time))continue;
      const k=rowKey(r),old=map.get(k);
      if(!old) {map.set(k,r);continue;}
      if(savedStamp(old)>savedStamp(r))continue;
      const combined={...old,...r};
      // Una Agenda encara sense marcador mai esborra un marcador conegut.
      if(validScore(old.homeScore)&&validScore(old.awayScore)&&
         (r.homeScore==null||r.awayScore==null)){
        combined.homeScore=old.homeScore;combined.awayScore=old.awayScore;
      }
      // Conservem la pista literal fins i tot si FECAPA retorna una cel·la buida.
      if(!text(r.venue)&&text(old.venue))combined.venue=old.venue;
      map.set(k,combined);
    }
    return [...map.values()].sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time)).slice(-2000);
  };
  const mergeData=(store,kind,p)=>{
    if(kind==='agenda-v5'){
      if(!Array.isArray(p.rows)||p.rows.length>150||!validDate(p.weekStart)||!validDate(p.weekEnd))throw Error('Dades d’Agenda no vàlides');
      const next=p.rows.map(cleanAgenda);
      if(!next.length||next.some(r=>!r)||new Set(next.map(rowKey)).size!==next.length)throw Error('Hi ha partits buits o duplicats');
      const stamped=next.map(r=>({...r,capturedAt:p.capturedAt}));
      store.agenda={rows:mergeRows(store.agenda?.rows||[],stamped),capturedAt:[store.agenda?.capturedAt,p.capturedAt].filter(Boolean).sort().pop()};
      const cb=p.counts?.barca ?? next.filter(r=>isBarca(r.home)||isBarca(r.away)).length;
      const cs=p.counts?.celoni ?? next.filter(r=>isCeloni(r.home)||isCeloni(r.away)).length;
      const pistes=next.filter(r=>!!r.venue).length;
      return `Agenda: ${next.length} partits (${cb} Barça, ${cs} Sant Celoni) · ${pistes} pistes`;
    }
    if(kind==='resultats-v5'){
      if(!Array.isArray(p.rows)||p.rows.length>300)throw Error('Dades d’En directe no vàlides');
      const next=p.rows.map(cleanScore);
      if(!next.length||next.some(r=>!r))throw Error('Cap marcador vàlid');
      // Es guarden els marcadors, pero la pantalla nomes aplica els que encaixen
      // sense ambiguitat amb un partit importat d'Agenda.
      const stamped=next.map(r=>({...r,capturedAt:p.capturedAt}));
      store.scoreUpdates={rows:mergeRows(store.scoreUpdates?.rows||[],stamped),capturedAt:[store.scoreUpdates?.capturedAt,p.capturedAt].filter(Boolean).sort().pop()};
      return `${next.length} marcadors consultats a En directe`;
    }
    throw Error('Tipus desconegut');
  };
  let importMessage='';
  (function importNewHash(){
    const hash=location.hash||'';if(!hash.startsWith('#fecapa='))return;
    let p;try{p=JSON.parse(decodeURIComponent(hash.slice(8)))}catch(_){return;}
    if(p?.kind!=='agenda-v5'&&p?.kind!=='resultats-v5')return; // els paquets antics els gestiona app.js
    history.replaceState(null,'',location.pathname+location.search);
    try{
      if(p.source!=='FECAPA-SAFARI'||p.v!==5||!Number.isFinite(Date.parse(p.capturedAt)))throw Error('Font o data desconeguda');
      const store=read();importMessage=mergeData(store,p.kind,p);
      if(!write(store))throw Error('No es poden desar les dades localment');
    }catch(e){importMessage='Error d’importació: '+e.message;}
  })();

  function sideClub(name){if(isBarca(name))return 'barca';if(isCeloni(name))return 'celoni';return '';}
  const coreCat=s=>norm(s).replace(/\s+\d+$/,'').replace(/\s+(GRUP|GRUPO)\s+[A-Z0-9]+$/,'');
  const nameKey=s=>{const n=norm(s);if(['BAR','BARCA','FC BARCELONA','F C BARCELONA'].includes(n))return 'BARCA';if(n==='CPSC'||n==='CP SANT CELONI'||n==='SANT CELONI')return 'SANT CELONI';return n;};
  function matches(a,b){
    if(a.iso!==b.iso||a.time!==b.time)return false;
    const ah=nameKey(a.home),aa=nameKey(a.away),bh=nameKey(b.home),ba=nameKey(b.away);
    if(ah===bh&&aa===ba)return true;
    // Per abreviatures d'En directe (BAR, CPSC, HSCA, etc.) necessitem
    // mateixa banda del club i categoria compatible; nomes s'acceptara
    // si hi ha una unica coincidencia a l'Agenda.
    if(coreCat(a.competition)&&coreCat(b.competition)&&coreCat(a.competition)!==coreCat(b.competition))return false;
    return (sideClub(a.home)&&sideClub(a.home)===sideClub(b.home)) ||
           (sideClub(a.away)&&sideClub(a.away)===sideClub(b.away));
  }
  function resolved(row,store){
    const candidates=[];
    const all=[...(store.scoreUpdates?.rows||[]),...(store.live?.rows||[])];
    for(const s of all){
      if(!validScore(s.homeScore)||!validScore(s.awayScore)||!matches(row,s))continue;
      const matched=(store.agenda?.rows||[]).filter(a=>matches(a,s));
      if(matched.length!==1||rowKey(matched[0])!==rowKey(row))continue;
      candidates.push({homeScore:s.homeScore,awayScore:s.awayScore,capturedAt:s.capturedAt||store.live?.capturedAt||''});
    }
    candidates.sort((a,b)=>savedStamp(b).localeCompare(savedStamp(a)));
    const latest=candidates[0];
    // En directe té prioritat sobre els marcadors d'Agenda, que es publiquen amb retard.
    if(latest)
      return {...row,homeScore:latest.homeScore,awayScore:latest.awayScore,scoreSource:'En directe',scoreCapturedAt:latest.capturedAt};
    return {...row,scoreSource:validScore(row.homeScore)&&validScore(row.awayScore)?'Agenda':''};
  }
  function el(tag,cls,txt){const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e;}
  function teamSide(name){
    const side=el('div','side'),crest=el('div','crest');
    let img='';const n=norm(name);
    if(isBarca(name))img='https://sidgad.cloud/fecapa/images/logos_clubes/234.png';
    if(isCeloni(name))img='https://sidgad.cloud/fecapa/images/logos_clubes/281.png';
    if(img){const i=el('img');i.src=img;i.alt='Escut '+name;i.loading='lazy';i.onerror=()=>crest.replaceChildren(el('span','crest-fallback',name.slice(0,1)));crest.append(i)}
    else crest.append(el('span','crest-fallback',name.slice(0,1).toUpperCase()));
    side.append(crest,el('strong','',name));return side;
  }
  function card(r,compact){
    const cls=isBarca(r.home)||isBarca(r.away)?'zok-v5-barca':
      /INFANTIL OR 10/.test(norm(r.competition))&& (isCeloni(r.home)||isCeloni(r.away))?'zok-v5-infantil':
      /JUVENIL OR 6/.test(norm(r.competition))&&(isCeloni(r.home)||isCeloni(r.away))?'zok-v5-juvenil':'zok-v5-neutral';
    const c=el('article','match zok-v5 '+cls+(compact?' zok-compact':''));
    c.dataset.zokV5='1';
    const top=el('div','match-top');top.append(el('span','pill',r.competition||'Categoria no indicada'),el('span','tag',r.scoreSource||'Agenda · FECAPA'));c.append(top);
    const dt=el('div','match-date');dt.append(el('strong','',r.time),el('small','',nice(r.iso)));if(compact)dt.dataset.zokCategoria=r.competition||'Categoria';c.append(dt);
    const teams=el('div','teams'),middle=el('div','middle');middle.append(el('div','score',validScore(r.homeScore)&&validScore(r.awayScore)?`${r.homeScore} : ${r.awayScore}`:'— : —'),el('small','score-note',r.scoreSource||'Pendent'));
    teams.append(teamSide(r.home),middle,teamSide(r.away));c.append(teams);
    if(!compact){
      const venue=el('div','venue');venue.append(el('strong','','📍 '+(r.venue||'Pista no indicada a Agenda')));c.append(venue);
    }
    return c;
  }
  const byWeek=(rows)=>{const start=monday(),end=plus(start,6);return rows.filter(r=>r.iso>=start&&r.iso<=end).sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time));};
  const favoriteDefs=[
    {name:'Barça Aleví',f:r=>(isBarca(r.home)||isBarca(r.away))&&norm(r.competition)==='ALEVI OR 3'},
    {name:'Sant Celoni Infantil B',f:r=>(isCeloni(r.home)||isCeloni(r.away))&&norm(r.competition)==='INFANTIL OR 10'},
    {name:'Sant Celoni Juvenil B',f:r=>(isCeloni(r.home)||isCeloni(r.away))&&norm(r.competition)==='JUVENIL OR 6'}
  ];
  function drawHome(rows){
    const root=$('#home-cards');if(!root)return;
    const sig=JSON.stringify(rows.map(r=>[rowKey(r),r.homeScore,r.awayScore,r.venue]));
    if(root.dataset.zokV5Sig===sig&&root.querySelector('[data-zok-v5]'))return;
    root.dataset.zokV5Sig=sig;
    const frag=document.createDocumentFragment();let count=0;
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const now=['year','month','day'].map(t=>parts.find(p=>p.type===t).value).join('-');
    for(const def of favoriteDefs){
      const candidates=rows.filter(def.f),next=candidates.find(r=>r.iso>=now)||candidates[candidates.length-1];
      if(next){frag.append(card(next,false));count++}
      else{const note=el('div','empty');note.dataset.zokV5='1';note.append(el('strong','',def.name+' · Sense partit importat aquesta setmana'));frag.append(note)}
    }
    root.replaceChildren(frag);if($('#home-count'))$('#home-count').textContent=count+' partits';
  }
  function activeTab(){const button=$('.navbtn.active');return button?.dataset.tab||($('#results-section')?.classList.contains('hide')?'home':'');}
  function drawList(tab,rows){
    const root=$('#results-list');if(!root||$('#results-section')?.classList.contains('hide'))return;
    if(tab==='classificacions'||!['barca','celoni','grupalevi','grupinfantil'].includes(tab))return;
    let selected=tab==='barca'?rows.filter(r=>isBarca(r.home)||isBarca(r.away)):
      tab==='celoni'?rows.filter(r=>isCeloni(r.home)||isCeloni(r.away)):
      tab==='grupalevi'?rows.filter(r=>norm(r.competition)==='ALEVI OR 3'&&(isBarca(r.home)||isBarca(r.away))):
      rows.filter(r=>norm(r.competition)==='INFANTIL OR 10'&&(isCeloni(r.home)||isCeloni(r.away)));
    if(tab.startsWith('grup'))selected=[...selected].reverse();
    const sig=tab+'|'+JSON.stringify(selected.map(r=>[rowKey(r),r.homeScore,r.awayScore]));
    if(root.dataset.zokV5Sig===sig&&root.querySelector('[data-zok-v5]'))return;
    root.dataset.zokV5Sig=sig;
    const frag=document.createDocumentFragment();
    if(!selected.length){const empty=el('div','empty','No hi ha partits verificats d’aquest club durant aquesta setmana a l’Agenda importada.');empty.dataset.zokV5='1';frag.append(empty);}
    for(const r of selected)frag.append(card(r,true));
    root.replaceChildren(frag);
    const labels={barca:'Barça · Setmana',celoni:'CP Sant Celoni · Setmana',grupalevi:'Barça Aleví OR 3 · Setmana',grupinfantil:'Sant Celoni Infantil OR 10 · Setmana'};
    if($('#results-title'))$('#results-title').textContent=labels[tab];
    if($('#results-note'))$('#results-note').textContent=`${selected.length} partits · Agenda FECAPA (setmana actual). Els marcadors s’actualitzen des d’En directe quan coincideix el partit.`;
    if($('#open-fecapa'))$('#open-fecapa').onclick=()=>window.open(AGENDA,'_blank','noopener');
  }
  let scheduled=false;
  function draw(){
    scheduled=false;const store=read();const list=store.agenda?.rows||[];
    if(!list.length)return; // No suprimir les pantalles antigues fins tenir Agenda.
    const week=byWeek(list).map(r=>resolved(r,store));
    drawHome(week);
    drawList(activeTab(),week);
    const last=[store.agenda?.capturedAt,store.scoreUpdates?.capturedAt,store.live?.capturedAt].filter(Boolean).sort().pop();
    if($('#data-label'))$('#data-label').textContent='Agenda + En directe · Safari';
    if($('#data-age')&&last)$('#data-age').textContent='Última lectura: '+timestamp(last);
    if($('#total-count'))$('#total-count').textContent=week.length+' partits setmana';
  }
  function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(draw)}
  function saveJson(event){
    event.preventDefault();event.stopImmediatePropagation();
    const payload={version:3,publishedAt:new Date().toISOString(),data:read()};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const a=el('a');a.href=url;a.download='zonaok-data.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);
  }
  async function mergePublished(){
    try{
      const res=await fetch('zonaok-data.json?t='+Date.now(),{cache:'no-store'});if(!res.ok)return;
      const p=await res.json();if(p.version!==3||!p.data||typeof p.data!=='object')return;
      const store=read();
      for(const kind of ['agenda','scoreUpdates']){
        const entry=p.data[kind];if(!entry||!Array.isArray(entry.rows)||entry.rows.length>2000)continue;
        const curr=store[kind]||{};
        store[kind]={rows:mergeRows(curr.rows||[],entry.rows),capturedAt:[curr.capturedAt,entry.capturedAt].filter(Boolean).sort().pop()};
      }
      write(store);schedule();
    }catch(_){/* Desconnectat: es conserva la còpia local */}
  }
  function setup(){
    for(const selector of ['#home-cards','#results-list','#import-summary']){
      const e=$(selector);if(e)new MutationObserver(schedule).observe(e,{childList:true,subtree:true});
    }
    const exportButton=$('#export-shared');if(exportButton)exportButton.addEventListener('click',saveJson,true);
    const reload=$('#reload-shared');if(reload)reload.addEventListener('click',e=>{
      e.preventDefault();e.stopImmediatePropagation();mergePublished().then(()=>{draw();location.reload()});
    },true);
    if(importMessage){
      setTimeout(()=>{
        const list=$('#import-summary');
        if(list){const notice=el('p','helper zok-v5-notice',importMessage);list.prepend(notice);}
        const toast=$('#toast');
        if(toast){toast.textContent=importMessage;toast.classList.add('visible');setTimeout(()=>toast.classList.remove('visible'),6500);}
      },550);
    }
    const style=el('style');style.textContent=`
      /* Prioritat absoluta al club, fins i tot quan la categoria es juvenil. */
      .match.zok-v5-barca{--accent:#8d2446!important;--tint:#eed0da!important}
      .match.zok-v5-infantil{--accent:#245bb0!important;--tint:#d9e8ff!important}
      .match.zok-v5-juvenil{--accent:#bc9214!important;--tint:#fff0b4!important}
      .match.zok-v5-neutral{--accent:#4c6680;--tint:#e5edf4}
      #results-list .match.zok-v5{max-width:100%;margin:0}
      #results-list .match.zok-v5 .match-date[data-zok-categoria]::after {content:attr(data-zok-categoria)}
      .zok-v5-notice{padding:7px 10px;border-radius:9px;background:#254968;color:#fff}
    `;document.head.append(style);
    schedule();setTimeout(mergePublished,450);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();
