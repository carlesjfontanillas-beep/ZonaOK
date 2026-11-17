/* ZonaOK Safari Bridge — importacions només de FECAPA. No fa peticions externes */
'use strict';
(() => {
 const key='ZONAOK_FECAPA_SAFARI_V1';
 const allowed={'4789':'Aleví Barça · FECAPA 4789','4786':'Infantil B · FECAPA 4786','4784':'Juvenil B · FECAPA 4784'};
 const el=document.getElementById('safari-matches');
 const counter=document.getElementById('safari-count');
 const hint=document.getElementById('safari-help');
 const safe=s=>String(s||'').trim();
 const read=()=>{try{return JSON.parse(localStorage.getItem(key)||'{}')}catch(_){return {}}};
 const persist=data=>{try{localStorage.setItem(key,JSON.stringify(data));return true}catch(_){return false}};
 const create=(tag,cls,txt)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(txt!==undefined)n.textContent=txt;return n};
 function show(){
  el.replaceChildren();const saved=read();let total=0;
  for(const id of ['4789','4786','4784']){
   const block=saved[id];if(!block||!Array.isArray(block.rows))continue;
   const heading=create('div','safari-entry'); heading.append(create('b','',allowed[id]));
   heading.append(create('p','',`Lectura de Safari: ${safe(block.capturedAt)} · ${block.rows.length} files`));el.append(heading);
   for(const row of block.rows){
    total++;const card=create('div','safari-entry');
    const date=safe(row.date);card.append(create('small','',date||'Data no identificada'));
    card.append(create('p','',safe(row.text)||'Fila buida'));
    el.append(card);
   }
  }
  counter.textContent=total?`${total} files`:'Sense dades';
  if(!total){el.append(create('p','safari-empty','Encara no s’han importat partits.'));}
 }
 function loadHash(){
  const hash=location.hash.slice(1);
  if(!hash.startsWith('fecapa='))return;
  // Eliminar el fragment després de la lectura per no deixar dades a l’historial / captures.
  try{history.replaceState(null,'',location.pathname+location.search)}catch(_){ }
  try{
    const payload=JSON.parse(decodeURIComponent(hash.slice(7)));
    if(!payload||payload.source!=='FECAPA-SAFARI'||!Object.prototype.hasOwnProperty.call(allowed,String(payload.league))) throw Error('Font o lliga incorrecta');
    if(!Array.isArray(payload.rows)||payload.rows.length>250)throw Error('Files invàlides');
    const rows=payload.rows.filter(r=>r&&typeof r.text==='string').map(r=>({date:safe(r.date).slice(0,30),text:safe(r.text).slice(0,400)}));
    if(!rows.length)throw Error('No s’han trobat files; no s’han desat canvis');
    const saved=read();saved[String(payload.league)]={capturedAt:safe(payload.capturedAt).slice(0,40),rows};
    if(!persist(saved))throw Error('Safari impedeix desar dades en aquest context');
    hint.textContent=`Importades ${rows.length} files de FECAPA a ZonaOK. Dades capturades a Safari, no actualitzades automàticament.`;
    show();
  }catch(e){hint.textContent='No s’han pogut importar les dades: '+(e.message||e);hint.classList.add('safari-alert');}
 }
 document.getElementById('safari-clear').addEventListener('click',()=>{if(confirm('Vols esborrar les dades importades de FECAPA d’aquest iPhone?')){localStorage.removeItem(key);hint.textContent='Dades esborrades.';show();}});
 document.getElementById('safari-read-guide').addEventListener('click',()=>{alert('1. Obre FECAPA amb Safari.\n2. Executa Compartir → Prova FECAPA amb el codi de la guia.\n3. La drecera obrirà ZonaOK amb les files llegides.\n\nAixò NO funciona automàticament des de GitHub Pages.');});
 show();loadHash();
})();
