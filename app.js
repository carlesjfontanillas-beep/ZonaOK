/* ZonaOK \u2014 interf\u00EDcie independent. Sense API, servidor ni peticions a fonts alienes. */
'use strict';
(()=>{
const BASE='https://www.hoqueipatins.fecapa.cat/';
const LEAGUES={4789:{name:'Alev\u00ED OR 3',short:'Bar\u00E7a Alev\u00ED',team:/^(BAR\u00C7A|BARCA|FC BARCELONA)$/i,color:'pink'},4786:{name:'Infantil OR 10',short:'Sant Celoni Infantil B',team:/^CP SANT CELONI B$/i,color:'blue'},4784:{name:'Juvenil OR 6',short:'Sant Celoni Juvenil B',team:/^CP SANT CELONI B$/i,color:'green'}};
const KEY='ZONAOK_FECAPA_SAFARI_V2',OLD='ZONAOK_FECAPA_SAFARI_V1';
const WEEK_KEY='ZONAOK_SETMANA_ACTIVA_V2';
const $$=s=>document.querySelector(s), mk=(tag,cls,content)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(content!==undefined)e.textContent=content;return e;};
let store=load(), section='home', selectedMonday=restoreMonday(), showSeason=false;
// V19: Inici i clubs tenen filtre SETMANAL; Magí i Ton sempre TEMPORADA.
// La setmana seleccionada no pot modificar el filtre de les dues temporades.
function isSeasonMenu(key){return key==='grupalevi'||key==='grupinfantil';}
function isWeekMenu(key){return key==='home'||key==='barca'||key==='celoni';}
function load(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{}}catch(_){return {}}}
function save(){try{localStorage.setItem(KEY,JSON.stringify(store));return true}catch(e){toast('No es poden desar dades en aquest navegador.');return false}}
function toast(msg){const e=$$('#toast');e.textContent=msg;e.classList.add('visible');clearTimeout(toast.t);toast.t=setTimeout(()=>e.classList.remove('visible'),5200)}
function localDate(d=new Date()){const x=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);return `${x.find(p=>p.type==='year').value}-${x.find(p=>p.type==='month').value}-${x.find(p=>p.type==='day').value}`;}
function mondayISO(){const today=localDate(), d=new Date(`${today}T12:00:00Z`);d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));return d.toISOString().slice(0,10)}
// Navegació global de setmana. Es conserva entre pestanyes i dins la mateixa sessió Safari.
function restoreMonday(){
  try{
    const iso=sessionStorage.getItem(WEEK_KEY);
    if(/^\d{4}-\d{2}-\d{2}$/.test(iso||'')){
      const d=new Date(iso+'T12:00:00Z');
      if(!Number.isNaN(d.valueOf())&&d.getUTCDay()===1&&d.toISOString().slice(0,10)===iso)return iso;
    }
  }catch(_){}
  return mondayISO();
}
function chosenWeek(){return {start:selectedMonday,end:plusDays(selectedMonday,6)};}
function changeWeek(weeks){
  if(!Number.isInteger(weeks)||!weeks)return;
  selectedMonday=plusDays(selectedMonday,7*weeks);
  showSeason=isSeasonMenu(section); // Filtre de temporada independent de selectedMonday.
  try{sessionStorage.setItem(WEEK_KEY,selectedMonday);}catch(_){}
  render();
}
function resetWeek(){
  selectedMonday=mondayISO();
  showSeason=isSeasonMenu(section);
  try{sessionStorage.setItem(WEEK_KEY,selectedMonday);}catch(_){}
  render();
}
function installWeekGestures(){
  const root=document.querySelector('main.app');
  if(!root)return;
  let touch=null;
  const excluded='a,button,input,select,textarea,summary,[contenteditable],.standings-wrap,.zok-week-nav';
  root.addEventListener('touchstart',event=>{
    touch=null;
    if(event.touches.length!==1||document.querySelector('dialog[open]'))return;
    if(!isWeekMenu(section))return;
    const target=event.target;
    if(target?.closest?.(excluded))return;
    // Les targetes de partit (role=button) admeten lliscament. La resta de controls, no.
    const interactive=target?.closest?.('[role="button"]');
    if(interactive&&!interactive.classList.contains('match'))return;
    const t=event.touches[0];
    // Els extrems de Safari estan reservats als gestos de navegació del navegador.
    if(t.clientX<22||t.clientX>window.innerWidth-22)return;
    touch={x:t.clientX,y:t.clientY,at:Date.now()};
  },{passive:true});
  root.addEventListener('touchcancel',()=>{touch=null;},{passive:true});
  root.addEventListener('touchend',event=>{
    if(!touch||event.changedTouches.length!==1)return;
    const t=event.changedTouches[0],dx=t.clientX-touch.x,dy=t.clientY-touch.y;
    const elapsed=Date.now()-touch.at;
    touch=null;
    // No confondre el desplaçament vertical o un toc amb un canvi de setmana.
    if(elapsed>1000||Math.abs(dx)<65||Math.abs(dx)<Math.abs(dy)*1.4)return;
    // Esquerra = setmana SEGÜENT; dreta = setmana ANTERIOR.
    event.preventDefault(); // Evita que el lliscament també obri el modal d'acta.
    changeWeek(dx<0?1:-1);
  },{passive:false});
}

