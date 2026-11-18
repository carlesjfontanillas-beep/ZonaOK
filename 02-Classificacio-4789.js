/* '4789' i 'ALEVI OR 3' es fixen per a cada drecera. */
completion((()=>{try{
const id='4789',group='ALEVI OR 3';
if(!/^(www\.)?hoqueipatins\.fecapa\.cat$/.test(location.hostname)||new URLSearchParams(location.search).get('liga')!==id)throw Error('Obre la classificació de la lliga '+id+' a Safari.');
const clean=x=>String(x||'').replace(/\s+/g,' ').trim(),norm=x=>clean(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();
const h=[...document.querySelectorAll('h2')].find(e=>norm(e.innerText)===group);
const table=h?.nextElementSibling?.querySelector('table.sidgad-clasif-tabla');
if(!table||!table.innerText)throw Error('Obre Classificacions i espera que es carregui el grup '+group+'.');
const headers=[];for(const th of table.querySelectorAll('thead th')){headers.push(norm(th.innerText));for(let i=1;i<(th.colSpan||1);i++)headers.push('');}
const col=(...names)=>headers.findIndex(h=>names.includes(h)),pj=col('PJ'),pts=col('PTS','PUNTS'),gf=col('GF','GOLS A FAVOR'),gc=col('GC','GOLS EN CONTRA'),dif=col('DIF','DIFERENCIA','AVG','AVERAGE');
if(pj<0||pts<0)throw Error('Columnes PJ/PTS no reconegudes.');
const rows=[...table.querySelectorAll('tbody tr')].map(tr=>{const c=[...tr.cells];return {pos:clean(c[0]?.innerText),team:clean(tr.querySelector('.sidgad-clasif-nombre')?.textContent),teamId:tr.dataset.teamId||'',played:clean(c[pj]?.innerText),points:clean(c[pts]?.innerText),gf:gf>=0?clean(c[gf]?.innerText):null,ga:gc>=0?clean(c[gc]?.innerText):null,difference:dif>=0?clean(c[dif]?.innerText):null}}).filter(r=>/^\d+$/.test(r.pos)&&r.team);
if(!rows.length)throw Error('Classificació buida.');
return 'https://carlesjfontanillas-beep.github.io/ZonaOK/#fecapa='+encodeURIComponent(JSON.stringify({source:'FECAPA-SAFARI',version:3,kind:'standings',league:id,capturedAt:new Date().toISOString(),url:location.href,rows}));
}catch(e){return 'https://carlesjfontanillas-beep.github.io/ZonaOK/?error='+encodeURIComponent(e.message)}})());
