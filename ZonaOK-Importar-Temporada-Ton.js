/* ZonaOK · Temporada completa CP Sant Celoni B Infantil OR 10 (FECAPA, lliga 4786) */
completion((()=>{try{
const ID='4786',GROUP='INFANTIL OR 10';
const APP='https://carlesjfontanillas-beep.github.io/ZonaOK/?v=20261118-season-import';
if(!/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(location.hostname)||new URLSearchParams(location.search).get('liga')!==ID)throw Error('Obre FECAPA Infantil OR 10, pestanya Calendari i resultats.');
const clean=x=>String(x||'').replace(/\s+/g,' ').trim(),norm=x=>clean(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Z0-9]+/gi,' ').trim().toUpperCase();
const heading=[...document.querySelectorAll('h1,h2,h3')].find(e=>norm(e.innerText)===GROUP);
if(!heading)throw Error('No trobo el grup INFANTIL OR 10. Selecciona Calendari i resultats i espera que carregui.');
function tableAfter(h){for(const base of [h,h.parentElement,h.parentElement?.parentElement]){let n=base;for(let i=0;i<4&&n;i++,n=n.nextElementSibling){if(n.matches?.('table'))return n;const t=n.querySelector?.('table');if(t)return t;}}return null;}
const table=tableAfter(heading);if(!table)throw Error('No trobo la taula de partits del grup.');
const date=x=>{const m=clean(x).match(/^(\d{1,2})[/. -](\d{1,2})[/. -](20\d{2})$/);if(!m)return '';const iso=`${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`,d=new Date(iso+'T12:00:00Z');return d.toISOString().slice(0,10)===iso?iso:''};
const toId=row=>{const nodes=[...row.querySelectorAll('a,button,[role="button"],[data-partido],[data-match-id],[data-id]')];for(const e of nodes){const label=norm(e.getAttribute('aria-label')||e.getAttribute('title')||e.innerText);if(!/DETALL|ACTA|PARTIT|PARTIDO/.test(label)&&!e.hasAttribute('data-partido')&&!e.hasAttribute('data-match-id'))continue;const href=e.getAttribute('href')||'',onclick=e.getAttribute('onclick')||'';const direct=(href+' '+onclick).match(/[?&]partido=(\d+)/i);if(direct)return direct[1];for(const k of ['data-partido','data-match-id','data-id']){const v=e.getAttribute(k);if(/^\d{4,}$/.test(v||''))return v;}}return '';};
const rows=[];let examined=0,withScore=0,withActa=0;
for(const tr of table.querySelectorAll('tbody tr')){const values=[...tr.querySelectorAll(':scope > td')].map(c=>clean(c.innerText));if(!values.some(Boolean))continue;examined++;
 const when=values.map(date).find(Boolean)||'';if(!when)continue;const time=values.map(v=>v.match(/\b\d{1,2}:\d{2}\b/)?.[0]).find(Boolean)||'';if(!time)continue;
 const teamNames=[...new Set(values.filter(v=>v&&!date(v)&&!/^\d{1,2}:\d{2}$/.test(v)&&!/\b\d{1,3}\s*[-:–]\s*\d{1,3}\b/.test(v)&&!/^JORNADA\b/i.test(v)&&!/^\d+$/.test(v)))];
 const targetIndex=teamNames.findIndex(v=>norm(v).includes('CELONI'));if(targetIndex<0||!/^CP SANT CELONI B$/.test(norm(teamNames[targetIndex])))continue;
 const home=teamNames[0]||'',away=teamNames[1]||'';if(!home||!away)continue;
 const scoreText=values.slice(2).find(v=>v!==time&&/^\s*\d{1,3}\s*[:–-]\s*\d{1,3}\s*$/.test(v))||'',score=scoreText.match(/^\s*(\d{1,3})\s*[:–-]\s*(\d{1,3})\s*$/);
 const actId=toId(tr),venue=values.find(v=>/PAVELL|POLIESPORT|MUNICIPAL|CAMPUS|PISTA/i.test(v))||'';
 if(score)withScore++;if(actId)withActa++;
 rows.push([when,time.padStart(5,'0'),GROUP,home,away,score?+score[1]:null,score?+score[2]:null,venue,actId]);
}
const unique=new Map(rows.map(r=>[[r[0],r[1],norm(r[3]),norm(r[4])].join('|'),r])),found=[...unique.values()].sort((a,b)=>(a[0]+a[1]).localeCompare(b[0]+b[1]));
if(!found.length)throw Error(`No he llegit partits de CP SANT CELONI B a ${GROUP}. Files examinades: ${examined}. Recarrega la pàgina i prova-ho de nou.`);
const season=document.body.innerText.match(/202\d\s*\/\s*202\d/)?.[0]||'2026/2027',capturedAt=new Date().toISOString();
const payload={source:'FECAPA-SAFARI',v:5,kind:'season-v1',league:ID,season,capturedAt,url:location.href,rows:found};
const url=APP+'#fecapa='+encodeURIComponent(JSON.stringify(payload));if(url.length>7500)throw Error(`La importació (${found.length} partits) supera la mida segura.`);
alert(`Temporada Infantil OR 10 · Sant Celoni B\nFiles examinades: ${examined}\nPartits importats: ${found.length}\nAmb resultat: ${withScore}\nAmb fitxa d’acta: ${withActa}\nTemporada: ${season}`);return url;
}catch(e){return 'https://carlesjfontanillas-beep.github.io/ZonaOK/?error='+encodeURIComponent('Importació Infantil Ton: '+e.message)}})());