function plusDays(s,n){const d=new Date(s+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)}
function niceDate(iso){if(!/^\d{4}-\d{2}-\d{2}$/.test(iso||''))return 'Data no confirmada';return new Intl.DateTimeFormat('ca-ES',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(iso+'T12:00:00Z'));}
function calendarUrl(id,view='calendar'){return `${BASE}?liga=${id}&vista=${view}`}
// FITXES FECAPA — obrir sobre ZonaOK sense perdre la pantalla ni la setmana.
// L'ID de partit només es considera fiable quan ve de la importació oficial.
function scorePresent(r){return r.homeScore!==null&&r.homeScore!==undefined&&r.awayScore!==null&&r.awayScore!==undefined;}
function numericId(value){const v=String(value??'').trim();return /^\d{3,10}$/.test(v)?v:'';}
function officialFecapaURL(raw){
  try{const u=new URL(String(raw||''),BASE);return u.origin===new URL(BASE).origin&&u.protocol==='https:'?u.href:'';}
  catch(_){return '';}
}
function matchLeagueId(r,id){
  for(const v of [r?.league,r?.leagueId,r?.liga,r?.competitionId]){const known=numericId(v);if(known)return known;}
  if(Object.hasOwn(LEAGUES,String(id)))return String(id);
  const name=normalize(r?.competition);
  if(/(?:^| )ALEVI OR 0?3(?: |$)/.test(name))return '4789';
  if(/(?:^| )INFANTIL OR 0?10(?: |$)/.test(name))return '4786';
  if(/(?:^| )JUVENIL OR 0?6(?: |$)/.test(name))return '4784';
  return '';
}
function matchOfficialLink(league,match){
  return `${BASE}?liga=${encodeURIComponent(league)}&vista=calendar&partido=${encodeURIComponent(match)}`;
}
function matchTeamKey(name){
  const v=normalize(name);
  if(['BAR','BARCA','FC BARCELONA','F C BARCELONA','FCBETERANS','FCBETRANS'].includes(v))return 'BARCA';
  return v.replace(/^(?:CP|C P|CLUB PATI)\s+/,'');
}
function exactActaLink(r,id){
  const fromImport=officialFecapaURL(r?.actaUrl);
  if(fromImport){
    const u=new URL(fromImport);
    if(numericId(u.searchParams.get('partido'))||/acta|fecapa_gr_/i.test(u.pathname))return fromImport;
  }
  const league=matchLeagueId(r,id),match=numericId(r?.id);
  return league&&match?matchOfficialLink(league,match):'';
}
function resolveActaLink(r,id){
  const direct=exactActaLink(r,id);
  if(direct)return {url:direct,exact:true,method:'Enllaç del partit'};
  const league=matchLeagueId(r,id);
  const official=store.actaIndex?.[league]?.rows||[];
  const stats={league,imported:official.length,sameDay:0,withBothTeams:0};
  const same=(x,y)=>matchTeamKey(x)===matchTeamKey(y);
  const unique=values=>[...new Set(values)];
  const exact=[],byDay=[];
  const favSide=(name)=>{
    const n=matchTeamKey(name);
    if(n==='BARCA')return 'BARCA';
    if(/^SANT CELONI(?: [AB])?$/.test(n))return n;
    return '';
  };
  for(const other of official){
    if(String(other.iso)!==String(r.iso))continue;
    const idp=numericId(other.id);if(!idp)continue;
    stats.sameDay++;
    const url=matchOfficialLink(league,idp);
    if(same(other.home,r.home)&&same(other.away,r.away)){
      stats.withBothTeams++;exact.push(url);
    }
    // No dependre d'un nom patrocinat exacte: només es pot usar un únic
    // partit de la mateixa lliga i el mateix dia, amb el favorit al mateix costat.
    if((favSide(other.home)&&favSide(other.home)===favSide(r.home))||
       (favSide(other.away)&&favSide(other.away)===favSide(r.away)))byDay.push(url);
  }
  const matched=unique(exact);
  if(matched.length===1)return {url:matched[0],exact:true,method:'Data i equips'};
  // Davant de més d'un ID contradictori, no triem per hora ni marcador.
  if(matched.length>1)return {url:league?calendarUrl(league):BASE,exact:false,stats};
  if(unique(byDay).length===1 && stats.sameDay===1)return {url:byDay[0],exact:true,method:'Únic partit del grup aquell dia'};
  // Els calendaris de Magí/Ton poden portar un enllaç directe importat.
  const possible=new Set();
  for(const group of ['4789','4786','4784']){
    if(league&&group!==league)continue;
    for(const rows of [allRows(group),store.seasons?.[group]?.rows||[]])for(const other of rows){
      if(other.iso!==r.iso||!same(other.home,r.home)||!same(other.away,r.away))continue;
      const known=exactActaLink(other,group);
      if(known)possible.add(known);
    }
  }
  if(possible.size===1)return {url:[...possible][0],exact:true,method:'Calendari oficial'};
  return {url:league?calendarUrl(league):BASE,exact:false,stats};
}
let actaDialog=null,actaFrame=null,actaTitle=null,actaHint=null,actaExternal=null,actaPosition=null;
function setupActaDialog(){
  const style=mk('style');style.textContent=`
  .zok-acta-dialog:not([open]){display:none}
  .zok-acta-dialog[open]{display:flex;flex-direction:column}
  .zok-acta-dialog{position:fixed;margin:auto;inset:0;box-sizing:border-box;width:min(98vw,1050px);max-width:98vw;height:min(93vh,940px);height:min(93dvh,940px);max-height:93vh;max-height:93dvh;padding:0;overflow:hidden;border:1px solid #34536d;border-radius:17px;background:#f3f6fa;color:#082238;box-shadow:0 20px 70px #000a}
  .zok-acta-dialog::backdrop{background:#03172bd9}
  .zok-acta-header{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#061f38;color:#fff;padding:12px 14px;min-height:48px}
  .zok-acta-header strong{font-size:1rem;line-height:1.25}
  .zok-acta-close{flex:0 0 auto;border:1px solid #b5c9d3;border-radius:10px;background:#244860;color:#fff;font-size:1.5rem;font-weight:800;line-height:1;padding:6px 11px;cursor:pointer}
  .zok-acta-subtitle{background:#e3eaf0;padding:8px 14px;font-weight:700;font-size:.9rem;line-height:1.3}
  .zok-acta-iframe{display:block;flex:1 1 auto;min-height:0;width:100%;border:0;background:#fff}
  .zok-acta-footer{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;background:#e3eaf0;padding:10px 12px}
  .zok-acta-hint{flex:1 1 200px;margin:0;font-size:.78rem;line-height:1.3;color:#234259}
  .zok-acta-external{display:inline-flex;align-items:center;justify-content:center;border-radius:10px;padding:10px 12px;background:#8f224c;color:#fff!important;text-decoration:none;font-weight:700;font-size:.85rem;white-space:nowrap}
  .match.zok-acta-available{cursor:pointer}
  .match.zok-acta-available:focus-visible{outline:3px solid #ffc66e;outline-offset:3px}
  .match.zok-acta-available .zok-acta-action{background:#8f224c;color:#fff;border:0;border-radius:8px;cursor:pointer;font-weight:700}
  @media(max-width:600px){.zok-acta-dialog{width:96vw;max-width:96vw;height:94dvh;max-height:94dvh;border:1px solid #34536d;border-radius:15px}.zok-acta-footer{padding-bottom:max(10px,env(safe-area-inset-bottom))}}
  `;document.head.append(style);
  actaDialog=mk('dialog','zok-acta-dialog');actaDialog.setAttribute('aria-label','Fitxa oficial del partit a FECAPA');
  const header=mk('div','zok-acta-header');header.append(mk('strong','','FITXA DEL PARTIT · FECAPA'));
  const close=mk('button','zok-acta-close','×');close.type='button';close.setAttribute('aria-label','Tancar la fitxa i tornar a ZonaOK');close.onclick=()=>actaDialog.close();header.append(close);
  actaTitle=mk('div','zok-acta-subtitle');
  actaFrame=mk('iframe','zok-acta-iframe');actaFrame.title='Fitxa oficial de FECAPA';actaFrame.setAttribute('loading','eager');actaFrame.setAttribute('sandbox','allow-forms allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox');
  const footer=mk('div','zok-acta-footer');actaHint=mk('p','zok-acta-hint');
  actaExternal=mk('a','zok-acta-external','Obrir a FECAPA ↗');actaExternal.target='_blank';actaExternal.rel='noopener';footer.append(actaHint,actaExternal);
  actaDialog.append(header,actaTitle,actaFrame,footer);document.body.append(actaDialog);
  actaDialog.addEventListener('click',e=>{if(e.target===actaDialog)actaDialog.close();});
  actaDialog.addEventListener('close',()=>{
    actaFrame.removeAttribute('src');
    if(actaPosition){const p=actaPosition;actaPosition=null;requestAnimationFrame(()=>window.scrollTo(p.x,p.y));}
  });
}
function openActaDialog(r,id){
  if(!scorePresent(r))return;
  // La importacio de JSON i el mòdul de sincronització poden escriure al mateix magatzem.
  store=load();
  if(!actaDialog)setupActaDialog();
  const link=resolveActaLink(r,id);
  actaPosition={x:window.scrollX,y:window.scrollY};
  actaTitle.textContent=`${r.home} · ${r.homeScore} - ${r.awayScore} · ${r.away} · ${niceDate(r.iso)}`;
  actaHint.textContent=link.exact
    ?'Si FECAPA no permet veure l’acta dins la finestra, prem «Obrir a FECAPA».'
    :'No s\u2019ha pogut relacionar una acta de manera inequívoca. IDs de la lliga: '+(link.stats?.imported||0)+'; mateix dia: '+(link.stats?.sameDay||0)+'. El calendari oficial està disponible al botó.';
  actaExternal.href=link.url;
  actaExternal.textContent=link.exact?'Obrir a FECAPA ↗':'Veure calendari ↗';
  actaFrame.hidden=!link.exact;
  actaFrame.style.display=link.exact?'':'none';
  actaDialog.showModal();
  if(link.exact)actaFrame.src=link.url;
  else actaFrame.removeAttribute('src');
}
// API mínima perquè zonaok-sync-v5.js obri exactament la mateixa finestra.
window.ZonaOKActes={open:openActaDialog,resolve:resolveActaLink};

function weekText(){
  const {start,end}=chosenWeek();
  const label=niceDate(start)+' \u2014 '+niceDate(end);
  const sm=start.slice(5,7),em=end.slice(5,7);
  const monthName=iso=>new Intl.DateTimeFormat('ca-ES',{month:'short',timeZone:'UTC'}).format(new Date(iso+'T12:00:00Z'));
  const shortLabel=sm===em?`${Number(start.slice(8))}–${Number(end.slice(8))} ${monthName(start)}`:`${Number(start.slice(8))} ${monthName(start)} – ${Number(end.slice(8))} ${monthName(end)}`;
  $$('#week').textContent=shortLabel;
  $$('#week').title=label;
  const resultLabel=$$('#results-week');
  if(resultLabel){
    const fullSeason=section==='grupalevi'||section==='grupinfantil';
    resultLabel.hidden=section==='classificacions'||fullSeason;
    resultLabel.textContent=fullSeason?'':'Setmana: '+label;
  }
  const today=$$('#week-today');if(today)today.disabled=start===mondayISO()&&!showSeason;
}

function sameTeam(a,b){return normalize(a)===normalize(b)}
function normalize(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Z0-9]/gi,' ').replace(/\s+/g,' ').trim().toUpperCase()}
function clubOf(name){const n=normalize(name);if(/\b(BARCA|FC BARCELONA|FCBETERANS|FCBETRANS)\b/.test(n))return 'barca';if(/\b(?:CP )?SANT CELONI(?: [AB])?\b/.test(n))return 'celoni';return ''}
function matchFav(r,id){const club=id==='4789'?'barca':'celoni';return clubOf(r.home)===club||clubOf(r.away)===club}
function allRows(id){return Array.isArray(store[id]?.rows)?store[id].rows:[]}
function liveRows(){return allRows('live')}
function agendaRows(){return allRows('agenda')}
function clubRows(){const rows=new Map(agendaRows().map(r=>[[r.iso,r.time,normalize(r.home),normalize(r.away)].join('|'),r]));for(const r of liveRows()){const k=[r.iso,r.time,normalize(r.home),normalize(r.away)].join('|'),old=rows.get(k);rows.set(k,old?{...old,...r,venue:r.venue||old.venue,id:r.id||old.id,actaUrl:r.actaUrl||old.actaUrl,league:r.league||old.league}:r)}return [...rows.values()]}

