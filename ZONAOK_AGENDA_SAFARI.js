/* ZonaOK Agenda V6.1 · Safari → FECAPA /ag/ → ZonaOK */
completion((()=>{try{
 const APP='https://carlesjfontanillas-beep.github.io/ZonaOK/?v=20261118-agenda61';
 if(!/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(location.hostname)||!location.pathname.startsWith('/ag'))throw Error('Obre l’agenda oficial FECAPA (/ag/) a Safari.');
 const clean=x=>String(x||'').replace(/\s+/g,' ').trim(),norm=x=>clean(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Z0-9]+/gi,' ').trim().toUpperCase();
 const club=s=>{const n=norm(s);if(/\b(BARCA|FC BARCELONA|FCBETERANS|FCBETRANS)\b/.test(n))return 'barca';if(n.includes('CELONI'))return 'celoni';return '';};
 const tables=[...document.querySelectorAll('table')],headersSeen=[],matches=[];let examined=0,candidates=0;
 const today=new Date(new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())+'T12:00:00Z');
 const monday=new Date(today);monday.setUTCDate(today.getUTCDate()-((today.getUTCDay()+6)%7));const sunday=new Date(monday);sunday.setUTCDate(monday.getUTCDate()+6);
 const iso=d=>d.toISOString().slice(0,10),weekStart=iso(monday),weekEnd=iso(sunday);
 const inWeek=d=>d>=weekStart&&d<=weekEnd;
 function dateValue(s){s=clean(s);let m=s.match(/\b(\d{1,2})[\/. -](\d{1,2})[\/. -](20\d{2})\b/);if(m)return validISO(`${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`);m=s.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/);if(m)return validISO(m[0]);m=s.match(/\b(\d{1,2})[\/. -](\d{1,2})\b/);if(!m)return '';const years=[today.getUTCFullYear()-1,today.getUTCFullYear(),today.getUTCFullYear()+1].map(y=>validISO(`${y}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`)).filter(Boolean);return years.find(inWeek)||years.sort((a,b)=>Math.abs(Date.parse(a)-Date.parse(weekStart))-Math.abs(Date.parse(b)-Date.parse(weekStart)))[0]||'';}
 function validISO(s){const m=String(s).match(/^(20\d{2})-(\d{2})-(\d{2})$/);if(!m)return '';const d=new Date(`${s}T12:00:00Z`);return d.getUTCFullYear()===+m[1]&&d.getUTCMonth()+1===+m[2]&&d.getUTCDate()===+m[3]?s:'';}
 let undatedClubRows=0;
 for(const table of tables){const trs=[...table.querySelectorAll('tr')];if(!trs.length)continue;const headerRow=table.querySelector('thead tr')||trs.find(tr=>tr.querySelector('th'))||null;const headers=headerRow?[...headerRow.querySelectorAll('th,td')].map(e=>clean(e.innerText)):[];headersSeen.push(headers.join(' | '));const h=headers.map(norm);
  const idx=re=>h.findIndex(x=>re.test(x));const di=idx(/DATA|DIA|DATE/),ti=idx(/HORA|HOUR/),hi=idx(/LOCAL|CASA|EQUIP\s*LOCAL|EQUIPO\s*LOCAL|HOME/),ai=idx(/VISITANT|VISITANTE|VISIT|AWAY/),vi=idx(/PISTA|PAVELL|INSTAL|LLOC|SEU/),ci=idx(/COMPET|CATEG|LLIGA|LIGA/),si=idx(/RESULT|MARCADOR|SCORE/);const start=headerRow?trs.indexOf(headerRow)+1:0;
  for(const tr of trs.slice(start)){const cells=[...tr.querySelectorAll(':scope > th, :scope > td')].map(e=>clean(e.innerText));if(!cells.some(Boolean))continue;examined++;const text=cells.join(' · ');let home=hi>=0?cells[hi]||'':'',away=ai>=0?cells[ai]||'':'';
   if(!home||!away){const opts=cells.filter(v=>v&&!dateValue(v)&&!/^\d{1,2}:\d{2}$/.test(v)&&!/\b\d{1,2}\s*[-–:]\s*\d{1,2}\b/.test(v));const named=opts.filter(v=>club(v));if(!home)home=named[0]||opts[0]||'';if(!away)away=named.find(v=>v!==home)||opts.find(v=>v!==home)||'';}
   const homeClub=club(home),awayClub=club(away);if(homeClub||awayClub)candidates++;if(!homeClub&&!awayClub)continue;
   const rawDate=di>=0?cells[di]:'',date=dateValue(rawDate)||dateValue(text);if(!date){undatedClubRows++;continue;}if(!inWeek(date))continue;const time=(ti>=0?cells[ti].match(/\b\d{1,2}:\d{2}\b/)?.[0]:null)||text.match(/\b\d{1,2}:\d{2}\b/)?.[0]||'';if(!/^\d{1,2}:\d{2}$/.test(time))continue;
   const scoreText=si>=0?cells[si]:text,score=scoreText.match(/\b(\d{1,2})\s*[-–:]\s*(\d{1,2})\b/);const venue=vi>=0?cells[vi]||'':'';const competition=ci>=0?cells[ci]||'':'';
   matches.push({iso:date,time:time.padStart(5,'0'),competition,home,away,homeScore:score?+score[1]:null,awayScore:score?+score[2]:null,venue,homeClub,awayClub});
  }
 }
 const unique=new Map();for(const r of matches){const k=[r.iso,r.time,norm(r.home),norm(r.away)].join('|');if(!unique.has(k))unique.set(k,r);}const rows=[...unique.values()].sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time));
 const barca=rows.filter(r=>r.homeClub==='barca'||r.awayClub==='barca').length,celoni=rows.filter(r=>r.homeClub==='celoni'||r.awayClub==='celoni').length,venueNames=[...new Set(rows.map(r=>r.venue).filter(Boolean))],venues=venueNames.length,capturedAt=new Date().toISOString();
 const summary=['ZonaOK Agenda V6.1 · diagnòstic',`Setmana: ${weekStart} → ${weekEnd}`,`Taules examinades: ${tables.length}`,`Files examinades: ${examined}`,`Files amb noms d’algun club: ${candidates}`,`Files d’algun club sense data vàlida (omesses): ${undatedClubRows}`,`Partits del Barça: ${barca}`,`Partits del CP Sant Celoni: ${celoni}`,`Pistes (${venues}): ${venueNames.join(', ')||'cap detectada'}`];
 if(!tables.length)summary.push('Pista: l’agenda no ha carregat cap taula. Torna a carregar /ag/ i espera que es mostrin les files.');
 else if(!rows.length)summary.push('Pista: comprova que Tots els clubs estigui seleccionat i que el període inclogui dilluns–diumenge. Capçaleres: '+(headersSeen.slice(0,3).join(' / ')||'no disponibles'));else if(!venues)summary.push('Pista: no s’ha pogut identificar una columna de pista/pavelló. Capçaleres: '+(headersSeen.slice(0,3).join(' / ')||'no disponibles'));
 const payload={source:'FECAPA-SAFARI',v:5,kind:'agenda-v5',capturedAt,weekStart,weekEnd,counts:{barca,celoni,examined,candidates,tables:tables.length,venues,venueNames},rows:rows.map(r=>[r.iso,r.time,r.competition,r.home,r.away,r.homeScore,r.awayScore,r.venue])};
 const url=APP+'#fecapa='+encodeURIComponent(JSON.stringify(payload));if(url.length>7500)throw Error('La importació supera la mida segura. No s’han retallat partits; redueix la selecció a la setmana actual.');
 try{alert(summary.join('\n'));}catch(_){}return url;
}catch(e){return 'https://carlesjfontanillas-beep.github.io/ZonaOK/?error='+encodeURIComponent('Agenda V6.1: '+e.message)}})());
