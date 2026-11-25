(()=>{
'use strict';
const D=window.ZonaOKJugadors,$=id=>document.getElementById(id),el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n};
const search=$('jp-search-panel'),profile=$('jp-profile-panel'),root=$('jp-profile');let scope='favorites',active=null,tab='Resum',membershipKey='',photoDb;
const read=D.read,byId=id=>D.players.find(p=>p.playerId===id);
function db(){if(!photoDb)photoDb=new Promise((ok,no)=>{const r=indexedDB.open(D.preview?'zonaok-jugadors-preview-photos':'zonaok-jugadors-photos',1);r.onupgradeneeded=()=>r.result.createObjectStore('photos');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});return photoDb}
async function photo(id,method='get',value){const d=await db();return new Promise((ok,no)=>{const t=d.transaction('photos',method==='get'?'readonly':'readwrite'),s=t.objectStore('photos');const r=method==='put'?s.put(value,id):method==='delete'?s.delete(id):s.get(id);t.oncomplete=()=>ok(r.result);t.onerror=()=>no(t.error);t.onabort=()=>no(t.error)})}
async function avatar(id,big=false){const n=el('div','zok-jp-avatar'+(big?' big':''),'♙');n.setAttribute('aria-hidden','true');try{const blob=await photo(id);if(blob instanceof Blob){const url=URL.createObjectURL(blob),img=el('img');img.alt='';img.onload=img.onerror=()=>URL.revokeObjectURL(url);img.src=url;n.replaceChildren(img)}}catch{}return n}
async function imageBlob(file){if(!file||!file.type.startsWith('image/')||file.size>15_000_000)throw Error('Selecciona una imatge de menys de 15 MB.');const url=URL.createObjectURL(file);try{const img=new Image();img.src=url;await img.decode();const c=document.createElement('canvas');c.width=c.height=384;const side=Math.min(img.width,img.height);c.getContext('2d').drawImage(img,(img.width-side)/2,(img.height-side)/2,side,side,0,0,384,384);return await new Promise((ok,no)=>c.toBlob(b=>b?ok(b):no(Error('No es pot preparar la foto.')),'image/jpeg',.82))}finally{URL.revokeObjectURL(url)}}
function btn(label,fn,cls='zok-jp-btn'){const n=el('button',cls,label);n.type='button';n.onclick=fn;return n}
function star(id,callback){const on=read().favorites.includes(id),b=btn(on?'★':'☆',()=>{try{D.fav(id,!read().favorites.includes(id));callback()}catch{alert('No s’ha pogut desar el favorit.')}},'zok-jp-star');b.setAttribute('aria-label',on?'Treure de favorits':'Afegir a favorits');b.setAttribute('aria-pressed',String(on));return b}
function options(id,label,values){const n=$(id),old=n.value;n.replaceChildren();const add=(v,t)=>{const o=el('option','',t);o.value=v;n.append(o)};add('',label);[...new Set(values)].sort((a,b)=>a.localeCompare(b,'ca')).forEach(v=>add(v,v));if([...n.options].some(o=>o.value===old))n.value=old}
function filterOptions(){const club=$('jp-club').value;options('jp-club','Tots els clubs',D.memberships.map(m=>m.clubName));const rows=D.memberships.filter(m=>!club||m.clubName===club);options('jp-team','Tots els equips',rows.map(m=>m.teamName));options('jp-category','Totes les categories',rows.filter(m=>!$('jp-team').value||m.teamName===$('jp-team').value).map(m=>m.groupName))}
function filteredMemberships(id){return D.list(id).filter(m=>[['jp-club','clubName'],['jp-team','teamName'],['jp-category','groupName'],['jp-position','position']].every(([f,k])=>!$(f).value||$(f).value===m[k]))}
let renderToken=0;
async function renderList(){const token=++renderToken;const q=D.norm($('jp-search').value),favs=read().favorites;const rows=D.players.filter(p=>(scope==='all'||favs.includes(p.playerId))&&(!q||D.norm(p.name).includes(q))&&filteredMemberships(p.playerId).length);$('jp-favs').setAttribute('aria-pressed',String(scope==='favorites'));$('jp-all').setAttribute('aria-pressed',String(scope==='all'));$('jp-count').textContent=rows.length+' jugadors'+(rows.length>100?' · primers 100, afina la cerca':'')+(scope==='favorites'?' favorits':D.preview?' de mostra':'');const list=$('jp-list');list.replaceChildren();if(!D.loaded){list.append(el('p','zok-jp-note','Encara no hi ha catàleg carregat.'));return}if(!rows.length){list.append(el('p','zok-jp-note',scope==='favorites'&&!favs.length?'Encara no tens jugadors favorits. Obre Tots els jugadors i marca una estrella.':'Cap jugador coincideix amb els filtres.'));return}for(const p of rows.slice(0,100)){const row=el('article','zok-jp-row'),m=filteredMemberships(p.playerId)[0],b=btn('',()=>open(p.playerId),'zok-jp-row-main');const name=el('strong','',p.name);if(filteredMemberships(p.playerId).some(x=>x.position==='goalkeeper'))name.append(el('span','zok-jp-keeper','🥅 Porter'));b.append(name,el('small','',m.clubName+' · '+m.groupName+' · '+(m.position==='goalkeeper'?'Porter':m.position==='field'?'Pista':'Posició no verificada')));const a=await avatar(p.playerId);if(token!==renderToken)return;row.append(a,b,star(p.playerId,renderList));list.append(row)}}
function stat(label,v){const n=el('div','zok-jp-stat');n.append(el('b','',v===undefined||v===null?'—':String(v)),el('small','',label));return n}
function card(...nodes){const n=el('article','zok-jp-card');n.append(...nodes);return n}
function open(id){active=id;tab='Resum';membershipKey='';search.hidden=true;profile.hidden=false;renderProfile();window.scrollTo(0,0)}
function back(){active=null;profile.hidden=true;search.hidden=false;renderList();window.scrollTo(0,0)}
const key=m=>m.leagueId+'|'+m.teamFilterId;
const ALL='all';
function aggregate(rows){
  const sp={};
  for(const k of ['played','goals','assists','yellowCards','blueCards','redCards']){
    // Do not sum potentially overlapping memberships of the same league.
    if(new Set(rows.map(x=>x.leagueId)).size===rows.length&&rows.every(x=>Number.isInteger(x.sports?.[k])))sp[k]=rows.reduce((n,x)=>n+x.sports[k],0);
  }
  const nums=[...new Set(rows.map(x=>x.sports?.number).filter(Number.isInteger))];
  if(nums.length===1&&rows.every(x=>Number.isInteger(x.sports?.number)))sp.number=nums[0];
  return sp;
}
function uniqueMatches(rows,id){const allowed=new Set(rows.map(key)),seen=new Map();for(const a of D.appearances){if(a.playerId===id&&(allowed.has(key(a))||(rows.length===D.list(id).length&&rows.some(m=>m.leagueId===a.leagueId)&&!a.teamFilterId))){const k=a.seasonId+'|'+a.leagueId+'|'+a.matchId;if(!seen.has(k))seen.set(k,a)}}return [...seen.values()].sort((a,b)=>String(b.fixture.date).localeCompare(String(a.fixture.date)))}
function ranking(rows){rows=rows.filter(x=>x.position==='field');const groups=new Map();for(const x of rows){if(!groups.has(x.playerId))groups.set(x.playerId,[]);groups.get(x.playerId).push(x)}return [...groups].map(([playerId,ms])=>({playerId,goals:aggregate(ms).goals})).filter(x=>Number.isInteger(x.goals)).sort((a,b)=>b.goals-a.goals||byId(a.playerId).name.localeCompare(byId(b.playerId).name,'ca'))}

function teamScore(a){
  const f=a.fixture;
  if(!f||!['home','away'].includes(a.side)||![f.homeScore,f.awayScore].every(v=>Number.isInteger(v)&&v>=0))return null;
  return a.side==='home'?[f.homeScore,f.awayScore]:[f.awayScore,f.homeScore];
}
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
function keeperRanking(selected,id){
 const groups=new Map();
 for(const x of D.memberships.filter(x=>x.position==='goalkeeper'&&selected.some(y=>x.leagueId===y.leagueId&&x.groupName===y.groupName))){if(!groups.has(x.playerId))groups.set(x.playerId,[]);groups.get(x.playerId).push(x)}
 root.append(el('h3','zok-jp-gold','🥅 Comparativa de porters'),el('p','zok-jp-note','Ordenat per GC de l’equip / partit amb resultat. No és un rànquing d’aturades ni de rendiment individual. Es mostra la cobertura.'));
 const peers=[...groups].map(([pid,ms])=>({pid,k:keeperStats(uniqueMatches(ms,pid))})).filter(x=>x.k.n).sort((a,b)=>a.k.avgGC-b.k.avgGC||b.k.n-a.k.n||byId(a.pid).name.localeCompare(byId(b.pid).name,'ca'));
 if(!peers.length)root.append(el('p','zok-jp-note','No hi ha resultats verificats per comparar.'));
 for(const x of peers){const n=card(el('strong','',byId(x.pid).name+' · '+decimal(x.k.avgGC)+' GC/partit equip'),el('p','zok-jp-note',x.k.n+'/'+x.k.acts+' actes amb resultat · '+x.k.gc+' GC equip'));if(x.pid===id)n.style.borderColor='#fbc252';root.append(n)}
}
async function renderProfile(){const id=active,p=byId(id);if(!p)return;const rows=D.list(id),m=rows.find(x=>key(x)===membershipKey)||rows[0];const all=membershipKey===ALL;membershipKey=all?ALL:key(m);const selected=all?rows:[m],match=uniqueMatches(selected,id),sp=all?aggregate(rows):m.sports;const keeperRows=selected.filter(x=>x.position==='goalkeeper'),fieldRows=selected.filter(x=>x.position==='field'),keeper=keeperRows.length>0;const positions=[...new Set(selected.map(x=>x.position))];const position=positions.length!==1?'Diverses posicions':positions[0]==='goalkeeper'?'Porter':positions[0]==='field'?'Jugador de pista':'Posició no verificada';root.replaceChildren();const head=el('div','zok-jp-profile-title');head.append(btn('← Cercador',back),star(id,renderProfile));root.append(head);
const hero=el('div','zok-jp-hero'),avatarHost=el('div'),info=el('div');hero.append(avatarHost,info);info.append(el('h2','',p.name),el('p','zok-jp-gold','Dorsal '+(sp.number??'—')+' · '+position),el('p','zok-jp-note',(p.birthYear??'—')+' · '+m.seasonName),el('p','zok-jp-note',(all?'Tots els equips · '+rows.length+' vinculacions':m.clubName+' · '+m.groupName)));root.append(hero);avatar(id,true).then(a=>avatarHost.replaceChildren(a));
const controls=el('div','zok-jp-photo-controls'),input=el('input');input.type='file';input.accept='image/*';input.hidden=true;const message=el('p','zok-jp-note','Foto privada en aquest dispositiu. No s’envia al servidor.');input.onchange=async()=>{try{await photo(id,'put',await imageBlob(input.files[0]));if(active===id)renderProfile()}catch(e){message.textContent=e.message||'No s’ha pogut desar la foto.'}finally{input.value=''}};controls.append(btn('Afegir / canviar foto',()=>input.click()),btn('Eliminar foto',async()=>{try{await photo(id,'delete');if(active===id)renderProfile()}catch{message.textContent='No s’ha pogut eliminar la foto.'}}),input);root.append(controls,message);
const label=el('label','','Equip i competició'),sel=el('select');const totalOption=el('option','','Tots els equips');totalOption.value=ALL;sel.append(totalOption);rows.forEach(x=>{const o=el('option','',x.teamName+' · '+x.groupName);o.value=key(x);sel.append(o)});sel.value=membershipKey;sel.onchange=()=>{membershipKey=sel.value;renderProfile()};label.append(sel);root.append(label);if(!D.preview&&m.profileUrl&&!all){const l=el('a','zok-jp-btn','Fitxa FECAPA');l.href=m.profileUrl;l.target='_blank';l.rel='noopener';root.append(l)}
const nav=el('div','zok-jp-segment zok-jp-profile-tabs');['Resum','Partits','Equips','Estadístiques','Rànquings'].forEach(t=>{const b=btn(t,()=>{tab=t;renderProfile()});b.setAttribute('aria-pressed',String(t===tab));nav.append(b)});root.append(nav);
if((tab==='Resum'||tab==='Estadístiques')&&keeper){
 keeperBlock(match,aggregate(keeperRows),tab==='Estadístiques');
 if(fieldRows.length){root.append(el('h3','','Jugador de pista'));const fs=aggregate(fieldRows),g=el('div','zok-jp-grid');[['PJ',fs.played],['Gols',fs.goals],['Assist.',fs.assists]].forEach(x=>g.append(stat(...x)));root.append(g)}
}
else if(tab==='Resum'||tab==='Estadístiques'){const grid=el('div','zok-jp-grid');const ratio=sp.played>0&&Number.isInteger(sp.goals)?(sp.goals/sp.played).toLocaleString('ca',{minimumFractionDigits:2,maximumFractionDigits:2}):undefined;[['PJ',sp.played],['Gols',sp.goals],['Gols/PJ',ratio],['Assist.',sp.assists],['Grogues',sp.yellowCards],['Blaves',sp.blueCards],['Vermelles',sp.redCards],['Capità (actes)',match.filter(a=>a.captain).length],['Consta a l’acta',match.length]].forEach(x=>grid.append(stat(...x)));root.append(grid);if(all)root.append(el('p','zok-jp-note','Totals de competicions diferents · — si falten dades o hi ha solapaments.'));if(tab==='Resum'&&match.some(a=>Number.isInteger(a.stats.goals))){root.append(el('h3','','Evolució golejadora · actes disponibles'));const spark=el('div','zok-jp-spark');for(const a of [...match].reverse().filter(a=>Number.isInteger(a.stats.goals))){const col=el('div','',String(a.stats.goals));col.style.height=Math.max(12,Math.min(100,a.stats.goals*24))+'%';spark.append(col)}root.append(spark)}if(tab==='Estadístiques')root.append(card(el('p','zok-jp-note','Penals, faltes directes, aturades i minuts: — (no verificats).')))}
else if(tab==='Partits'){if(!match.length)root.append(el('p','zok-jp-note','No hi ha partits disponibles per a aquesta vinculació.'));for(const a of match){const matchCard=card(el('strong','',a.fixture.date+' · '+a.fixture.rival+' · '+a.fixture.result),el('p','zok-jp-gold',a.position==='goalkeeper'?(teamScore(a)?'GF equip '+teamScore(a)[0]+' · GC equip '+teamScore(a)[1]:'Resultat no verificat')+(a.participation==='played'?' · Participació confirmada':' · Consta a l’acta'):(a.stats.goals??'—')+' gols · '+(a.stats.assists??'—')+' assist.'),el('p','zok-jp-note',(all?(rows.find(x=>key(x)===key(a))?.groupName||a.teamName)+' · ':'')+'Dorsal '+(a.shirtNumber??'—')+(a.captain?' · Capità':'')+' · '+(a.position==='goalkeeper'?'Porter':a.position==='field'?'Pista':'Posició no verificada')));if(a.actaUrl){const l=el('a','zok-jp-btn','Acta');l.href=a.actaUrl;l.target='_blank';l.rel='noopener';matchCard.append(l)}root.append(matchCard)}}
else if(tab==='Equips'){for(const x of selected)root.append(card(el('strong','',x.teamName),el('p','zok-jp-gold',x.groupName),el('p','zok-jp-note',(x.sports.played??'—')+' PJ · '+(x.position==='goalkeeper'?'🥅 Porter':(x.sports.goals??'—')+' gols')+' · '+x.seasonName)))}
else if(keeper){keeperRanking(keeperRows,id);if(fieldRows.length)root.append(el('p','zok-jp-note','Selecciona una vinculació de pista per veure el rànquing de golejadors.'))}
else {const peers=ranking(D.memberships.filter(x=>selected.some(y=>x.groupName===y.groupName&&x.leagueId===y.leagueId)));root.append(el('p','zok-jp-note',(all?'Rànquing acumulat de les competicions seleccionades':'Rànquing de gols de la competició')+(D.preview?' · mostra':' · dades disponibles, cobertura no garantida')));let rank=0,last=-1;peers.forEach((x,i)=>{if(x.goals!==last)rank=i+1;last=x.goals;const n=card(el('strong','',rank+'. '+byId(x.playerId).name+' · '+x.goals+' G'));if(x.playerId===id)n.style.borderColor='#fbc252';root.append(n)})}}
$('jp-favs').onclick=()=>{scope='favorites';renderList()};$('jp-all').onclick=()=>{scope='all';renderList()};$('jp-search').oninput=renderList;['jp-club','jp-team','jp-category','jp-position'].forEach(k=>$(k).onchange=()=>{filterOptions();renderList()});filterOptions();renderList();
window.addEventListener('zonaok:jugadors-loaded',()=>{active=null;profile.hidden=true;search.hidden=false;filterOptions();renderList()});
window.addEventListener('pageshow',e=>{if(e.persisted)active?renderProfile():renderList()});
})();