function render(){weekText();renderSources();renderHome();if(section!=='home')renderSection(section)}
function renderSources(){const list=$$('#import-summary');list.replaceChildren();let total=liveRows().length+(store.agenda?.rows?.length||0),latest=[store.live?.capturedAt,store.agenda?.capturedAt].filter(Boolean).sort().pop()||'';if(store.agenda){const r=mk('div','source-row');r.append(mk('strong','','Agenda \u00B7 Temporada '+(store.agenda.season||'')),mk('small','',agendaRows().length+' partits \u00B7 Bar\u00E7a '+(store.agenda.counts?.barca??'\u2014')+' \u00B7 Sant Celoni '+(store.agenda.counts?.celoni??'\u2014')+' \u00B7 '+formatTimestamp(store.agenda.capturedAt)));list.append(r);}if(store.live){const r=mk('div','source-row');r.append(mk('strong','','En directe \u00B7 Bar\u00E7a i Sant Celoni'),mk('small','',liveRows().length+' partits \u00B7 '+formatTimestamp(store.live.capturedAt)));list.append(r);}for(const id of ['4789','4786','4784']){const item=store[id],season=store.seasons?.[id];const count=allRows(id).length+(season?.rows?.length||0);total+=count;const r=mk('div','source-row');const a=mk('div');a.append(mk('strong','',LEAGUES[id].name));a.append(mk('small','',season?.capturedAt?'Temporada '+(season.season||'')+': '+formatTimestamp(season.capturedAt):(item?.standingsAt?'Classificaci\u00F3: '+formatTimestamp(item.standingsAt):(item?.capturedAt?'Calendari: '+formatTimestamp(item.capturedAt):'Encara no importat'))));const vista=id==='4789'?partitsTemporadaJugador('grupalevi').rows.length:id==='4786'?partitsTemporadaJugador('grupinfantil').rows.length:null;
const resumPartits=vista===null?count+' partits':vista+' partits (agenda + lliga)';
r.append(a,mk('span','',resumPartits+' \u00B7 '+(item?.standings?.length||0)+' equips'));list.append(r);for(const stamp of [season?.capturedAt,item?.capturedAt,item?.standingsAt])if(stamp&&(!latest||stamp>latest))latest=stamp;}if(store.actaIndex){const labels=Object.entries({4789:'Magí',4786:'Ton',4784:'Juvenil'}).map(([id,name])=>{const n=store.actaIndex[id]?.rows?.length||0;return n?name+' '+n+' IDs':''}).filter(Boolean);if(labels.length){const info=mk('div','source-row');info.append(mk('strong','','Actes oficials FECAPA'),mk('small','',labels.join(' · ')+' · Identificadors importats'));list.append(info);}}let legacy=0;try{const old=JSON.parse(localStorage.getItem(OLD)||'{}');for(const id of ['4789','4786','4784'])legacy+=(old[id]?.rows||[]).length}catch(_){}if(legacy){const msg=mk('div','source-row');const label=mk('div');label.append(mk('strong','','Importaci\u00F3 antiga conservada'));label.append(mk('small','','Hi ha '+legacy+' files de la prova anterior. No s\u2019eliminen, per\u00F2 cal repetir la drecera nova per mostrar els partits separats.'));msg.append(label);list.append(msg);}$$('#total-count').textContent=total+' files';$$('#data-age').textContent=latest?'\u00DAltima importaci\u00F3: '+formatTimestamp(latest):'Sense dades noves importades'}
function formatTimestamp(iso){try{return new Intl.DateTimeFormat('ca-ES',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Madrid'}).format(new Date(iso))}catch(_){return 'Data desconeguda'}}
function safeImage(src){try{const u=new URL(src);return u.protocol==='https:'&&(/(^|\.)hoqueipatins\.fecapa\.cat$/i.test(u.hostname)||(u.hostname==='sidgad.cloud'&&u.pathname.startsWith('/fecapa/images/logos_clubes/')))?u.href:''}catch(_){return ''}}
function dateStatus(r){const now=localDate();if(r.status)return r.status+' \u00B7 lectura Safari';if(r.homeScore!==null&&r.awayScore!==null)return 'Marcador FECAPA';return r.iso>now?'Programat':'Sense resultat confirmat'}
function createCard(r,id){const c=mk('article','match '+(LEAGUES[id]?.color||'gray'));
const top=mk('div','match-top'),pill=mk('span','pill',r.competition||LEAGUES[id]?.name||'FECAPA'),tag=mk('span','tag',dateStatus(r));top.append(pill,tag);c.append(top);
const dt=mk('div','match-date');dt.append(mk('strong','',r.time||'Hora pendent'),mk('small','',niceDate(r.iso)));c.append(dt);
const teams=mk('div','teams');const side=(name,logo)=>{name=name==='BAR'?'BAR\u00C7A':name==='CPSC'?'CP SANT CELONI':name;const d=mk('div','side'),crest=mk('div','crest');if(safeImage(logo)){const img=mk('img');img.src=safeImage(logo);img.alt='Escut de '+name;img.loading='lazy';img.onerror=()=>{crest.replaceChildren(mk('span','crest-fallback','\u{1F3D2}'))};crest.append(img)}else crest.append(mk('span','crest-fallback',name?name.trim().charAt(0).toUpperCase():'\u{1F3D2}'));d.append(crest,mk('strong','',name||'Equip no identificat'));return d};
const mid=mk('div','middle');mid.append(mk('div','score',r.homeScore!==null&&r.awayScore!==null?`${r.homeScore} : ${r.awayScore}`:'\u2014 : \u2014'));mid.append(mk('small','score-note',r.homeScore!==null?'Resultat':'Pendent'));if(scorePresent(r)){const actaMini=mk('button','zok-acta-chip','⌕ Acta');actaMini.type='button';actaMini.onclick=e=>{e.stopPropagation();openActaDialog(r,id)};mid.append(actaMini);}teams.append(side(r.home,r.homeLogo),mid,side(r.away,r.awayLogo));c.append(teams);
const loc=mk('div','venue');loc.append(mk('strong','','\u{1F4CD} '+(r.venue||'Pista pendent de verificar a FECAPA')));if(!r.venue)loc.append(mk('div','', 'No s\u2019ha llegit cap pista per a aquest partit'));c.append(loc);
const buttons=mk('div','match-actions');const cal=mk('button','','\u25A6 Calendari');cal.disabled=!r.iso||!r.time;cal.onclick=()=>exportICS(r);const maps=mk('a','light',r.venue?'\u2197 Google Maps':'\u2197 Cercar pista');maps.href=r.venue?'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(r.venue):BASE+'ag/';maps.target='_blank';maps.rel='noopener';const source=mk('a','light','FECAPA \u2197');source.href=exactActaLink(r,id)||(id==='live'?BASE:calendarUrl(id));source.target='_blank';source.rel='noopener';buttons.append(cal,maps,source);if(scorePresent(r)){const acta=mk('button','zok-acta-action','\u2315 Acta');acta.type='button';acta.onclick=()=>openActaDialog(r,id);acta.setAttribute('aria-label','Obrir l\u2019acta del partit sense sortir de ZonaOK');buttons.append(acta)}c.append(buttons);if(r.capturedAt)c.append(mk('small','helper','Lectura: '+formatTimestamp(r.capturedAt)));if(scorePresent(r)){c.classList.add('zok-acta-available');c.tabIndex=0;c.setAttribute('role','button');c.setAttribute('aria-label','Obrir fitxa del partit '+r.home+' - '+r.away);c.addEventListener('click',e=>{if(e.target.closest?.('button,a,input,select,textarea'))return;openActaDialog(r,id)});c.addEventListener('keydown',e=>{if(e.target!==c||(e.key!=='Enter'&&e.key!==' '))return;e.preventDefault();openActaDialog(r,id)})}return c}
function missing(id){const out=mk('div','empty');out.append(mk('strong','',LEAGUES[id].short+' \u00B7 Dades pendents'));out.append(mk('div','', 'Sense partit identificat d\u2019aquest equip aquesta setmana. En directe no sempre distingeix el grup ni la lletra A/B. Consulta la llista del club o el calendari oficial.'));const a=mk('a','','Obrir calendari FECAPA \u2197');a.href=calendarUrl(id);a.target='_blank';a.rel='noopener';out.append(a);return out}
function favoriteState(){try{return JSON.parse(localStorage.getItem('ZONAOK_FAVORITS_V1')||'{}')||{}}catch(_){return {}}}
function favoriteTeamFromId(id,state){if(typeof id!=='string'||!id.toUpperCase().startsWith('TEAM|'))return null;const parts=id.split('|');if(parts.length<3)return null;return {team:normalize(parts[1]),category:normalize(parts.slice(2).join('|')),name:String(state.teamNames?.[id]||'').trim()}}
function favoriteTeamMatches(row,fav){return Boolean(row&&fav&&normalize(row.competition||row.category||'')===fav.category&&[row.home,row.away].some(team=>normalize(team)===fav.team))}
function favoriteClubMatches(row,name){if(!row||!name)return false;const club=normalize(name),slug=club==='BARCA'?'barca':club==='CP SANT CELONI'?'celoni':'';return [row.home,row.away].some((team,index)=>{const teamSlug=index===0?row.homeClub:row.awayClub;return slug?teamSlug===slug||clubOf(team)===slug:normalize(team)===club||normalize(team).startsWith(club+' ')})}
function renderHome(){const box=$$('#home-cards');box.replaceChildren();const state=favoriteState();const teams=(Array.isArray(state.teams)?state.teams:[]).map((id,index)=>({id,index,favorite:favoriteTeamFromId(id,state)})).filter(item=>item.favorite);const clubs=(Array.isArray(state.clubs)?state.clubs:[]).map((name,index)=>({name,index})).filter(item=>typeof item.name==='string'&&item.name.trim());const {start,end}=chosenWeek();const rows=clubRows().filter(row=>row.iso>=start&&row.iso<=end&&(teams.length?teams.some(item=>favoriteTeamMatches(row,item.favorite)):clubs.some(item=>favoriteClubMatches(row,item.name)))).sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time));for(const row of rows)box.append(createCard(row,'live'));let pending=0;const missingFavorites=teams.length?teams.filter(item=>!rows.some(row=>favoriteTeamMatches(row,item.favorite))).map(item=>({label:(item.favorite.name||item.favorite.team)+' · '+item.favorite.category,key:'favteam'+(item.index+1)}):clubs.filter(item=>!rows.some(row=>favoriteClubMatches(row,item.name))).map(item=>({label:item.name,key:'favclub'+(item.index+1)}));for(const item of missingFavorites){const card=mk('div','empty zok-favorite-pending');card.append(mk('strong','',item.label+' · Resultats pendents'),mk('div','','No s’ha identificat cap partit importat d’aquest favorit aquesta setmana.'));const button=mk('button','secondary','Resultats');button.type='button';button.addEventListener('click',()=>selectSection(item.key));card.append(button);box.append(card);pending++;}if(!teams.length&&!clubs.length){box.classList.add('zok-home-no-favorites');const help=mk('article','zok-favorite-empty-card');help.append(mk('h3','','Encara no has triat cap favorit'),mk('p','','Tria clubs o equips per veure aquí els partits de la setmana.'));const link=mk('a','','Configura Favorits');link.href='favorits.html';help.append(link);box.append(help);}else box.classList.remove('zok-home-no-favorites');if(!rows.length&&!pending&& (teams.length||clubs.length))box.append(mk('div','empty','No hi ha partits importats dels favorits aquesta setmana.'));$$('#home-count').textContent=rows.length+' partits';}
function emptyResults(message,ids=[]){const v=mk('div','empty');v.append(mk('div','',message));for(const id of ids){const a=mk('a','','Obrir '+LEAGUES[id].name+' \u2197');a.href=calendarUrl(id);a.target='_blank';a.rel='noopener';v.append(mk('div','', ' '));v.append(a)}$$('#results-list').append(v)}
const SECTIONS={celoni:{name:'CP Sant Celoni \u00B7 Setmana',source:BASE,ids:['4786','4784'],msg:'Partits del CP Sant Celoni presents al llistat En directe. La llista pot ser parcial; FECAPA no hi distingeix sempre A/B ni el grup.'},barca:{name:'Bar\u00E7a \u00B7 Setmana',source:BASE,ids:['4789'],msg:'Partits del Bar\u00E7a presents al llistat En directe. Mostrem la categoria publicada i l\u2019hora de la lectura; la llista pot ser parcial.'},classificacions:{name:'Classificacions \u00B7 3 grups',source:calendarUrl('4789','clasificaciones'),ids:['4789','4786','4784'],msg:'Les classificacions nom\u00E9s apareixen despr\u00E9s d\u2019importar les taules oficials de FECAPA des de Safari.'},grupalevi:{name:'Alev\u00ED OR 3',source:calendarUrl('4789'),ids:['4789'],msg:'Tots els partits de la temporada del Bar\u00E7a a Alev\u00ED OR 3, amb els marcadors publicats per FECAPA.'},grupinfantil:{name:'Infantil OR 10',source:calendarUrl('4786'),ids:['4786'],msg:'Tots els partits de la temporada del Sant Celoni B a Infantil OR 10, amb els marcadors publicats per FECAPA.'}};
/* MAGI i TON - mostrar partits reals de l'AGENDA importada, no dependre
   d'una segona importacio per lliga. La lectura de tota la temporada existeix
   a store.agenda.rows; les entrades store[4789/4786].rows poden estar buides.
   Les etiquetes FECAPA poden tenir accents, sigles o text addicional. */
function temporadaActual(){
  const avui=localDate();
  const any=Number(avui.slice(0,4))-(Number(avui.slice(5,7))<7?1:0);
  return {inici:any+'-07-01',fi:(any+1)+'-06-30',nom:any+'/'+(any+1)};
}
function competicioJugador(r,key){
  const n=normalize(r?.competition||'');
  const patr=key==='grupalevi'?/(?:^|\s)ALEVI\s+OR\s+0?3(?:\s|$)/:/(?:^|\s)INFANTIL\s+OR\s+0?10(?:\s|$)/;
  return patr.test(n);
}
function equipJugador(nom,key){
  const n=normalize(nom);
  if(key==='grupalevi')return clubOf(nom)==='barca';
  // La categoria Infantil OR 10 ha de ser el SANT CELONI B, no l'A.
  return /^(?:(?:CP|C P|CLUB PATI)\s+)?SANT CELONI\s+B$/.test(n);
}
function partitsTemporadaJugador(key){
  const id=key==='grupalevi'?'4789':'4786',grup=LEAGUES[id].name;
  const periode=temporadaActual();
  const valid=(r,fiable)=>r&&r.iso>=periode.inici&&r.iso<=periode.fi&&
    (equipJugador(r.home,key)||equipJugador(r.away,key))&&
    (fiable?(!r.competition||competicioJugador(r,key)):competicioJugador(r,key));
  // En els calendaris de lliga l'identificador 4789/4786 es fiable.
  // A l'agenda general es OBLIGATORI comprovar el nom de la competicio.
  const fonts=[
    {rows:allRows(id),at:store[id]?.capturedAt||'',fiable:true},
    {rows:store.seasons?.[id]?.rows||[],at:store.seasons?.[id]?.capturedAt||'',fiable:true},
    {rows:agendaRows(),at:store.agenda?.capturedAt||'',fiable:false}
  ].sort((a,b)=>String(a.at).localeCompare(String(b.at)));
  const resultat=new Map();
  let nAgendaGrup=0, nAgendaEquip=0, nAgendaAmbdos=0;
  for(const r of agendaRows()){
    if(!r||r.iso<periode.inici||r.iso>periode.fi)continue;
    const cg=competicioJugador(r,key),ce=equipJugador(r.home,key)||equipJugador(r.away,key);
    if(cg)nAgendaGrup++;
    if(ce)nAgendaEquip++;
    if(cg&&ce)nAgendaAmbdos++;
  }
  for(const font of fonts){
    for(const r of font.rows){
      if(!r)continue;
      const p=parseRow(r);
      if(!valid(p,font.fiable))continue;
      // Nomes etiquetar el grup conegut un cop validat el partit.
      p.competition=grup;
      p.capturedAt=String(r.capturedAt||font.at||'');
      const k=[p.iso,normalize(p.home),normalize(p.away),normalize(p.competition)].join('|');
      const old=resultat.get(k);
      if(!old||p.capturedAt>=old.capturedAt)resultat.set(k,{...old,...p,
        homeScore:p.homeScore===null&&old?old.homeScore:p.homeScore,
        awayScore:p.awayScore===null&&old?old.awayScore:p.awayScore,
        venue:p.venue||(old?.venue||''),id:p.id||(old?.id||''),actaUrl:p.actaUrl||(old?.actaUrl||''),league:p.league||(old?.league||id)});
    }
  }
  return {rows:[...resultat.values()].sort((a,b)=>(b.iso+' '+b.time).localeCompare(a.iso+' '+a.time)),
    periode,diagnostic:{agenda:agendaRows().length,grup:nAgendaGrup,equip:nAgendaEquip,ambdos:nAgendaAmbdos}};
}
function mostrarTemporadaJugador(key,box){
  const magi=key==='grupalevi',id=magi?'4789':'4786';
  const {rows:seasonRows,periode,diagnostic}=partitsTemporadaJugador(key);
  // No llegir chosenWeek() aquí: MAGÍ i TON SEMPRE mostren tota la temporada.
  const rows=seasonRows;
  $$('#results-title').textContent=magi?'Mag\u00ED \u00B7 Bar\u00E7a Alev\u00ED OR 3':'Ton \u00B7 CP Sant Celoni B Infantil OR 10';
  $$('#results-note').textContent=rows.length+' partits · '+periode.nom+' · Més recents primer';
  const readAt=store.seasons?.[id]?.capturedAt||store[id]?.capturedAt||store.agenda?.capturedAt||store.live?.capturedAt||'';
  const readNode=$$('#results-read-at');if(readNode){readNode.hidden=!readAt;readNode.textContent=readAt?'Lectura: '+formatTimestamp(readAt):'';}
  if(!rows.length){
    if(seasonRows.length){
      emptyResults('No hi ha dades de temporada disponibles en aquesta còpia.',[id]);
    }else{
      emptyResults('L\u2019agenda general t\u00E9 '+diagnostic.agenda+' partits. D\u2019aquests, '+diagnostic.grup+' s\u00F3n de la competici\u00F3, '+diagnostic.equip+' identifiquen aquest equip i '+diagnostic.ambdos+' coincideixen en totes dues condicions. Revisa els noms d\u2019equip o competici\u00F3 importats.',[id]);
    }
    return;
  }
  for(const r of rows)box.append(createCard(r,id));
}
function renderSection(key){const section=SECTIONS[key];if(!section)return;weekText();const seasonToggle=$$('#season-toggle');if(seasonToggle){seasonToggle.hidden=['classificacions','barca','celoni','grupalevi','grupinfantil'].includes(key);seasonToggle.textContent=showSeason?'Veure setmana':'Tota la temporada';}$$('#results-title').textContent=section.name;$$('#results-eyebrow').textContent='CONSULTA \u00B7 FECAPA';$$('#results-note').textContent=section.msg;$$('#open-fecapa').onclick=()=>window.open(section.source,'_blank','noopener');$$('#ask-section').onclick=()=>ask(key);const box=$$('#results-list');box.replaceChildren();const {start,end}=chosenWeek();if(key==='classificacions'){let any=false;const statLabels={PTS:'Pts',PJ:'PJ',PG:'PG',PE:'PE',PP:'PP',GF:'GF',GC:'GC',DIF:'DIF',SAN:'SAN'};for(const id of section.ids){const rows=store[id]?.standings||[];box.append(mk('h3','',LEAGUES[id].name));if(store[id]?.standingsAt)box.append(mk('small','helper','Lectura: '+formatTimestamp(store[id].standingsAt)));if(!rows.length){emptyResults('Classificaci\u00F3 pendent de lectura des de Safari.',[id]);continue;}any=true;const statKeys=[...new Set(rows.flatMap(r=>Object.keys(r.stats||{})))];const columns=[['pos','Pos.'],['team','Equip'],...statKeys.map(k=>['stats.'+k,statLabels[k]||k]),...(statKeys.length?[]:[['played','PJ'],['gf','GF'],['ga','GC'],['difference','DIF'],['points','Pts']])];for(const [k] of [...columns])if(k.startsWith('stats.')){const raw=k.slice(6);if(rows.every(r=>r.stats?.[raw]===null||r.stats?.[raw]===undefined||r.stats?.[raw]===''))columns.splice(columns.findIndex(c=>c[0]===k),1)}const table=mk('table','standings'),head=mk('tr');for(const [,label] of columns)head.append(mk('th','',label));table.append(head);for(const r of rows){const tr=mk('tr',/BAR\u00C7A|CP SANT CELONI B/i.test(r.team||'')?'highlight':'');for(const [k] of columns){const value=k.startsWith('stats.')?r.stats?.[k.slice(6)]:r[k];tr.append(mk('td','',value??'\u2014'))}table.append(tr)}const wrap=mk('div','standings-wrap');wrap.append(table);box.append(wrap)}if(!any)toast('Importa les classificacions des de Safari.');return;}
if(key==='grupalevi'||key==='grupinfantil'){mostrarTemporadaJugador(key,box);return;}
if(key==='celoni'||key==='barca'){
  const club=key==='celoni'?'celoni':'barca',source=clubRows();
  const rows=source.filter(r=>r.iso>=start&&r.iso<=end&&(clubOf(r.home)===club||clubOf(r.away)===club))
    .sort((a,b)=>showSeason?(b.iso+b.time).localeCompare(a.iso+a.time):(a.iso+a.time).localeCompare(b.iso+b.time));
  const clubName=key==='celoni'?'CP Sant Celoni':'Bar\u00E7a';
  $$('#results-title').textContent=clubName+' \u00B7 Setmana';
  $$('#results-note').textContent=rows.length+' partits del club aquesta setmana.';
  for(const r of rows)box.append(createCard(r,'live'));
  if(!rows.length)emptyResults('Cap partit importat d\u2019aquest club aquesta setmana.');
  return;
}
emptyResults('No hi ha partits disponibles per a aquesta secci\u00F3.',section.ids);}

function selectSection(key){showSeason=isSeasonMenu(key);if(key==='home'){section='home';$$('#results-section').classList.add('hide');$$('#home-cards').scrollIntoView({behavior:'smooth',block:'start'});}else{section=key;$$('#results-section').classList.remove('hide');renderSection(key);$$('#results-section').scrollIntoView({behavior:'smooth',block:'start'});}document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active',b.dataset.tab===key));}
function escapeICS(v){return String(v||'').replace(/\\/g,'\\\\').replace(/\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;')}
function exportICS(r){if(!r.iso||!r.time)return toast('No hi ha data i hora confirmades');const local=(r.iso.replace(/-/g,'')+'T'+r.time.replace(':','')+'00');const h=+r.time.slice(0,2);const end=(h+2)%24;const next=end<h?plusDays(r.iso,1).replace(/-/g,''):r.iso.replace(/-/g,'');const finish=next+'T'+String(end).padStart(2,'0')+r.time.slice(3,5)+'00';const event=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//ZonaOK//FECAPA//CA','BEGIN:VEVENT','UID:zonaok-'+(r.id||Date.now())+'@zonaok.local','DTSTAMP:'+new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z'),'DTSTART;TZID=Europe/Madrid:'+local,'DTEND;TZID=Europe/Madrid:'+finish,'SUMMARY:'+escapeICS(r.home+' - '+r.away),'LOCATION:'+escapeICS(r.venue||''),'DESCRIPTION:'+escapeICS('Consulta la font FECAPA. Durada provisional de 2 hores.'),'END:VEVENT','END:VCALENDAR'].join('\r\n');const url=URL.createObjectURL(new Blob([event],{type:'text/calendar;charset=utf-8'}));const a=mk('a');a.href=url;a.download='ZonaOK-partit.ics';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);}
function prompts(key){
  const pref='Respon en catal\u00E0. Consulta ARA \u00FAnicament la web oficial https://www.hoqueipatins.fecapa.cat/ i https://www.hoqueipatins.fecapa.cat/ag/ per a pistes i resultats. No utilitzis altres fonts. No inventis partits, hores, pistes, escuts, marcadors ni classificacions. Si la lectura din\u00E0mica no \u00E9s possible, indica clarament que no est\u00E0 verificat. Mostra targetes compactes iPhone amb horaris Europe/Madrid, marcadors, escuts verificats, Google Maps i afegir al calendari quan es conegui la informaci\u00F3. ';
  const {start,end}=chosenWeek();
  const periode='Del '+start+' al '+end+' (hora Europe/Madrid). ';
  const atemporada=showSeason?'Durant tota la temporada 2026/27. ':periode;
  return pref+({
    home:periode+'Consulta els partits de Bar\u00E7a Alev\u00ED OR 3 lliga 4789, CP Sant Celoni B Infantil OR 10 lliga 4786 i CP Sant Celoni B Juvenil OR 6 lliga 4784.',
    celoni:atemporada+'Busca tots els partits de TOTS els equips del CP Sant Celoni en totes les competicions oficials, incloent-hi resultats.',
    barca:atemporada+'Busca tots els partits de TOTS els equips del FC Barcelona hoquei patins en totes les competicions oficials, incloent-hi resultats.',
    classificacions:'Consulta les taules completes de classificaci\u00F3 de les lligues 4789, 4786 i 4784, destacant Bar\u00E7a Alev\u00ED i CP Sant Celoni B Infantil i Juvenil.',
    grupalevi:atemporada+'Consulta els partits i resultats del Bar\u00E7a de la lliga 4789 Alev\u00ED OR 3, ordena m\u00E9s recent a dalt.',
    grupinfantil:atemporada+'Consulta els partits i resultats del CP Sant Celoni B de la lliga 4786 Infantil OR 10, ordena m\u00E9s recent a dalt.'
  }[key]||'');
}
function ask(key){const q=prompts(key);navigator.clipboard?.writeText(q).catch(()=>{});window.open('https://chatgpt.com/?q='+encodeURIComponent(q),'_blank','noopener');toast('S\u2019obre ChatGPT. Si no apareix la pregunta, ja s\u2019ha intentat copiar per enganxar-la.');}
function legacyImportHash(payloadOverride){const h=location.hash.slice(1);if(!payloadOverride&&!h.startsWith('fecapa='))return;try{history.replaceState(null,'',location.pathname+location.search);const payload=payloadOverride||JSON.parse(decodeURIComponent(h.slice(7)));if(!payload||payload.source!=='FECAPA-SAFARI')throw Error('Font no acceptada');const rows=Array.isArray(payload.rows)?payload.rows:[];
  if(payload.kind==='match-ids-v1'){
    const league=numericId(payload.league);
    if(!league||!Object.hasOwn(LEAGUES,league))throw Error('Lliga no reconeguda per ZonaOK');
    if(!rows.length||rows.length>250)throw Error('Cap ID d’acta o massa files');
    const incoming=[];
    for(const a of rows){
      if(!Array.isArray(a)||a.length<5)throw Error('Fila d’identificador incompleta');
      const [iso,time,home,away,idp]=a;
      if(!/^20\d{2}-\d{2}-\d{2}$/.test(String(iso))||!/^\d{2}:\d{2}$/.test(String(time))||!String(home).trim()||!String(away).trim()||!numericId(idp))throw Error('Data, equips o ID de partit incorrectes');
      incoming.push({iso:String(iso),time:String(time),home:String(home).slice(0,120),away:String(away).slice(0,120),id:String(idp),league});
    }
    store.actaIndex=store.actaIndex||{};
    const old=store.actaIndex[league]?.rows||[];
    const indexKey=r=>[r.iso,r.time,matchTeamKey(r.home),matchTeamKey(r.away)].join('|');
    const merged=new Map(old.map(r=>[indexKey(r),r]));
    for(const r of incoming){const key=indexKey(r),prev=merged.get(key);if(prev&&prev.id!==r.id&&incoming.filter(x=>indexKey(x)===key).length>1)throw Error('Dos IDs diferents per al mateix partit');merged.set(key,r);}
    store.actaIndex[league]={rows:[...merged.values()],capturedAt:String(payload.capturedAt||new Date().toISOString()),sourceURL:String(payload.url||'')};
    if(!save())throw Error('No s’han pogut guardar els IDs');
    toast('ACTES IMPORTADES · Lliga '+league+' · '+incoming.length+' identificadors · '+merged.size+' totals');
    render();return true;
  }
  if(payload.kind==='agenda-season'){if(rows.length>1500)throw Error('Massa partits');const parsed=rows.map(a=>Array.isArray(a)?({iso:a[0],time:a[1],competition:a[2],home:a[3],away:a[4],homeScore:a[5],awayScore:a[6],venue:a[7],id:a[8]||'',actaUrl:a[9]||'',league:a[10]||''}):a).map(parseRow).filter(Boolean);if(!parsed.length||parsed.length!==rows.length)throw Error('La temporada cont\u00E9 files incompletes');const prior=agendaRows();for(const r of parsed){r.homeClub=clubOf(r.home);r.awayClub=clubOf(r.away);r.capturedAt=String(payload.capturedAt||'');}const merged=mergeAgendaRows(prior,parsed);store.agenda={season:String(payload.season||''),capturedAt:String(payload.capturedAt||''),sourceURL:String(payload.url||''),counts:{...(payload.counts||{}),barca:merged.filter(r=>r.homeClub==='barca'||r.awayClub==='barca').length,celoni:merged.filter(r=>r.homeClub==='celoni'||r.awayClub==='celoni').length},rows:merged};if(!save())throw Error('No es pot desar al navegador');toast('Importats '+parsed.length+' partits \u00B7 total conservat: '+merged.length);render();return true;}if(payload.kind==='season-v1'){const id=String(payload.league);if(!Object.hasOwn(LEAGUES,id)||rows.length>1000)throw Error('Lliga o nombre de partits no v\u00E0lid');const parsed=rows.map(a=>Array.isArray(a)?({iso:a[0],time:a[1],competition:a[2],home:a[3],away:a[4],homeScore:a[5],awayScore:a[6],venue:a[7],id:a[8]||'',actaUrl:a[9]||'',league:id}):a).map(parseRow).filter(Boolean);if(!parsed.length||parsed.length!==rows.length)throw Error('Temporada incompleta o il\u00B7legible');store.seasons=store.seasons||{};store.seasons[id]={season:String(payload.season||''),capturedAt:String(payload.capturedAt||''),sourceURL:String(payload.url||''),rows:parsed};if(save())toast(LEAGUES[id].name+': '+parsed.length+' partits de temporada');render();return;}if(!Object.hasOwn(LEAGUES,String(payload.league)))throw Error('Lliga no acceptada');const id=String(payload.league);if(rows.length>100)throw Error('Massa files');if(payload.kind==='standings'){const st=rows.map(r=>({pos:String(r.pos||'').slice(0,10),team:String(r.team||'').slice(0,100),played:String(r.played??'').slice(0,10),points:String(r.points??'').slice(0,10),gf:stat(r.gf),ga:stat(r.ga),difference:stat(r.difference,true),stats:Object.fromEntries(Object.entries(r.stats||{}).filter(([k])=>/^[A-Z0-9_ -]{1,30}$/.test(k)).map(([k,v])=>[k,stat(v,true)]))})).filter(r=>r.team);if(!st.length)throw Error('Classificaci\u00F3 buida');store[id]={...(store[id]||{}),standings:st,standingsAt:String(payload.capturedAt||'')};if(save())toast('Classificaci\u00F3 '+LEAGUES[id].name+' importada ('+st.length+' equips)');}else{const parsed=rows.map(parseRow).filter(Boolean).filter(r=>r.iso&&r.home&&r.away);if(!parsed.length)throw Error('No hi ha partits estructurats v\u00E0lids. Comprova el calendari.');const prior=store[id]||{};const byKey=new Map((prior.rows||[]).map(r=>[r.iso+' '+r.time+' '+r.home+' '+r.away,r]));for(const r of parsed)byKey.set(r.iso+' '+r.time+' '+r.home+' '+r.away,r);store[id]={...prior,rows:[...byKey.values()].sort((a,b)=>(a.iso+' '+a.time).localeCompare(b.iso+' '+b.time)),capturedAt:String(payload.capturedAt||''),sourceURL:String(payload.url||'')};if(save())toast(LEAGUES[id].name+': '+parsed.length+' files importades');}render();}catch(err){toast('Importaci\u00F3 no v\u00E0lida: '+err.message);return false;}}
function stat(v,signed=false){return (signed?/^[+-]?\d+$/:/^\d+$/).test(String(v??''))?String(v).slice(0,8):null}
function parseRow(r){if(!r||typeof r!=='object')return null;const iso=String(r.iso||'').slice(0,10),time=String(r.time||'').slice(0,5),home=String(r.home||'').trim().slice(0,120),away=String(r.away||'').trim().slice(0,120);if(!/^\d{4}-\d{2}-\d{2}$/.test(iso)||!/^\d\d:\d\d$/.test(time)||!home||!away)return null;const score=v=>v===null||v===undefined||v===''?null:(Number.isInteger(+v)&&+v>=0&&+v<200?+v:null);return{iso,time,home,away,competition:String(r.competition||'').slice(0,120),homeScore:score(r.homeScore),awayScore:score(r.awayScore),venue:String(r.venue||'').slice(0,180),homeLogo:safeImage(r.homeLogo),awayLogo:safeImage(r.awayLogo),actaUrl:String(r.actaUrl||'').startsWith('https://www.hoqueipatins.fecapa.cat/')?String(r.actaUrl).slice(0,300):'',id:String(r.id||'').slice(0,60),league:numericId(r.league||r.leagueId||r.liga||r.competitionId),capturedAt:String(r.capturedAt||'').slice(0,40)}}
function validateLive(r){
 const x=parseRow(r);if(!x)return null;
 for(const k of ['competition','round','status','homeClub','awayClub'])x[k]=String(r[k]||'').slice(0,120);
 const valid=(side)=>{const name=x[side],logo=x[side+'Logo'],club=x[side+'Club'];return (club==='barca'&&name==='BAR'&&/\/234\.png$/i.test(logo))||(club==='celoni'&&name==='CPSC'&&/\/281\.png$/i.test(logo))};
 for(const side of ['home','away'])if(!valid(side))x[side+'Club']='';if(!x.homeClub&&!x.awayClub)return null;return x;
}
function liveKey(r){return [r.competition,r.round,r.home,r.away,r.homeLogo,r.awayLogo,r.iso].join('|')}


/* Conserva els partits anteriors i identifica canvis d'hora sense duplicar-los.
   Quan canvia el dia, fusiona nom\u00E9s si hi ha una coincid\u00E8ncia inequ\u00EDvoca
   de competici\u00F3 i equips dins d'una finestra de 21 dies. */
function mergeAgendaRows(previous,incoming){
  const out=[...(previous||[])].map(r=>({...r}));
  const touched=new Set();
  const sameFixture=(a,b)=>normalize(a.home)===normalize(b.home)&&normalize(a.away)===normalize(b.away)&&normalize(a.competition)===normalize(b.competition);
  const daysApart=(a,b)=>Math.abs((Date.parse(a.iso+'T12:00:00Z')-Date.parse(b.iso+'T12:00:00Z'))/86400000);
  for(const row of incoming){
    let index=-1;
    if(row.id)index=out.findIndex((r,i)=>!touched.has(i)&&r.id&&r.id===row.id);
    if(index<0)index=out.findIndex((r,i)=>!touched.has(i)&&sameFixture(r,row)&&r.iso===row.iso);
    if(index<0){
      const possible=[];
      for(let i=0;i<out.length;i++){
        if(touched.has(i)||!sameFixture(out[i],row)||daysApart(out[i],row)>21)continue;
        // Un partit ja jugat no es pot moure a una nova data pendent.
        if(out[i].homeScore!==null&&out[i].awayScore!==null&&row.homeScore===null&&row.awayScore===null)continue;
        possible.push(i);
      }
      if(possible.length===1)index=possible[0];
    }
    if(index<0){out.push({...row});touched.add(out.length-1);continue;}
    const old=out[index];
    if(String(row.capturedAt||'')>=String(old.capturedAt||'')){
      out[index]={...old,...row,
        venue:row.venue||old.venue||'',
        homeLogo:row.homeLogo||old.homeLogo||'',awayLogo:row.awayLogo||old.awayLogo||'',
        actaUrl:row.actaUrl||old.actaUrl||'',id:row.id||old.id||'',league:row.league||old.league||'',
        homeScore:row.homeScore===null?old.homeScore:row.homeScore,
        awayScore:row.awayScore===null?old.awayScore:row.awayScore};
    }
    touched.add(index);
  }
  return out.sort((a,b)=>(a.iso+' '+a.time).localeCompare(b.iso+' '+b.time));
}

/* Importaci\u00F3 de temporada sense URLs llargues: Dreceres copia el JSON al porta-retalls. */
let clipboardDialog=null, clipboardTextarea=null, clipboardNote=null;
function showClipboardDialog(){
  if(!clipboardDialog)return;
  clipboardNote.textContent='Selecciona el fitxer JSON d’Agenda o d’Actes de FECAPA. Despr\u00E9s de llegir-lo, aquesta finestra mostrar\u00E0 el recompte importat, o b\u00E9 l\u2019error concret.';
  clipboardNote.style.color='#eef6ff';
  clipboardNote.style.fontWeight='400';
  clipboardDialog.showModal();
}
function importClipboardText(raw){
  let payload;
  try{payload=JSON.parse(String(raw||'').trim())}catch(_){throw Error('El porta-retalls no cont\u00E9 un JSON v\u00E0lid');}
  if(!payload||payload.source!=='FECAPA-SAFARI'||!['agenda-season','match-ids-v1'].includes(payload.kind)||!Array.isArray(payload.rows))throw Error('Cal un JSON d’Agenda o de la nova drecera ZonaOK Actes');
  if(!payload.rows.length)throw Error('La importaci\u00F3 no cont\u00E9 partits');
  if(payload.rows.length>1500)throw Error('La importaci\u00F3 supera el l\u00EDmit actual de 1.500 partits');
  if(!legacyImportHash(payload))throw Error('Les dades no s\u2019han pogut desar');
  // No tancar autom\u00E0ticament: iPhone necessita una confirmaci\u00F3 visible.
  const n=payload.rows.length;
  const total=payload.kind==='match-ids-v1'?(store.actaIndex?.[payload.league]?.rows||[]).length:agendaRows().length;
  const instant=store.agenda?.capturedAt ? formatTimestamp(store.agenda.capturedAt) : 'desconeguda';
  clipboardNote.textContent='IMPORTACI\u00D3 CORRECTA! '+n+(payload.kind==='match-ids-v1'?' IDs d\u2019acta':' partits')+'. Total acumulat: '+total+'. Lectura: '+instant+'. Ja pots pr\u00E9mer Tancar.';
  clipboardNote.style.color='#bbf7d0';
  clipboardNote.style.fontWeight='700';
  clipboardDialog?.querySelector('.zonaok-cancel')?.focus();
}
async function readClipboardAgenda(){
  try{
    if(!navigator.clipboard?.readText)throw Error('Safari no ofereix lectura directa del porta-retalls');
    const raw=await navigator.clipboard.readText();
    importClipboardText(raw);
  }catch(e){
    clipboardNote.textContent='El porta-retalls no serveix: '+e.message+'. Utilitza \u00ABSeleccionar fitxer JSON\u00BB.';
    clipboardTextarea.focus();
  }
}
function setupClipboardImport(){
  const style=mk('style');style.textContent=`
  .zonaok-paste-dialog{width:min(94vw,640px);max-height:90vh;overflow:auto;border:1px solid #3f718f;border-radius:20px;background:#09243d;color:#eef6ff;padding:20px;box-shadow:0 24px 70px #0008}
  .zonaok-paste-dialog::backdrop{background:#031221bc}
  .zonaok-paste-dialog h2{margin:0 0 12px;font-size:1.25rem;color:#fff}
  .zonaok-paste-dialog p{line-height:1.45}
  .zonaok-paste-dialog #import-agenda-file{display:block;background:#ffb56e;margin-bottom:16px}
  .zonaok-paste-dialog textarea{width:100%;box-sizing:border-box;min-height:115px;border-radius:8px;padding:10px;color:#082138;background:#fff}
  .zonaok-paste-dialog button{padding:12px 16px;border:0;border-radius:10px;background:#ffa965;color:#071f38;font-weight:700;margin:8px 8px 0 0}
  .zonaok-paste-dialog button.zonaok-cancel{background:#254b67;color:white}
  `;document.head.append(style);
  clipboardDialog=mk('dialog','zonaok-paste-dialog');
  clipboardDialog.append(mk('h2','','Importar agenda / actes FECAPA'));
  clipboardNote=mk('p','','');clipboardDialog.append(clipboardNote);
  const read=mk('button','','\u{1F4CB} Llegir porta-retalls');read.type='button';read.onclick=readClipboardAgenda;clipboardDialog.append(read);
  // Importaci\u00F3 estable des d\u2019un arxiu. Sense porta-retalls, GZIP ni URL llarga.
  const choose=mk('button','','\u{1F4C1} Seleccionar fitxer JSON');choose.type='button';
  choose.id='import-agenda-file';clipboardDialog.append(choose);
  const input=mk('input');input.type='file';input.accept='.json,application/json,text/plain';
  input.id='agenda-json-file';input.style.display='none';clipboardDialog.append(input);
  choose.onclick=()=>input.click();
  input.onchange=async()=>{
    const file=input.files?.[0];if(!file)return;
    try{
      if(file.size>3000000)throw Error('Fitxer de m\u00E9s de 3 MB: comprova que sigui l\u2019agenda');
      const raw=await file.text();
      importClipboardText(raw);
    }catch(e){clipboardNote.textContent='ERROR: no s\u2019ha importat '+file.name+'. Motiu: '+e.message;clipboardNote.style.color='#ffc5b8';clipboardNote.style.fontWeight='700';}
    finally{input.value='';}
  };
  clipboardTextarea=mk('textarea');clipboardTextarea.placeholder='Alternativa: enganxa aqu\u00ED el JSON complet';clipboardTextarea.setAttribute('aria-label','JSON de l\u2019agenda FECAPA');clipboardDialog.append(clipboardTextarea);
  const paste=mk('button','','Importar text enganxat');paste.type='button';paste.onclick=()=>{try{importClipboardText(clipboardTextarea.value)}catch(e){clipboardNote.textContent='Error: '+e.message;}};clipboardDialog.append(paste);
  const cancel=mk('button','zonaok-cancel','Tancar');cancel.type='button';cancel.onclick=()=>clipboardDialog.close();clipboardDialog.append(cancel);
  document.body.append(clipboardDialog);
  const reference=$$('#export-shared');
  if(reference?.parentNode){const b=mk('button',reference.className,'\u{1F4C1} Importar agenda / actes JSON');b.type='button';b.id='import-clipboard';b.onclick=showClipboardDialog;reference.parentNode.insertBefore(b,reference);}
}

function importHash(){
 const h=location.hash.slice(1);const err=new URLSearchParams(location.search).get('error');if(err){toast(err);history.replaceState(null,'',location.pathname);}
  if(h==='fecapa-clipboard'){history.replaceState(null,'',location.pathname+location.search);showClipboardDialog();return;}
 if(h.startsWith('fecapa-gz=')){try{const b64=h.slice(10).replace(/-/g,'+').replace(/_/g,'/'),binary=atob(b64+'='.repeat((4-b64.length%4)%4)),bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));if(typeof DecompressionStream==='undefined')throw Error('Aquest Safari no pot obrir la importaci\u00F3 comprimida');new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text().then(t=>legacyImportHash(JSON.parse(t))).catch(e=>toast('No s\u2019ha pogut llegir la temporada: '+e.message));}catch(e){toast('No s\u2019ha pogut obrir la temporada: '+e.message)}return;}
 if(!h.startsWith('fecapa='))return;
 let p;try{p=JSON.parse(decodeURIComponent(h.slice(7)))}catch(e){toast('Importaci\u00F3 il\u00B7legible');return;}
 if(p.kind!=='live'){legacyImportHash(p);return;}
 if(p.format==='compact'){try{if(!Array.isArray(p.competitions)||p.competitions.length>100)throw Error();p.rows=p.rows.map(a=>{if(!Array.isArray(a)||a.length!==11||!Number.isInteger(a[4])||typeof p.competitions[a[4]]!=='string'||![a[9],a[10]].every(x=>typeof x==='string'&&/^[a-zA-Z0-9_.-]+$/.test(x)))throw Error();const base='https://sidgad.cloud/fecapa/images/logos_clubes/';return {iso:a[0],time:a[1],home:a[2],away:a[3],competition:p.competitions[a[4]],round:a[5],status:a[6],homeScore:a[7],awayScore:a[8],homeLogo:base+a[9],awayLogo:base+a[10],homeClub:a[2]==='BAR'?'barca':a[2]==='CPSC'?'celoni':'',awayClub:a[3]==='BAR'?'barca':a[3]==='CPSC'?'celoni':''};});}catch(e){toast('Paquet compacte no v\u00E0lid');return;}}
 history.replaceState(null,'',location.pathname+location.search);
 try{
 if(p.source!=='FECAPA-SAFARI'||!Array.isArray(p.rows)||p.rows.length>300||!Number.isFinite(Date.parse(p.capturedAt)))throw Error('Paquet no v\u00E0lid');
 const rows=p.rows.map(validateLive);if(!rows.length||rows.some(r=>!r))throw Error('Hi ha files no v\u00E0lides. No s\u2019ha fet una importaci\u00F3 parcial.');
 const season=String(p.season||'');const prior=store.live?.season===season?liveRows():[];
 const byKey=new Map(prior.map(r=>[liveKey(r),r]));if(new Set(rows.map(liveKey)).size!==rows.length)throw Error('Hi ha equips ambigus amb la mateixa categoria i jornada. No s\u2019han fusionat.');for(const r of rows){const old=byKey.get(liveKey(r));if(!old||String(old.capturedAt||'')<=p.capturedAt)byKey.set(liveKey(r),{...r,capturedAt:p.capturedAt});}
 store.live={rows:[...byKey.values()],capturedAt:p.capturedAt,season};save();render();toast(rows.length+' partits llegits d\u2019En directe. Publica el JSON per compartir-los.');
 }catch(e){toast('Importaci\u00F3 no v\u00E0lida: '+e.message)}
}

// PUBLICACIÓ D'ACTES: GitHub Pages no permet escriure fitxers automàticament.
// La descàrrega crea zonaok-actes.json amb les dades REALS del Safari;
// l'usuari el publica al repositori. No es toca zonaok-data.json.
function buildActaFile(){
  const local=load(),out=new Map(),now=new Date().toISOString();
  const candidates=[...(local.agenda?.rows||[])];
  for(const league of Object.keys(LEAGUES))candidates.push(...(local.seasons?.[league]?.rows||[]),...(local[league]?.rows||[]));
  const byFixture=(a,b)=>a.iso===b.iso&&matchTeamKey(a.home)===matchTeamKey(b.home)&&matchTeamKey(a.away)===matchTeamKey(b.away);
  const add=(league,id,record)=>{
    if(!Object.hasOwn(LEAGUES,String(league))||!numericId(id)||!/^20\d\d-\d\d-\d\d$/.test(String(record.iso||'')))return;
    const key=String(league)+':'+String(id);
    const compatible=candidates.filter(r=>byFixture(r,record)&&(matchLeagueId(r,'')===String(league)||!matchLeagueId(r,'')));
    const matched=compatible.length?compatible.find(r=>r.time===record.time)||compatible[0]:null;
    const score=val=>Number.isInteger(val)&&val>=0?val:null;
    const entry={league:String(league),id:String(id),iso:String(record.iso),time:String(record.time||''),home:String(record.home||''),away:String(record.away||''),
      competition:LEAGUES[league].name,homeScore:score(matched?.homeScore),awayScore:score(matched?.awayScore),
      venue:String(matched?.venue||record.venue||''),actaUrl:matchOfficialLink(league,id)};
    const old=out.get(key);
    if(!old||(!old.venue&&entry.venue))out.set(key,entry);
  };
  for(const [league,data] of Object.entries(local.actaIndex||{}))for(const r of data?.rows||[])add(league,r.id,r);
  // Actes guardades directament en calendaris de temporada.
  for(const league of Object.keys(LEAGUES))for(const r of [...(local[league]?.rows||[]),...(local.seasons?.[league]?.rows||[])]){
    const link=officialFecapaURL(r.actaUrl);
    if(!link)continue;
    const u=new URL(link),id=numericId(u.searchParams.get('partido'));
    if(id&&u.searchParams.get('liga')===league)add(league,id,r);
  }
  return {version:1,generatedAt:now,source:'FECAPA-SAFARI',fixtures:[...out.values()].sort((a,b)=>a.iso.localeCompare(b.iso)||a.league.localeCompare(b.league))};
}
function exportActesJSON(){
  const packet=buildActaFile();
  if(!packet.fixtures.length){toast('Encara no hi ha IDs d\u2019acta verificats en aquest Safari.');return;}
  const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)],{type:'application/json;charset=utf-8'}));
  const a=mk('a');a.href=url;a.download='zonaok-actes.json';document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),5000);
  toast(packet.fixtures.length+' fitxes d\u2019acta exportades. Publica zonaok-actes.json a GitHub.');
}
async function loadActesJSON(){
  try{
    const response=await fetch('zonaok-actes.json?t='+Date.now(),{cache:'no-store'});
    if(!response.ok)return;
    const packet=await response.json();
    if(packet.version!==1||!Array.isArray(packet.fixtures)||packet.fixtures.length>1200)return;
    const current=load();current.actaIndex=current.actaIndex||{};
    let changes=0;
    for(const f of packet.fixtures){
      const league=String(f.league||''),id=numericId(f.id);
      if(!Object.hasOwn(LEAGUES,league)||!id||!/^20\d\d-\d\d-\d\d$/.test(String(f.iso||'')))continue;
      if(!String(f.home||'').trim()||!String(f.away||'').trim())continue;
      // Comprovació estricta de l'URL; rebutgem qualsevol ID/lliga discordant.
      const url=officialFecapaURL(f.actaUrl);if(!url)continue;
      const u=new URL(url);
      if(u.searchParams.get('partido')!==id||u.searchParams.get('liga')!==league)continue;
      const entry={iso:String(f.iso),time:String(f.time||''),home:String(f.home).slice(0,120),away:String(f.away).slice(0,120),id,league,actaUrl:matchOfficialLink(league,id)};
      const old=current.actaIndex[league]?.rows||[];
      // Mateix partit oficial: combinar per ID. No esborrar altres actes locals.
      if(old.some(r=>String(r.id)===id))continue;
      current.actaIndex[league]={...current.actaIndex[league],rows:[...old,entry],capturedAt:packet.generatedAt||''};changes++;
    }
    if(changes){try{localStorage.setItem(KEY,JSON.stringify(current));store=current;render();}catch(_){}}
  }catch(_){/* Offline: les actes locals continuen disponibles. */}
}

