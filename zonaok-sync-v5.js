/* ZonaOK V10.5 \u2014 Agenda com a font de partits, En directe nomes com a font de marcadors.
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
  const cleanSeasonRow=(input,league)=>{
    const r=Array.isArray(input)?{iso:input[0],time:input[1],competition:input[2],home:input[3],away:input[4],homeScore:input[5],awayScore:input[6],venue:input[7],actaId:input[8]}:input;
    if(!r||typeof r!=='object'||!validDate(r.iso)||!validTime(r.time)||!text(r.home)||!text(r.away))return null;
    const score=v=>v==null||v===''?null:(Number.isInteger(+v)&&+v>=0&&+v<200?+v:null);
    const homeScore=score(r.homeScore),awayScore=score(r.awayScore);
    if((homeScore===null)!==(awayScore===null))return null;
    let actaUrl='';try{const u=new URL(r.actaUrl||'');if(u.protocol==='https:'&&u.hostname==='www.hoqueipatins.fecapa.cat'&&u.searchParams.has('partido'))actaUrl=u.href}catch(_){}
    if(!actaUrl&&/^\d{4,}$/.test(String(r.actaId||''))&&['4789','4786'].includes(String(league)))actaUrl=ROOT+`?liga=${league}&vista=calendar&partido=${r.actaId}`;
    return {iso:r.iso,time:r.time,competition:text(r.competition),home:text(r.home),away:text(r.away),homeScore,awayScore,venue:text(r.venue),actaUrl};
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
      // Conservem la pista literal fins i tot si FECAPA retorna una cel\u00B7la buida.
      if(!text(r.venue)&&text(old.venue))combined.venue=old.venue;
      map.set(k,combined);
    }
    return [...map.values()].sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time)).slice(-2000);
  };
  const mergeData=(store,kind,p)=>{
    if(kind==='season-v1'){
      const id=String(p.league||'');
      if(!['4789','4786'].includes(id)||!Array.isArray(p.rows)||p.rows.length>100||!Number.isFinite(Date.parse(p.capturedAt)))throw Error('Importaci\u00F3 de temporada no v\u00E0lida');
      const next=p.rows.map(r=>cleanSeasonRow(r,id));
      if(!next.length||next.some(r=>!r)||new Set(next.map(rowKey)).size!==next.length)throw Error('Hi ha partits de temporada buits o duplicats');
      const prior=store.seasons?.[id]||{},rows=mergeRows(prior.rows||[],next.map(r=>({...r,capturedAt:p.capturedAt})));
      store.seasons={...(store.seasons||{}),[id]:{rows,capturedAt:p.capturedAt,season:text(p.season),sourceURL:text(p.url)}};
      return `${id==='4789'?'Alev\u00ED OR 3 \u00B7 Bar\u00E7a':'Infantil OR 10 \u00B7 Sant Celoni'}: ${rows.length} partits de temporada`;
    }
    if(kind==='agenda-v5'){
      if(!Array.isArray(p.rows)||p.rows.length>150||!validDate(p.weekStart)||!validDate(p.weekEnd))throw Error('Dades d\u2019Agenda no v\u00E0lides');
      const next=p.rows.map(cleanAgenda);
      if(!next.length||next.some(r=>!r)||new Set(next.map(rowKey)).size!==next.length)throw Error('Hi ha partits buits o duplicats');
      const stamped=next.map(r=>({...r,capturedAt:p.capturedAt}));
      store.agenda={rows:mergeRows(store.agenda?.rows||[],stamped),capturedAt:[store.agenda?.capturedAt,p.capturedAt].filter(Boolean).sort().pop()};
      const cb=p.counts?.barca ?? next.filter(r=>isBarca(r.home)||isBarca(r.away)).length;
      const cs=p.counts?.celoni ?? next.filter(r=>isCeloni(r.home)||isCeloni(r.away)).length;
      const pistes=next.filter(r=>!!r.venue).length;
      return `Agenda: ${next.length} partits (${cb} Bar\u00E7a, ${cs} Sant Celoni) \u00B7 ${pistes} pistes`;
    }
    if(kind==='resultats-v5'){
      if(!Array.isArray(p.rows)||p.rows.length>300)throw Error('Dades d\u2019En directe no v\u00E0lides');
      const next=p.rows.map(cleanScore);
      if(!next.length||next.some(r=>!r))throw Error('Cap marcador v\u00E0lid');
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
    if(p?.kind!=='agenda-v5'&&p?.kind!=='resultats-v5'&&p?.kind!=='season-v1')return; // els paquets antics els gestiona app.js
    history.replaceState(null,'',location.pathname+location.search);
    try{
      if(p.source!=='FECAPA-SAFARI'||p.v!==5||!Number.isFinite(Date.parse(p.capturedAt)))throw Error('Font o data desconeguda');
      const store=read();importMessage=mergeData(store,p.kind,p);
      if(!write(store))throw Error('No es poden desar les dades localment');
    }catch(e){importMessage='Error d\u2019importaci\u00F3: '+e.message;}
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
    // En directe t\u00E9 prioritat sobre els marcadors d'Agenda, que es publiquen amb retard.
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
  // Dates i hores de FECAPA estan en hora local Europe/Madrid.
  // El fitxer ICS usa UTC real: evita desfasaments a l'estiu i a l'hivern.
  function madridToUTC(iso,time){
    const [year,month,day]=iso.split('-').map(Number);
    const [hour,minute]=time.split(':').map(Number);
    const wanted=Date.UTC(year,month-1,day,hour,minute);
    const fmt=new Intl.DateTimeFormat('en-GB',{
      timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit',
      hour:'2-digit',minute:'2-digit',hourCycle:'h23'
    });
    const localAsUTC=ms=>{
      const parts=Object.fromEntries(fmt.formatToParts(new Date(ms)).filter(x=>x.type!=='literal').map(x=>[x.type,Number(x.value)]));
      return Date.UTC(parts.year,parts.month-1,parts.day,parts.hour,parts.minute);
    };
    let actual=wanted-(localAsUTC(wanted)-wanted);
    actual=wanted-(localAsUTC(actual)-actual);
    return new Date(actual);
  }
  const icsUTC=d=>d.toISOString().slice(0,19).replace(/[-:]/g,'')+'Z';
  const icsText=value=>String(value??'').replace(/\\/g,'\\\\').replace(/\r\n|\r|\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
  function icsFold(line){
    // RFC 5545: continuaci\u00F3 de l\u00EDnies llargues (m\u00E0xim 75 octets).
    const encoder=new TextEncoder();let result='',bytes=0;
    for(const ch of line){
      const count=encoder.encode(ch).length;
      if(bytes+count>75){result+='\r\n ';bytes=1;}
      result+=ch;bytes+=count;
    }
    return result;
  }
  function mapsURL(venue){
    return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(venue);
  }
  function calendarICS(r){
    const start=madridToUTC(r.iso,r.time);
    const end=new Date(start.getTime()+90*60000); // Durada estimada: 1 h 30 min.
    const title=`${r.home} - ${r.away}`;
    const description=[
      'Partit d\u2019hoquei patins',
      'Competici\u00F3: '+(r.competition||'No indicada'),
      'Hora local: '+r.iso+' '+r.time+' (Europe/Madrid)',
      ...(r.venue?['Pista: '+r.venue,'Google Maps: '+mapsURL(r.venue)]:[]),
      'Font: Agenda FECAPA'
    ].join('\n');
    let hash=2166136261;
    for(const ch of rowKey(r))hash=Math.imul(hash^ch.charCodeAt(0),16777619)>>>0;
    const lines=[
      'BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//ZonaOK//Partits FECAPA//CA',
      'CALSCALE:GREGORIAN','METHOD:PUBLISH','BEGIN:VEVENT',
      'UID:zonaok-'+r.iso.replace(/-/g,'')+'-'+hash.toString(16)+'@zonaok.local',
      'DTSTAMP:'+icsUTC(new Date()),
      'DTSTART:'+icsUTC(start),'DTEND:'+icsUTC(end),
      'SUMMARY:'+icsText(title),
      'DESCRIPTION:'+icsText(description),
      ...(r.venue?['LOCATION:'+icsText(r.venue)]:[]),
      'URL:'+AGENDA,
      'END:VEVENT','END:VCALENDAR'
    ];
    return lines.map(icsFold).join('\r\n')+'\r\n';
  }
  function addCalendar(r){
    if(!validDate(r.iso)||!validTime(r.time))return;
    const blob=new Blob([calendarICS(r)],{type:'text/calendar;charset=utf-8'});
    const url=URL.createObjectURL(blob);
    const link=el('a');link.href=url;
    link.download='ZonaOK-'+r.iso+'-'+r.time.replace(':','')+'.ics';
    document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  }
  function card(r,compact){
    const cls=isBarca(r.home)||isBarca(r.away)?'zok-v5-barca':
      /INFANTIL OR 10/.test(norm(r.competition))&& (isCeloni(r.home)||isCeloni(r.away))?'zok-v5-infantil':
      /JUVENIL OR 6/.test(norm(r.competition))&&(isCeloni(r.home)||isCeloni(r.away))?'zok-v5-juvenil':'zok-v5-neutral';
    const c=el('article','match zok-v5 '+cls+(compact?' zok-compact':''));
    c.dataset.zokV5='1';
    const top=el('div','match-top'),scoreLabel=validScore(r.homeScore)&&validScore(r.awayScore)?(r.scoreSource==='En directe'?'En directe':'Resultat \u00B7 FECAPA'):'Agenda \u00B7 FECAPA';top.append(el('span','pill',r.competition||'Categoria no indicada'),el('span','tag',scoreLabel));c.append(top);
    const dt=el('div','match-date');dt.append(el('strong','',r.time),el('small','',nice(r.iso)));if(compact)dt.dataset.zokCategoria=r.competition||'Categoria';c.append(dt);
    const teams=el('div','teams'),middle=el('div','middle');middle.append(el('div','score',validScore(r.homeScore)&&validScore(r.awayScore)?`${r.homeScore} : ${r.awayScore}`:'\u2014 : \u2014'),el('small','score-note',validScore(r.homeScore)&&validScore(r.awayScore)?scoreLabel:'Pendent'));
    teams.append(teamSide(r.home),middle,teamSide(r.away));c.append(teams);
    if(!compact){
      const venue=el('div','venue');
      if(r.venue){
        const map=el('a','zok-map-link');map.href=mapsURL(r.venue);
        map.target='_blank';map.rel='noopener noreferrer';
        map.setAttribute('aria-label','Obrir Google Maps: '+r.venue);
        map.append(el('strong','','\uD83D\uDCCD '+r.venue+' \u2197'));venue.append(map);
      }else venue.append(el('strong','','\uD83D\uDCCD Pista no indicada a Agenda'));
      // Acc\u00E9s al calendari al costat de la pista, nom\u00E9s a les 3 targetes d'inici.
      const calendar=el('button','zok-calendar-btn','\uD83D\uDCC5 Calendari');
      calendar.type='button';
      calendar.title='Afegir al calendari';
      calendar.setAttribute('aria-label','Afegir al calendari: '+r.home+' contra '+r.away);
      calendar.addEventListener('click',()=>addCalendar(r));
      venue.append(calendar);
      c.append(venue);
    }
    const actions=el('div','match-actions');
    if(r.actaUrl){
      const link=el('a','light','\u2315 Acta');link.href=r.actaUrl;link.target='_blank';link.rel='noopener';
      link.setAttribute('aria-label','Obrir la fitxa i l\u2019acta oficial del partit');actions.append(link);
    }
    if(actions.childNodes.length)c.append(actions);
    return c;
  }
  const byWeek=(rows)=>{const start=monday(),end=plus(start,6);return rows.filter(r=>r.iso>=start&&r.iso<=end).sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time));};
  const favoriteDefs=[
    {name:'Bar\u00E7a Alev\u00ED',f:r=>(isBarca(r.home)||isBarca(r.away))&&norm(r.competition)==='ALEVI OR 3'},
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
      else{const note=el('div','empty');note.dataset.zokV5='1';note.append(el('strong','',def.name+' \u00B7 Sense partit importat aquesta setmana'));frag.append(note)}
    }
    root.replaceChildren(frag);if($('#home-count'))$('#home-count').textContent=count+' partits';
  }
  function activeTab(){const button=$('.navbtn.active');return button?.dataset.tab||($('#results-section')?.classList.contains('hide')?'home':'');}
  // V10.5: les consultes de club i de Magi/Ton sempre son de TEMPORADA.
  // La pantalla Inici es l'unic lloc on apliquem el filtre setmanal.
  function drawList(tab,rows,store){
    const root=$('#results-list');
    if(!root||$('#results-section')?.classList.contains('hide'))return;
    if(tab==='classificacions'||!['barca','celoni','grupalevi','grupinfantil'].includes(tab))return;

    const seasonId=tab==='grupalevi'?'4789':tab==='grupinfantil'?'4786':'';
    const seasons=store.seasons||{};
    const seasonItem=seasonId?(seasons[seasonId]||{}):{};
    const wanted=String(store.agenda?.season||seasonItem.season||'');
    const dates=wanted.match(/(20\d{2})\D+(20\d{2})/);
    const current=Number(monday().slice(0,4))-(Number(monday().slice(5,7))<7?1:0);
    const y=dates?Number(dates[1]):current;
    const seasonName=dates?wanted:(y+'/'+(y+1));
    const seasonStart=y+'-07-01',seasonEnd=(y+1)+'-06-30';

    const isTon=s=>/^(?:(?:CP|C P|CLUB PATI)\s+)?SANT CELONI\s+B$/.test(norm(s));
    const alevi=s=>/^ALEVI\s+OR\s+0?3(?:\s|$)/.test(norm(s));
    const infantil=s=>/^INFANTIL\s+OR\s+0?10(?:\s|$)/.test(norm(s));
    const sameClub=(r,check)=>check(r.home)||check(r.away);
    const leagueMatch=(r,knownId)=>knownId==='4789'
      ?sameClub(r,isBarca)&&(!r.competition||alevi(r.competition))
      :sameClub(r,isTon)&&(!r.competition||infantil(r.competition));

    // La base es l'agenda general. Els calendaris individuals son complementaris,
    // mai no han de substituir els partits que ja s'han importat a l'agenda.
    const sources=rows.map(r=>({...r}));
    if(seasonId){
      const official=[...(store[seasonId]?.rows||[]),...(seasonItem.rows||[])];
      for(const r of official){
        if(!r||!leagueMatch(r,seasonId))continue;
        sources.push(resolved({...r,
          competition:r.competition|| (seasonId==='4789'?'Alevi OR 3':'Infantil OR 10'),
          capturedAt:r.capturedAt||seasonItem.capturedAt||store[seasonId]?.capturedAt||''},store));
      }
    }

    const eligible=r=>r&&validDate(r.iso)&&validTime(r.time)&&
      r.iso>=seasonStart&&r.iso<=seasonEnd;
    const keep=r=>{
      if(tab==='barca')return sameClub(r,isBarca);
      if(tab==='celoni')return sameClub(r,isCeloni);
      if(tab==='grupalevi')return alevi(r.competition)&&sameClub(r,isBarca);
      return infantil(r.competition)&&sameClub(r,isTon);
    };
    const byFixture=new Map();
    for(const r of sources){
      if(!eligible(r)||!keep(r))continue;
      // No utilitzem l'hora a la clau: un partit mogut d'horari no es duplica.
      const key=r.id?'id:'+r.id:[r.iso,norm(r.competition),norm(r.home),norm(r.away)].join('|');
      const prev=byFixture.get(key);
      if(!prev){byFixture.set(key,r);continue;}
      const newer=String(r.capturedAt||'')>=String(prev.capturedAt||'')?r:prev;
      const older=newer===r?prev:r;
      byFixture.set(key,{...older,...newer,
        venue:newer.venue||older.venue||'',
        actaUrl:newer.actaUrl||older.actaUrl||'',
        homeScore:validScore(newer.homeScore)?newer.homeScore:older.homeScore,
        awayScore:validScore(newer.awayScore)?newer.awayScore:older.awayScore});
    }
    const selected=[...byFixture.values()].sort((a,b)=>
      (b.iso+' '+b.time).localeCompare(a.iso+' '+a.time));

    const labels={
      barca:'Bar\u00e7a \u00b7 Temporada',
      celoni:'CP Sant Celoni \u00b7 Temporada',
      grupalevi:'Mag\u00ed \u00b7 Bar\u00e7a Alev\u00ed OR 3 \u00b7 Temporada',
      grupinfantil:'Ton \u00b7 CP Sant Celoni B Infantil OR 10 \u00b7 Temporada'
    };
    // Actualitzar sempre els titols, fins si les targetes ja estan pintades.
    if($('#results-title'))$('#results-title').textContent=labels[tab];
    if($('#results-note'))$('#results-note').textContent=
      selected.length+' partits \u00b7 Temporada '+seasonName+
      ' \u00b7 Agenda FECAPA. M\u00e9s recents primer.';
    if($('#open-fecapa'))$('#open-fecapa').onclick=()=>window.open(
      seasonId?ROOT+'?liga='+seasonId+'&vista=calendar':AGENDA,'_blank','noopener');

    const sig=tab+'|'+JSON.stringify(selected.map(r=>
      [rowKey(r),r.homeScore,r.awayScore,r.venue,r.actaUrl]));
    if(root.dataset.zokV5Sig===sig&&root.querySelector('[data-zok-v5]'))return;
    root.dataset.zokV5Sig=sig;
    const frag=document.createDocumentFragment();
    if(!selected.length){
      const empty=el('div','empty',
        'No hi ha partits d\u2019aquest equip i competici\u00f3 dins de l\u2019agenda de la temporada '+seasonName+'.');
      empty.dataset.zokV5='1';frag.append(empty);
    }
    for(const r of selected)frag.append(card(r,true));
    root.replaceChildren(frag);
  }
  let scheduled=false;
  function draw(){
    scheduled=false;
    const store=read(),list=store.agenda?.rows||[];
    if(!list.length)return; // Sense agenda, app.js segueix funcionant.
    const week=byWeek(list).map(r=>resolved(r,store));
    drawHome(week); // Inici = setmana; no modificar aquest comportament.
    const tab=activeTab();
    // MAI passar la llista setmanal a Magi/Ton: la font son totes les files.
    const all=list.map(r=>resolved(r,store));
    drawList(tab,all,store);
    const last=[store.agenda?.capturedAt,store.scoreUpdates?.capturedAt,
      store.live?.capturedAt].filter(Boolean).sort().pop();
    if($('#data-label'))$('#data-label').textContent='Agenda + En directe \u00b7 Safari';
    if($('#data-age')&&last)$('#data-age').textContent='\u00daltima lectura: '+timestamp(last);
    if($('#total-count'))$('#total-count').textContent=list.length+' partits temporada';
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
        store[kind]={...entry,...curr,
          rows:mergeRows(curr.rows||[],entry.rows),
          capturedAt:[curr.capturedAt,entry.capturedAt].filter(Boolean).sort().pop(),
          season:curr.season||entry.season||'',
          counts:curr.counts||entry.counts||{}};
      }
      for(const id of ['4789','4786']){
        const entry=p.data.seasons?.[id];
        if(entry&&Array.isArray(entry.rows)&&entry.rows.length<=100&&
           String(entry.capturedAt||'')>String(store.seasons?.[id]?.capturedAt||'')){
          store.seasons={...(store.seasons||{}),[id]:{
            ...entry,rows:entry.rows.map(r=>cleanSeasonRow(r,id)).filter(Boolean)}};
        }
      }
      write(store);schedule();
    }catch(_){/* Desconnectat: es conserva la c\u00F2pia local */}
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
      .match.zok-v5:not(.zok-compact) .match-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}
      /* Pista a l'esquerra, calendari petit a la dreta (sense segona fila). */
      .match.zok-v5:not(.zok-compact) .venue{display:flex!important;align-items:center;justify-content:space-between;gap:10px;flex-wrap:nowrap}
      .match.zok-v5:not(.zok-compact) .venue .zok-map-link,
      .match.zok-v5:not(.zok-compact) .venue > strong{flex:1 1 auto;min-width:0;overflow-wrap:anywhere}
      .match.zok-v5 .zok-calendar-btn{appearance:none;-webkit-appearance:none;display:inline-flex;flex:0 0 auto;align-items:center;justify-content:center;min-height:36px;padding:8px 12px;border:1px solid rgba(255,255,255,.2);border-radius:10px;background:#061d33;color:#fff;font:inherit;font-size:12px;font-weight:800;line-height:1.1;white-space:nowrap;cursor:pointer;touch-action:manipulation}
      .match.zok-v5 .zok-calendar-btn:active{transform:translateY(1px);background:#123d60}
      .match.zok-v5 .zok-calendar-btn:focus-visible,.match.zok-v5 .zok-map-link:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
      .match.zok-v5 .venue .zok-map-link{display:inline-flex;align-items:center;color:inherit;text-decoration:none;cursor:pointer;touch-action:manipulation}
      .match.zok-v5 .venue .zok-map-link:hover{text-decoration:underline}
      @media(max-width:380px){.match.zok-v5 .zok-calendar-btn{font-size:11px;padding:8px 9px}.match.zok-v5:not(.zok-compact) .venue{gap:7px}}
    `;document.head.append(style);
    schedule();setTimeout(mergePublished,450);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();
