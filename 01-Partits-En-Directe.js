/* Safari → Compartir. Llegeix el DOM de FECAPA, sense fetch ni APIs. */
completion((()=>{try{
const APP='https://carlesjfontanillas-beep.github.io/ZonaOK/';
if(!/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(location.hostname))throw Error('Obre FECAPA a Safari.');
const clean=x=>String(x||'').replace(/\s+/g,' ').trim(), text=e=>clean(e?.innerText), rows=[];
const root=document.querySelector('#sidgad-seccion-partidos');
if(!root||!text(root))throw Error('Obre En directe i espera que aparegui el llistat de partits.');
const season=document.querySelector('#sidgad-season-selector')?.selectedOptions[0]?.textContent||'';
const years=season.match(/(20\d{2})\s*[\/-]\s*(20\d{2})/);
if(!years)throw Error('No puc verificar la temporada seleccionada.');
const logo=e=>{try{const u=new URL(e?.querySelector('img')?.getAttribute('src')||'',location.href);return u.protocol==='https:'&&u.hostname==='sidgad.cloud'&&u.pathname.startsWith('/fecapa/images/logos_clubes/')?u.href:''}catch(_){return ''}};
const club=(name,src)=>name==='BAR'&&/\/234\.png$/i.test(src)?'barca':name==='CPSC'&&/\/281\.png$/i.test(src)?'celoni':'';
for(const el of root.querySelectorAll('.sidgad-partido-fila')){
 const h=el.querySelector('.sidgad-local'),a=el.querySelector('.sidgad-visitante');
 const home=text(h?.querySelector('.sidgad-equipo-nombre')),away=text(a?.querySelector('.sidgad-equipo-nombre'));
 const homeLogo=logo(h),awayLogo=logo(a),homeClub=club(home,homeLogo),awayClub=club(away,awayLogo);
 if(!homeClub&&!awayClub)continue;
 const d=text(h?.querySelector('.sidgad-equipo-sub')).match(/^(\d{2})\/(\d{2})\s+(\d{2}:\d{2})$/);
 if(!d)throw Error('Un partit del club té una data no reconeguda. No s’ha importat parcialment.');
 const year=+d[2]>=7?years[1]:years[2],iso=year+'-'+d[2]+'-'+d[1];
 const header=el.closest('.sidgad-liga-grupo')?.querySelector('.sidgad-liga-header-separador');
 const competition=clean([...header?.childNodes||[]].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' '));
 const score=text(el.querySelector('.sidgad-resultado-texto')).match(/^(\d{1,3})\s*-\s*(\d{1,3})$/);
 rows.push({iso,time:d[3],home,away,homeLogo,awayLogo,homeClub,awayClub,competition,round:text(a?.querySelector('.sidgad-equipo-sub')),status:text(el.querySelector('.sidgad-status-tag')),homeScore:score?+score[1]:null,awayScore:score?+score[2]:null});
}
if(!rows.length)throw Error('No hi ha partits identificables de Barça o CP Sant Celoni al llistat carregat.');
const payload={source:'FECAPA-SAFARI',version:3,kind:'live',season:clean(season),capturedAt:new Date().toISOString(),url:location.href,rows};
const link=APP+'#fecapa='+encodeURIComponent(JSON.stringify(payload));
if(link.length>24500)throw Error('La importació supera la mida segura. No s’han retallat partits.');
return link;
}catch(e){return 'https://carlesjfontanillas-beep.github.io/ZonaOK/?error='+encodeURIComponent(e.message)}})());