function downloadShared(){const packet={version:3,publishedAt:new Date().toISOString(),data:store};const a=mk('a');const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)],{type:'application/json'}));a.href=url;a.download='zonaok-data.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);toast('Fitxer preparat. Puja zonaok-data.json a l\u2019arrel del repositori i confirma el commit.');}
async function loadShared(){try{const response=await fetch('zonaok-data.json?t='+Date.now(),{cache:'no-store'});if(!response.ok)return;const p=await response.json();if(p.version!==3||!p.data||typeof p.data!=='object')return;
 for(const id of ['live','agenda','4789','4786','4784']){const item=p.data[id];if(!item)continue;const current=store[id]||{};
 if(id==='agenda'){if(!Array.isArray(item.rows)||item.rows.length>1500)continue;const rows=item.rows.map(parseRow).filter(Boolean).map(r=>({...r,homeClub:clubOf(r.home),awayClub:clubOf(r.away)}));if(rows.length!==item.rows.length)continue;const currentRows=agendaRows();const merged=mergeAgendaRows(rows,currentRows);store.agenda={...item,rows:merged,capturedAt:[item.capturedAt,current.capturedAt].filter(Boolean).sort().pop()};}else if(id==='live'){if(!Array.isArray(item.rows)||item.rows.length>1000)continue;const rows=item.rows.map(validateLive);if(rows.some(r=>!r))continue;const merged=new Map(rows.map(r=>[liveKey(r),r]));for(const r of current.rows||[]){const old=merged.get(liveKey(r));if(!old||String(r.capturedAt||current.capturedAt)>String(old.capturedAt||item.capturedAt))merged.set(liveKey(r),r)}store[id]={...item,rows:[...merged.values()],capturedAt:[item.capturedAt,current.capturedAt].filter(Boolean).sort().pop()};}
 else {const next={...current};if(Array.isArray(item.rows)&&String(item.capturedAt||'')>String(current.capturedAt||'')){next.rows=item.rows.map(parseRow).filter(Boolean);next.capturedAt=item.capturedAt;}
 if(Array.isArray(item.standings)&&item.standings.length<=30&&String(item.standingsAt||'')>String(current.standingsAt||'')){next.standings=item.standings.map(r=>({pos:String(r.pos||'').slice(0,10),team:String(r.team||'').slice(0,120),played:String(r.played??'').slice(0,10),points:String(r.points??'').slice(0,10),gf:stat(r.gf),ga:stat(r.ga),difference:stat(r.difference,true),stats:Object.fromEntries(Object.entries(r.stats||{}).filter(([k])=>/^[A-Z0-9_ -]{1,30}$/.test(k)).map(([k,v])=>[k,stat(v,true)]))}));next.standingsAt=item.standingsAt;}store[id]=next;}}
 const actaData=p.data.actaIndex;if(actaData&&typeof actaData==='object'){store.actaIndex=store.actaIndex||{};for(const id of Object.keys(LEAGUES)){const item=actaData[id];if(!item||!Array.isArray(item.rows)||item.rows.length>300)continue;const prior=store.actaIndex[id]?.rows||[];const key=r=>[r.iso,r.time,matchTeamKey(r.home),matchTeamKey(r.away)].join('|');const merged=new Map(item.rows.filter(r=>numericId(r.id)).map(r=>[key(r),r]));for(const r of prior)if(numericId(r.id))merged.set(key(r),r);store.actaIndex[id]={rows:[...merged.values()],capturedAt:[item.capturedAt,store.actaIndex[id]?.capturedAt].filter(Boolean).sort().pop()};}}
  const seasons=p.data.seasons;if(seasons&&typeof seasons==='object'){store.seasons=store.seasons||{};for(const id of ['4789','4786','4784']){const item=seasons[id];if(!item||!Array.isArray(item.rows)||item.rows.length>1000)continue;const current=store.seasons[id];if(!current||String(item.capturedAt||'')>String(current.capturedAt||'')){const rows=item.rows.map(parseRow).filter(Boolean);if(rows.length===item.rows.length)store.seasons[id]={...item,rows};}}}save();render();}catch(_){/* Offline: keep the last local snapshot. */}}
