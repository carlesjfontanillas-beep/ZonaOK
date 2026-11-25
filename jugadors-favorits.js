(()=>{
'use strict';
const D=window.ZonaOKJugadors,host=document.getElementById('jugadors-favorits');if(!D||!host)return;
const el=(t,c,s)=>{const n=document.createElement(t);if(c)n.className=c;if(s!==undefined)n.textContent=s;return n};
const btn=(s,f)=>{const b=el('button','zok-jp-btn',s);b.type='button';b.onclick=f;return b};
const byName=(a,b)=>a.name.localeCompare(b.name,'ca',{sensitivity:'base'});
const matches=(p,q)=>{const words=q.split(/\s+/),name=D.norm(p.name);return words.length===1?name.includes(q):words.every(w=>name.split(/\s+/).some(n=>n.startsWith(w)))};
function playerText(p,teamId){const txt=el('span','zok-jp-choice-text'),name=el('strong','',p.name);const ms=D.list(p.playerId).filter(m=>!teamId||D.teamMatches(m,teamId));if(ms.some(m=>m.position==='goalkeeper'))name.append(el('span','zok-jp-keeper','🥅 Porter'));txt.append(name,el('small','',[...new Set(ms.map(m=>m.clubName+' · '+m.groupName))].join(' / ')));return txt}
const heading=el('h2','','Jugadors'),note=el('p','zok-jp-note','Escriu el nom del jugador per afegir-lo a Favorits.'),input=el('input');
input.type='search';input.placeholder='Escriu nom o cognoms…';input.setAttribute('aria-label','Cerca jugadors favorits');input.autocomplete='off';
const results=el('div','zok-jp-fav-results'),searchLine=el('div','zok-jp-search-line'),importHost=document.getElementById('jp-data-status');
searchLine.append(input);if(importHost)searchLine.append(importHost);host.append(heading,note,searchLine,results);
let limit=40,lastQuery='';
function render(){
 const q=D.norm(input.value),selected=new Set(D.read().favorites);if(q!==lastQuery){limit=40;lastQuery=q}results.replaceChildren();
 if(!D.loaded){results.append(el('p','zok-jp-note','Catàleg de jugadors encara no carregat.'));return}
 const found=D.players.filter(p=>q?matches(p,q):selected.has(p.playerId)).sort((a,b)=>Number(selected.has(b.playerId))-Number(selected.has(a.playerId))||byName(a,b));
 if(!found.length){results.append(el('p','zok-jp-note',q?'Cap coincidència.':'Cap jugador seleccionat.'));return}
 const list=el('div',q?'zok-jp-suggestions':'zok-jp-selected-list');list.setAttribute('aria-label',q?'Coincidències de jugadors':'Jugadors seleccionats');
 for(const p of (q?found.slice(0,limit):found)){
  const row=el('label','zok-jp-row'),c=el('input');c.type='checkbox';c.checked=selected.has(p.playerId);c.setAttribute('aria-label',p.name);
  c.onchange=()=>{try{if(c.checked)input.value='';D.fav(p.playerId,c.checked);render()}catch{note.textContent='No s’ha pogut desar la selecció.';render()}};
  row.append(c,playerText(p));list.append(row)
 }
 if(q){list.prepend(el('p','zok-jp-note',found.length+' coincidències de tot el catàleg'));if(found.length>limit){const more=btn('Mostra més jugadors ('+(found.length-limit)+' restants)',()=>{const old=list.scrollTop;limit+=40;render();const next=results.querySelector('.zok-jp-suggestions');if(next)next.scrollTop=old});list.append(more)}}results.append(list);
}
function mount(){
 document.querySelectorAll('.zok-jp-team-picker:not([data-mounted])').forEach(box=>{
  box.dataset.mounted='1';if(!D.loaded)return;
  const id=box.dataset.teamId,existing=box.dataset.originalName;if(D.preview&&D.ensureTeam?.(id)){render();const marker=document.querySelector('#jugadors-favorits .zok-jp-mode-row .zok-jp-note');if(marker)marker.textContent='Catàleg de prova · '+D.players.length+' jugadors ficticis'}const eligible=D.players.filter(p=>D.list(p.playerId).some(m=>D.teamMatches(m,id))).sort(byName);
  const q=el('input');q.type='search';q.placeholder='Cerca jugador de l’equip…';q.setAttribute('aria-label','Cerca jugador de '+box.dataset.teamLabel);q.autocomplete='off';
  const picked=el('div','zok-jp-picked'),opts=el('div','zok-jp-picker-options zok-jp-suggestions');
  box.append(q,picked,opts);box.addEventListener('click',e=>e.stopPropagation());
  function show(){
   const selected=D.read().teamPlayers[id],p=D.players.find(p=>p.playerId===selected);
   picked.replaceChildren();
   if(p){picked.append(el('span','','Seleccionat: '+p.name),btn('×',()=>{D.assign(id,'');q.value='';show();render()}));picked.lastChild.setAttribute('aria-label','Treure selecció');picked.lastChild.title='Treure selecció'}
   else if(existing)picked.append(el('span','zok-jp-note','Nom actual: '+existing+' · es conserva'));
   picked.hidden=!picked.childNodes.length;
   opts.replaceChildren();const query=D.norm(q.value);opts.hidden=!query;if(!query)return;
   const found=eligible.filter(p=>matches(p,query));
   for(const p of found.slice(0,8)){const b=btn('',()=>{q.value='';D.assign(id,p.playerId);show();render()});b.append(playerText(p,id));opts.append(b)}
   if(!found.length)opts.append(el('p','zok-jp-note','Cap jugador coincideix.'));
   else if(found.length>8)opts.append(el('p','zok-jp-note','Escriu més lletres.'));
  }
  q.oninput=show;q.addEventListener('keydown',e=>{if(e.key==='Escape'){q.value='';show()}});show()
 })
}
window.addEventListener('zonaok:jugadors-loaded',()=>{document.querySelectorAll('.zok-jp-team-picker').forEach(b=>{b.replaceChildren();delete b.dataset.mounted});render();mount()});
input.oninput=render;input.addEventListener('keydown',e=>{if(e.key==='Escape'){input.value='';render()}});
window.addEventListener('zonaok:team-pickers-rendered',mount);window.addEventListener('zonaok:jugadors-preferences',render);render();mount();
})();
