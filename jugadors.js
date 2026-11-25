(()=>{
'use strict';
const D=window.ZonaOKJugadors,$=id=>document.getElementById(id),el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n};
const search=$('jp-search-panel'),profile=$('jp-profile-panel'),root=$('jp-profile');let scope='favorites',active=null,tab='Resum',membershipKey='',rankingCategory='',photoDb,rankHistory=[];
const read=D.read,byId=id=>D.players.find(p=>p.playerId===id);
function db(){if(!photoDb)photoDb=new Promise((ok,no)=>{const r=indexedDB.open(D.preview?'zonaok-jugadors-preview-photos':'zonaok-jugadors-photos',1);r.onupgradeneeded=()=>r.result.createObjectStore('photos');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});return photoDb}
async function photo(id,method='get',value){const d=await db();return new Promise((ok,no)=>{const t=d.transaction('photos',method==='get'?'readonly':'readwrite'),s=t.objectStore('photos');const r=method==='put'?s.put(value,id):method==='delete'?s.delete(id):s.get(id);t.oncomplete=()=>ok(r.result);t.onerror=()=>no(t.error);t.onabort=()=>no(t.error)})}
function openPhoto(blob,name){
 const dialog=el('dialog','zok-jp-photo-dialog'),url=URL.createObjectURL(blob);
 dialog.setAttribute('aria-label','Foto de '+name);
 const close=btn('✕',()=>dialog.close(),'zok-jp-photo-close');close.setAttribute('aria-label','Tancar foto');
 const img=el('img','zok-jp-photo-full');img.alt='Foto de '+name;img.src=url;
 dialog.append(close,img);document.body.append(dialog);
 dialog.addEventListener('close',()=>{URL.revokeObjectURL(url);dialog.remove()},{once:true});
 dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
 try{dialog.showModal();close.focus()}catch{URL.revokeObjectURL(url);dialog.remove()}
}
async function avatar(id,big=false){
 const n=el('div','zok-jp-avatar'+(big?' big':''),'♙');n.setAttribute('aria-hidden','true');
 try{const blob=await photo(id);if(blob instanceof Blob){
  const url=URL.createObjectURL(blob),img=el('img');img.alt='';img.onload=img.onerror=()=>URL.revokeObjectURL(url);img.src=url;
  if(big){const name=byId(id)?.name||'jugador',button=btn('',()=>openPhoto(blob,name),'zok-jp-avatar big zok-jp-avatar-open');button.setAttribute('aria-label','Ampliar foto de '+name);button.append(img);return button}
  n.replaceChildren(img)
 }}catch{}return n
}
async function imageBlob(file){if(!file||!file.type.startsWith('image/')||file.size>15_000_000)throw Error('Selecciona una imatge de menys de 15 MB.');const url=URL.createObjectURL(file);try{const img=new Image();img.src=url;await img.decode();const c=document.createElement('canvas');c.width=c.height=384;const side=Math.min(img.width,img.height);c.getContext('2d').drawImage(img,(img.width-side)/2,(img.height-side)/2,side,side,0,0,384,384);return await new Promise((ok,no)=>c.toBlob(b=>b?ok(b):no(Error('No es pot preparar la foto.')),'image/jpeg',.82))}finally{URL.revokeObjectURL(url)}}
function btn(label,fn,cls='zok-jp-btn'){const n=el('button',cls,label);n.type='button';n.onclick=fn;return n}
function star(id,callback){const on=read().favorites.includes(id),b=btn(on?'★':'☆',()=>{try{D.fav(id,!read().favorites.includes(id));callback()}catch{alert('No s’ha pogut desar el favorit.')}},'zok-jp-star');b.setAttribute('aria-label',on?'Treure de favorits':'Afegir a favorits');b.setAttribute('aria-pressed',String(on));return b}
function options(id,label,values){const n=$(id),old=n.value;n.replaceChildren();const add=(v,t)=>{const o=el('option','',t);o.value=v;n.append(o)};add('',label);[...new Set(values)].sort((a,b)=>a.localeCompare(b,'ca')).forEach(v=>add(v,v));if([...n.options].some(o=>o.value===old))n.value=old}
function filterOptions(){const club=$('jp-club').value;options('jp-club','Tots els clubs',D.memberships.map(m=>m.clubName));const rows=D.memberships.filter(m=>!club||m.clubName===club);options('jp-team','Tots els equips',rows.map(m=>m.teamName));options('jp-category','Totes les categories',rows.filter(m=>!$('jp-team').value||m.teamName===$('jp-team').value).map(m=>m.groupName))}
function filteredMemberships(id){return D.list(id).filter(m=>[['jp-club','clubName'],['jp-team','teamName'],['jp-category','groupName'],['jp-position','position']].every(([f,k])=>!$(f).value||$(f).value===m[k]))}
const searchInput=$('jp-search'),suggestions=$('jp-suggestions');
let renderToken=0;
function renderSuggestions(rows){
 suggestions.replaceChildren();suggestions.hidden=false;
 suggestions.append(el('p','zok-jp-note',rows.length+' coincidències al catàleg'));
 for(const p of rows.slice(0,8)){
  const ms=filteredMemberships(p.playerId),row=el('div','zok-jp-search-choice'),b=btn('',()=>{searchInput.value='';suggestions.hidden=true;open(p.playerId)},'zok-jp-row-main'),name=el('strong','',p.name);
  if(ms.some(x=>x.position==='goalkeeper'))name.append(el('span','zok-jp-keeper','🥅 Porter'));
  b.append(name,el('small','',[...new Set(ms.map(x=>x.clubName+' · '+x.groupName))].join(' / ')));
  row.append(b,star(p.playerId,renderList));suggestions.append(row);
 }
 if(!rows.length)suggestions.append(el('p','zok-jp-note','Cap jugador coincideix amb la cerca i els filtres.'));
 else if(rows.length>8)suggestions.append(el('p','zok-jp-note','Escriu més lletres per afinar la cerca.'));
}
async function renderList(){
 const token=++renderToken,q=D.norm(searchInput.value),favs=new Set(read().favorites),list=$('jp-list'),count=$('jp-count');
 $('jp-favs').setAttribute('aria-pressed',String(scope==='favorites'));$('jp-all').setAttribute('aria-pressed',String(scope==='all'));
 list.replaceChildren();suggestions.replaceChildren();suggestions.hidden=true;count.hidden=false;list.hidden=false;
 if(!D.loaded){count.textContent='';list.append(el('p','zok-jp-note','Carregant el catàleg…'));return}
 if(q){
  const words=q.split(/\s+/),rows=D.players.filter(p=>(words.length===1?D.norm(p.name).includes(q):words.every(w=>D.norm(p.name).split(/\s+/).some(n=>n.startsWith(w))))&&filteredMemberships(p.playerId).length).sort((a,b)=>a.name.localeCompare(b.name,'ca',{sensitivity:'base'}));
  list.hidden=true;count.hidden=true;renderSuggestions(rows);return;
 }
 const rows=D.players.filter(p=>(scope==='all'||favs.has(p.playerId))&&filteredMemberships(p.playerId).length).sort((a,b)=>a.name.localeCompare(b.name,'ca',{sensitivity:'base'}));
 count.textContent=rows.length+' jugadors'+(rows.length>100?' · primers 100, afina la cerca':'')+(scope==='favorites'?' favorits':D.preview?' de mostra':'');
 if(!rows.length){list.append(el('p','zok-jp-note',scope==='favorites'&&!favs.size?'Encara no tens jugadors favorits. Cerca un nom i marca una estrella.':'Cap jugador coincideix amb els filtres.'));return}
 for(const p of rows.slice(0,100)){const row=el('article','zok-jp-row'),m=filteredMemberships(p.playerId)[0],b=btn('',()=>open(p.playerId),'zok-jp-row-main');const name=el('strong','',p.name);if(filteredMemberships(p.playerId).some(x=>x.position==='goalkeeper'))name.append(el('span','zok-jp-keeper','🥅 Porter'));b.append(name,el('small','',m.clubName+' · '+m.groupName+' · '+(m.position==='goalkeeper'?'Porter':m.position==='field'?'Pista':'Posició no verificada')));const placeholder=el('div','zok-jp-avatar','♙');placeholder.setAttribute('aria-hidden','true');if(token!==renderToken)return;row.append(placeholder,b,star(p.playerId,renderList));list.append(row);avatar(p.playerId).then(a=>{if(token===renderToken&&placeholder.isConnected)placeholder.replaceWith(a)})}}
const CARD_COLORS={Grogues:'yellow',Blaves:'blue',Vermelles:'red'};
function cardSymbol(color){const n=el('span','zok-jp-card-symbol '+color);n.setAttribute('aria-hidden','true');return n}
function stat(label,v){const n=el('div','zok-jp-stat'),shown=v===undefined||v===null?'—':String(v);n.append(el('b','',shown));
 if(CARD_COLORS[label]){const small=el('small','zok-jp-stat-card-icon');small.append(cardSymbol(CARD_COLORS[label]));n.append(small);n.setAttribute('aria-label',label+': '+shown);n.title=label+': '+shown}
 else n.append(el('small','',label));return n
}
function cardCount(label,color,value,partial=false){const item=el('span','zok-jp-team-card-count'),shown=(value??'—')+(partial?'*':'');item.setAttribute('aria-label',label+': '+shown);item.title=label+': '+shown;item.append(cardSymbol(color),el('span','zok-jp-team-card-value',shown));return item}
function card(...nodes){const n=el('article','zok-jp-card');n.append(...nodes);return n}
function open(id,fromRanking=false){if(!byId(id))return;if(!fromRanking)rankHistory=[];active=id;tab='Resum';membershipKey=ALL;rankingCategory='';search.hidden=true;profile.hidden=false;renderProfile();window.scrollTo(0,0)}
function openRankPlayer(id){if(!byId(id))return;if(id!==active)rankHistory.push({id:active,tab,membershipKey,rankingCategory,scroll:window.scrollY});open(id,true)}
function backToRanking(){const prev=rankHistory.pop();if(!prev||!byId(prev.id))return;active=prev.id;tab=prev.tab;membershipKey=prev.membershipKey;rankingCategory=prev.rankingCategory;renderProfile();requestAnimationFrame(()=>window.scrollTo(0,prev.scroll))}
function back(){rankHistory=[];active=null;profile.hidden=true;search.hidden=false;renderList();window.scrollTo(0,0)}
const key=m=>m.leagueId+'|'+m.teamFilterId;
const ALL='all';
const Totals=window.ZonaOKPlayerTotals;
function profileTotals(rows,matches,universe,allMatches){
 const all=universe||D.list(rows[0]?.playerId);
 return Totals.totals(rows,all.length?all:rows,allMatches||uniqueMatches(all.length?all:rows,rows[0]?.playerId));
}
function profileNumbers(rows,matches){
 const numbers=new Set();
 for(const m of rows){
  const n=m.sports?.number;
  if(Number.isInteger(n)&&n>=0)numbers.add(n);
 }
 for(const a of matches){if(Number.isInteger(a.shirtNumber)&&a.shirtNumber>=0)numbers.add(a.shirtNumber)}
 return [...numbers].sort((a,b)=>a-b).join(' / ')||'—';
}
function uniqueMatches(rows,id){const allowed=new Set(rows.map(key)),seen=new Map();for(const a of (D.matchesFor?.(id)||D.appearances)){if(a.playerId===id&&(allowed.has(key(a))||(rows.length===D.list(id).length&&rows.some(m=>m.leagueId===a.leagueId)&&!a.teamFilterId))){const k=a.seasonId+'|'+a.leagueId+'|'+a.matchId;if(!seen.has(k))seen.set(k,a)}}return [...seen.values()].sort((a,b)=>String(b.fixture.date).localeCompare(String(a.fixture.date)))}
// Categoria sencera: conserva el nivell i l'edat, treu únicament el sufix de grup.
const category=Totals.category;
function rankGroups(rows){
 const groups=new Map();for(const x of rows){if(!byId(x.playerId))continue;if(!groups.has(x.playerId))groups.set(x.playerId,[]);groups.get(x.playerId).push(x)}
 const acts=new Map();for(const a of D.appearances){if(!groups.has(a.playerId))continue;if(!acts.has(a.playerId))acts.set(a.playerId,[]);acts.get(a.playerId).push(a)}
 return [...groups].map(([playerId,ms])=>({playerId,ms,club:[...new Set(ms.map(m=>m.clubName).filter(Boolean))].join(' / ')||'—',...Totals.totals(ms,D.list(playerId),acts.get(playerId)||[]).sp}));
}
function rankTable(headers,rows,id){
 const wrap=el('div','zok-jp-rank-wrap'),table=el('table','zok-jp-rank-table'),thead=el('thead'),hr=el('tr'),body=el('tbody');
 headers.forEach(text=>{const th=el('th','',text);th.scope='col';hr.append(th)});thead.append(hr);table.append(thead,body);
 for(const row of rows){const tr=el('tr',row.playerId===id?'zok-jp-rank-current':'');tr.dataset.playerId=row.playerId;row.cells.forEach((v,i)=>{const label=v===null||v===undefined?'—':String(v),td=el('td',i===1?'zok-jp-rank-name':'');if(i===1&&byId(row.playerId)){const link=btn(label,()=>openRankPlayer(row.playerId),'zok-jp-rank-player');link.setAttribute('aria-label','Obrir la fitxa de '+label);td.append(link)}else td.textContent=label;tr.append(td)});body.append(tr)}
 wrap.append(table);root.append(wrap);
}
function renderCategoryRanking(selected,id){
 const categories=new Map();for(const m of selected){const c=category(m);categories.set(c.key,c)}
 if(!categories.size){root.append(el('p','zok-jp-note','No hi ha categories disponibles.'));return}
 if(!categories.has(rankingCategory))rankingCategory=categories.keys().next().value;
 const label=el('label','zok-jp-ranking-filter','Categoria del rànquing'),select=el('select');select.id='jp-ranking-category';
 for(const c of categories.values()){const opt=el('option','',c.label);opt.value=c.key;select.append(opt)}
 select.value=rankingCategory;select.onchange=()=>{rankingCategory=select.value;renderProfile()};label.append(select);root.append(label);
 const c=categories.get(rankingCategory),own=selected.filter(m=>category(m).key===c.key),peers=D.memberships.filter(m=>category(m).key===c.key);
 root.append(el('p','zok-jp-note',c.label+' · Tots els grups de la categoria'+(D.preview?' · Dades de mostra':' · Dades disponibles')));
 if(own.some(m=>m.position==='field'||!m.position)){
  const ranked=rankGroups(peers.filter(m=>m.position==='field'||(!m.position&&Number.isInteger(m.sports?.goals))));
  ranked.sort((a,b)=>(b.goals??-1)-(a.goals??-1)||byId(a.playerId).name.localeCompare(byId(b.playerId).name,'ca'));
  let rank=0,last;const records=ranked.map((x,i)=>{if(x.goals!==last)rank=i+1;last=x.goals;return {playerId:x.playerId,cells:[Number.isInteger(x.goals)?rank:'—',byId(x.playerId).name,x.club,x.goals,x.played]}});
  if(records.length)rankTable(['Pos.','Jugador','Club','Gols','PJ'],records,id);else root.append(el('p','zok-jp-note','No hi ha golejadors disponibles.'));
 }
 if(own.some(m=>m.position==='goalkeeper'))keeperRanking(peers,id);
}

function teamScore(a){
  const f=a.fixture;
  if(!f||!['home','away'].includes(a.side)||![f.homeScore,f.awayScore].every(v=>Number.isInteger(v)&&v>=0))return null;
  return a.side==='home'?[f.homeScore,f.awayScore]:[f.awayScore,f.homeScore];
}
function matchOutcome(a){const f=a.fixture;if(!f||!['home','away'].includes(a.side)||![f.homeScore,f.awayScore].every(v=>Number.isInteger(v)&&v>=0))return 'unknown';const [gf,gc]=a.side==='home'?[f.homeScore,f.awayScore]:[f.awayScore,f.homeScore];return gf>gc?'win':gf<gc?'loss':'draw'}
function keeperStats(matches){
  const acts=matches.filter(a=>a.position==='goalkeeper'), scores=acts.map(teamScore).filter(Boolean),n=scores.length;
  const gf=n?scores.reduce((s,r)=>s+r[0],0):null,gc=n?scores.reduce((s,r)=>s+r[1],0):null;
  return {acts:acts.length,confirmed:acts.filter(a=>a.participation==='played').length,n,gf,gc,diff:n?gf-gc:null,
    wins:n?scores.filter(([f,c])=>f>c).length:null,draws:n?scores.filter(([f,c])=>f===c).length:null,losses:n?scores.filter(([f,c])=>f<c).length:null,
    clean:n?scores.filter(([,c])=>c===0).length:null,
    avgGF:n?gf/n:null,avgGC:n?gc/n:null,winPct:n?scores.filter(([f,c])=>f>c).length/n*100:null};
}
const decimal=n=>n==null?null:n.toLocaleString('ca',{minimumFractionDigits:2,maximumFractionDigits:2});
function keeperBlock(matches,sp,detail){
 const k=keeperStats(matches);root.append(el('h3','zok-jp-gold','🥅 Estadístiques de porter'));
 const grid=el('div','zok-jp-grid');
 const stats=[['PJ federatius',sp.played],['Actes com a porter',k.acts],['Amb resultat',k.n],['GF equip',k.gf],['GC equip',k.gc],['Diferència',k.diff],['GF / partit',decimal(k.avgGF)],['GC / partit',decimal(k.avgGC)],['Porteria a zero equip',k.clean],['Victòries',k.wins],['Empats',k.draws],['Derrotes',k.losses],['Victòries %',k.winPct==null?null:decimal(k.winPct)+'%'],['Participació confirmada',k.confirmed]];
 if(detail)stats.push(['Grogues',sp.yellowCards],['Blaves',sp.blueCards],['Vermelles',sp.redCards]);
 stats.forEach(x=>grid.append(stat(...x)));root.append(grid);
 root.append(el('p','zok-jp-note','Cobertura: '+k.n+' de '+k.acts+' actes amb resultat. GF i GC són els de l’equip en partits on el porter consta a l’acta, no gols individuals encaixats. Les mitjanes divideixen pels partits amb resultat.'));
 if(detail)root.append(card(el('p','zok-jp-note','Aturades, minuts, gols encaixats individuals i percentatge d’aturades: — (no verificats). No s’infereixen del marcador.')));
}
function keeperRanking(peers,id){
 root.append(el('h3','zok-jp-gold','🥅 Comparativa de porters'),el('p','zok-jp-note','Ordenat per GC de l’equip / partit amb resultat. No és un rànquing d’aturades ni de rendiment individual. Es mostra la cobertura.'));
 const ranked=rankGroups(peers.filter(m=>m.position==='goalkeeper')).map(x=>({...x,k:keeperStats(uniqueMatches(x.ms,x.playerId))}));
 ranked.sort((a,b)=>(a.k.avgGC??Infinity)-(b.k.avgGC??Infinity)||b.k.n-a.k.n||byId(a.playerId).name.localeCompare(byId(b.playerId).name,'ca'));
 let rank=0,last;const records=ranked.map((x,i)=>{if(x.k.avgGC!==last)rank=i+1;last=x.k.avgGC;return {playerId:x.playerId,cells:[x.k.n?rank:'—',byId(x.playerId).name,x.club,x.k.gf,x.k.gc,x.played,decimal(x.k.avgGC),x.k.n+'/'+x.k.acts]}});
 if(records.length)rankTable(['Pos.','Porter','Club','GF','GC','PJ','GC/partit','Actes'],records,id);else root.append(el('p','zok-jp-note','No hi ha resultats verificats per comparar.'));
}

async function renderProfile(){const id=active,p=byId(id);if(!p)return;const rows=D.list(id);if(!rows.length)return;const all=membershipKey===ALL;const catKey=membershipKey.startsWith('cat:')?membershipKey.slice(4):'';const catRows=catKey?rows.filter(x=>category(x).key===catKey):[];const m=rows.find(x=>key(x)===membershipKey)||catRows[0]||rows[0];const catMode=catRows.length>0;membershipKey=all?ALL:catMode?'cat:'+catKey:key(m);const selected=all?rows:catMode?catRows:[m],match=uniqueMatches(selected,id),allMatches=uniqueMatches(rows,id),totals=profileTotals(selected,match,rows,allMatches),sp=totals.sp;const keeperRows=selected.filter(x=>x.position==='goalkeeper'),fieldRows=selected.filter(x=>x.position==='field'),keeper=keeperRows.length>0;const positions=[...new Set(selected.map(x=>x.position))];const position=positions.length!==1?'Diverses posicions':positions[0]==='goalkeeper'?'Porter':positions[0]==='field'?'Jugador de pista':'Posició no verificada';root.replaceChildren();const head=el('div','zok-jp-profile-title');const backButtons=el('div','zok-jp-profile-back');backButtons.append(btn('← Cercador',back));if(rankHistory.length)backButtons.append(btn('← Rànquing',backToRanking));head.append(backButtons,star(id,renderProfile));root.append(head);
const hero=el('div','zok-jp-hero'),avatarHost=el('div'),info=el('div');hero.append(avatarHost,info);info.append(el('h2','',p.name),el('p','zok-jp-gold','Dorsal '+profileNumbers(selected,match)+' · '+position),el('p','zok-jp-note',(p.birthYear??'—')+' · '+m.seasonName),el('p','zok-jp-note',(all?'Tots els equips · '+rows.length+' vinculacions':catMode?category(m).label+' · Tots els grups':m.clubName+' · '+m.groupName)));root.append(hero);avatar(id,true).then(a=>avatarHost.replaceChildren(a));
const controls=el('div','zok-jp-photo-controls'),input=el('input');input.type='file';input.accept='image/*';input.hidden=true;const message=el('p','zok-jp-note','Foto privada en aquest dispositiu. No s’envia al servidor.');input.onchange=async()=>{try{await photo(id,'put',await imageBlob(input.files[0]));if(active===id)renderProfile()}catch(e){message.textContent=e.message||'No s’ha pogut desar la foto.'}finally{input.value=''}};const photoButton=btn('',()=>input.click(),'zok-jp-btn zok-jp-camera');photoButton.title='Pujar imatge';photoButton.setAttribute('aria-label','Pujar imatge');const camera=document.createElementNS('http://www.w3.org/2000/svg','svg');camera.setAttribute('viewBox','0 0 24 24');camera.setAttribute('fill','none');camera.setAttribute('stroke','currentColor');camera.setAttribute('stroke-width','1.8');camera.setAttribute('stroke-linejoin','round');camera.setAttribute('aria-hidden','true');const outline=document.createElementNS(camera.namespaceURI,'path');outline.setAttribute('d','M3 7h4l2-3h6l2 3h4v13H3z');const lens=document.createElementNS(camera.namespaceURI,'circle');lens.setAttribute('cx','12');lens.setAttribute('cy','13');lens.setAttribute('r','4');camera.append(outline,lens);photoButton.append(camera,el('span','','Pujar imatge'));controls.append(photoButton,btn('Eliminar foto',async()=>{try{await photo(id,'delete');if(active===id)renderProfile()}catch{message.textContent='No s’ha pogut eliminar la foto.'}}),input);const official=selected.filter(x=>x.profileUrl);if(!D.preview&&official.length){const links=[...new Map(official.map(x=>[x.profileUrl,x])).values()];if(links.length===1){const l=el('a','zok-jp-btn zok-jp-fecapa','Fitxa FECAPA');l.href=links[0].profileUrl;l.target='_blank';l.rel='noopener';controls.append(l)}else{const picker=el('details','zok-jp-fecapa-picker'),summary=el('summary','zok-jp-btn zok-jp-fecapa','Fitxa FECAPA'),menu=el('div','zok-jp-fecapa-menu');for(const x of links){const l=el('a','zok-jp-btn',x.teamName+' · '+x.groupName);l.href=x.profileUrl;l.target='_blank';l.rel='noopener';menu.append(l)}picker.append(summary,menu);controls.append(picker)}}root.append(controls,message);
const label=el('label','','Equip i competició'),sel=el('select');sel.id='jp-membership';const totalOption=el('option','','Tots els equips');totalOption.value=ALL;sel.append(totalOption);const categories=new Map(rows.map(x=>[category(x).key,category(x)]));for(const c of categories.values()){const o=el('option','',c.label+' · Tots els grups');o.value='cat:'+c.key;sel.append(o)}rows.forEach(x=>{const o=el('option','',x.teamName+' · '+x.groupName);o.value=key(x);sel.append(o)});sel.value=membershipKey;sel.onchange=()=>{membershipKey=sel.value;rankingCategory='';renderProfile()};label.append(sel);root.append(label);
const nav=el('div','zok-jp-segment zok-jp-profile-tabs');['Resum','Partits','Equips','Estadístiques','Rànquings'].forEach(t=>{const b=btn(t==='Rànquings'?'Rànquing':t,()=>{tab=t;renderProfile()});b.setAttribute('aria-pressed',String(t===tab));nav.append(b)});root.append(nav);
if((tab==='Resum'||tab==='Estadístiques')&&keeper){
 keeperBlock(match,profileTotals(keeperRows,uniqueMatches(keeperRows,id)).sp,tab==='Estadístiques');
 if(fieldRows.length){root.append(el('h3','','Jugador de pista'));const fs=profileTotals(fieldRows,uniqueMatches(fieldRows,id)).sp,g=el('div','zok-jp-grid');[['PJ',fs.played],['Gols',fs.goals],['Assist.',fs.assists]].forEach(x=>g.append(stat(...x)));root.append(g)}
}
else if(tab==='Resum'||tab==='Estadístiques'){const grid=el('div','zok-jp-grid');const ratio=sp.played>0&&Number.isInteger(sp.goals)?(sp.goals/sp.played).toLocaleString('ca',{minimumFractionDigits:2,maximumFractionDigits:2}):undefined;[['PJ',sp.played],['Gols',sp.goals],['Gols/PJ',ratio],['Assist.',sp.assists],['Grogues',sp.yellowCards],['Blaves',sp.blueCards],['Vermelles',sp.redCards],['Capità (actes)',match.filter(a=>a.captain).length],['Consta a l’acta',match.length]].forEach(x=>grid.append(stat(...x)));root.append(grid);if(tab==='Resum'&&match.some(a=>Number.isInteger(a.stats.goals))){root.append(el('h3','','Evolució golejadora · actes disponibles'));const spark=el('div','zok-jp-spark');for(const a of [...match].reverse().filter(a=>Number.isInteger(a.stats.goals))){const col=el('div','',String(a.stats.goals));col.style.height=Math.max(12,Math.min(100,a.stats.goals*24))+'%';spark.append(col)}root.append(spark)}if(tab==='Estadístiques')root.append(card(el('p','zok-jp-note','Penals, faltes directes, aturades i minuts: — (no verificats).')))}
if((tab==='Resum'||tab==='Estadístiques')&&(totals.partial.length||totals.possibleOverlap)){const labels={played:'PJ',goals:'gols',assists:'assistències',yellowCards:'grogues',blueCards:'blaves',redCards:'vermelles'};root.append(el('p','zok-jp-note',(totals.partial.length?'Dades parcials: '+totals.partial.map(k=>labels[k]).join(', ')+'. Només dades atribuïbles a l’equip o categoria; les actes incompletes no es compten com a totals verificats. — = sense dades. ':'')+(totals.possibleOverlap?'Hi ha diversos equips a la mateixa lliga; els totals federatius podrien solapar-se.':'')))}
if(tab==='Partits'){
 if(!match.length)root.append(el('p','zok-jp-note','No hi ha partits disponibles per a aquesta vinculació.'));
 for(const a of match){
  const matchCard=card();const content=el('div','zok-jp-match-content'),side=el('div','zok-jp-match-side');content.append(el('strong','',a.fixture.date+' · '+a.fixture.rival));const outcome=matchOutcome(a),score=el('strong','zok-jp-match-score '+outcome,a.fixture.result||'— : —');score.setAttribute('aria-label',({win:'Victòria',loss:'Derrota',draw:'Empat',unknown:'Resultat no verificat'})[outcome]+': '+(a.fixture.result||'— : —'));side.append(score);
  matchCard.classList.add('zok-jp-match-card');
  const statsLine=el('div','zok-jp-match-stats');
  statsLine.append(el('span','zok-jp-gold',a.position==='goalkeeper'?(teamScore(a)?'GF equip '+teamScore(a)[0]+' · GC equip '+teamScore(a)[1]:'Resultat no verificat')+(a.participation==='played'?' · Participació confirmada':' · Consta a l’acta'):(a.stats.goals??'—')+' gols · '+(a.stats.assists??'—')+' assist.'));
  const cards=el('span','zok-jp-match-card-counts');for(const [k,label,color] of [['yellowCards','Grogues','yellow'],['blueCards','Blaves','blue'],['redCards','Vermelles','red']])cards.append(cardCount(label,color,a.stats[k]));statsLine.append(cards);content.append(statsLine);
  const foot=el('div','zok-jp-match-foot');foot.append(el('p','zok-jp-note',((all||catMode)?(rows.find(x=>key(x)===key(a))?.groupName||a.teamName)+' · ':'')+'Dorsal '+(a.shirtNumber??'—')+(a.captain?' · Capità':'')+' · '+(a.position==='goalkeeper'?'Porter':a.position==='field'?'Pista':'Posició no verificada')));
  const actaUrl=window.ZonaOKActaLinks.savedUrl(a);if(actaUrl){const l=btn('Acta',()=>window.ZonaOKActaFitxa.open({...a,iso:a.fixture.date,home:a.side==='home'?a.teamName:a.fixture.rival,away:a.side==='away'?a.teamName:a.fixture.rival,homeScore:a.fixture.homeScore,awayScore:a.fixture.awayScore,competition:rows.find(x=>key(x)===key(a))?.groupName},actaUrl));side.append(l)}
  content.append(foot);matchCard.append(content,side);root.append(matchCard);
 }
}
else if(tab==='Equips'){
 for(const x of selected){
  const acts=uniqueMatches([x],id).filter(a=>key(a)===key(x)||(!a.teamFilterId&&a.leagueId===x.leagueId&&rows.filter(m=>m.leagueId===x.leagueId).length===1));
  const totals=profileTotals([x],acts,rows,allMatches),line=el('div','zok-jp-team-cards');
  const teamHead=el('div','zok-jp-team-head'),played=el('strong','zok-jp-team-pj',(totals.sp.played??'—')+' PJ'+(totals.partial.includes('played')&&Number.isInteger(totals.sp.played)?'*':''));
  teamHead.append(el('strong','zok-jp-team-name',x.teamName),played);
  const teamCard=card(teamHead,el('p','zok-jp-gold',x.groupName),el('p','zok-jp-note',(x.position==='goalkeeper'?'🥅 Porter · ':'')+x.seasonName));
  for(const [k,label,color] of [['yellowCards','Grogues','yellow'],['blueCards','Blaves','blue'],['redCards','Vermelles','red']]){
   const value=totals.sp[k],partial=totals.partial.includes(k)&&Number.isInteger(value);
   line.append(cardCount(label,color,value,partial));
  }
  const goals=el('strong','zok-jp-team-goals',(totals.sp.goals??'—')+' gols'+(totals.partial.includes('goals')&&Number.isInteger(totals.sp.goals)?'*':''));
  line.append(goals);teamCard.append(line);
  if(['played','goals','yellowCards','blueCards','redCards'].some(k=>totals.partial.includes(k)&&Number.isInteger(totals.sp[k])))teamCard.append(el('p','zok-jp-note','* Dades parcials de les actes disponibles.'));
  root.append(teamCard);
 }
}
else if(tab==='Rànquings')renderCategoryRanking(selected,id)}
$('jp-favs').onclick=()=>{scope='favorites';searchInput.value='';renderList()};$('jp-all').onclick=()=>{scope='all';searchInput.value='';renderList()};searchInput.oninput=renderList;searchInput.addEventListener('keydown',e=>{if(e.key==='Escape'){searchInput.value='';renderList()}else if(e.key==='Enter'&&!suggestions.hidden){const first=suggestions.querySelector('.zok-jp-row-main');if(first){e.preventDefault();first.click()}}});['jp-club','jp-team','jp-category','jp-position'].forEach(k=>$(k).onchange=()=>{filterOptions();renderList()});filterOptions();renderList();
function openRequestedPlayer(){const id=new URLSearchParams(location.search).get('playerId');if(id&&byId(id)&&!active){open(id);return true}return false}
window.ZonaOKOpenActaPlayer=id=>{if(!byId(id))return false;open(id);return true};
openRequestedPlayer();
window.addEventListener('zonaok:jugadors-loaded',()=>{filterOptions();if(openRequestedPlayer())return;if(active&&byId(active)&&D.list(active).length){renderProfile();return}rankHistory=[];active=null;profile.hidden=true;search.hidden=false;renderList()});
window.addEventListener('pageshow',e=>{if(e.persisted)active?renderProfile():renderList()});
})();