$$('#export-shared').onclick=downloadShared;
$$('#publish-shared').onclick=()=>window.open('https://github.com/carlesjfontanillas-beep/ZonaOK/upload/main','_blank','noopener');
$$('#reload-shared').onclick=()=>{loadShared();loadActesJSON();};
$$('#guide-button').onclick=()=>$$('#guide').showModal();$$('#guide-close').onclick=()=>$$('#guide').close();$$('#clear-button').onclick=()=>{if(confirm('Esborrar totes les dades importades de Safari a ZonaOK?')){localStorage.removeItem(KEY);localStorage.removeItem(OLD);store={};render();toast('Dades esborrades.')}};$$('#ask-home').onclick=()=>ask('home');$$('#refresh-home').onclick=()=>selectSection('home');$$('#close-results').onclick=()=>selectSection('home');document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>selectSection(b.dataset.tab));
$$('#week-prev').onclick=()=>changeWeek(-1);
$$('#week-next').onclick=()=>changeWeek(1);
$$('#week-today').onclick=resetWeek;
$$('#season-toggle').onclick=()=>{if(section!=='home')return;};
installWeekGestures();
setupActaDialog();
setupClipboardImport();
const btnActes=$$('#import-actes-json');if(btnActes)btnActes.onclick=showClipboardDialog;
const exportActes=$$('#export-actes-json');if(exportActes)exportActes.onclick=exportActesJSON;
render();importHash();loadShared();loadActesJSON();
})();
