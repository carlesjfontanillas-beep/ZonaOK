/* ZonaOK — fitxa pròpia d'acta. Només dades publicades FECAPA. */
(function(root){
'use strict';
const int=x=>Number.isInteger(x)&&x>=0,fmt=x=>int(x)?String(x):'',str=x=>typeof x==='string'?x.trim():'';
function identity(url){try{const u=new URL(url);if(u.protocol!=='https:'||!['www.hoqueipatins.fecapa.cat','hoqueipatins.fecapa.cat'].includes(u.hostname)||u.username||u.password||u.port)return null;const l=u.searchParams.get('liga'),m=u.searchParams.get('partido');return /^\d{3,10}$/.test(l||'')&&/^\d{3,10}$/.test(m||'')?{leagueId:l,matchId:m,key:l+'|'+m,url:u.href}:null}catch{return null}}
function matchData(id,row,catalog,master,state){
 const matches=(catalog?.matches||[]).filter(r=>{const linked=identity(r.actaUrl);return linked?linked.key===id.key:String(r.leagueId||r.league)===id.leagueId&&String(r.matchId||r.id)===id.matchId});
 const fixture=matches.length===1?{...row,...matches[0]}:row;
 const people=master?.players||{},seen=new Set(),sides={home:[],away:[]};
 if(master?.source==='FECAPA'||master?.trusted===true)for(const a of Object.values(master.matchAppearances||{})){
  if(String(a.leagueId)!==id.leagueId||String(a.matchId)!==id.matchId||!sides[a.side]||seen.has(String(a.playerId)))continue;
  const person=people[a.playerId];if(!person||!str(person.name))continue;seen.add(String(a.playerId));sides[a.side].push({...a,name:person.name});
 }
 for(const side of Object.values(sides))side.sort((a,b)=>(a.shirtNumber??999)-(b.shirtNumber??999)||a.name.localeCompare(b.name,'ca'));
 const entry=state?.matches?.[id.key],details=entry?.details?.source==='FECAPA'?entry.details:{};
 return {fixture,sides,details};
}
if(typeof module!=='undefined'&&module.exports){module.exports={identity,matchData};return}
const el=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e};
const button=(label,fn,cls)=>{const b=el('button',cls,label);b.type='button';b.onclick=fn;return b};
let active=null,cache=null;
async function json(path,gz=false){const r=await fetch(path,{cache:'no-cache',credentials:'same-origin'});if(!r.ok)throw Error('HTTP '+r.status);if(gz){if(typeof DecompressionStream==='undefined')throw Error('gzip');return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json()}return r.json()}
function loadedPlayers(){const d=root.ZonaOKJugadors;if(!d?.loaded||d.preview)return null;return {trusted:true,players:Object.fromEntries(d.players.map(p=>[p.playerId,p])),matchAppearances:d.appearances}}
function data(){if(!cache){cache=Promise.allSettled([json('zonaok-tots-partits.json'),loadedPlayers()||json('imports/jugadors-master.json.gz',true),json('imports/jugadors-maintenance-state.json')]).then(xs=>xs.map(x=>x.status==='fulfilled'?x.value:null));setTimeout(()=>{cache=null},60000)}return cache}
const colors={yellowCards:'#fbc252',blueCards:'#3893f5',redCards:'#ed5353'};
function icon(k){const n=el('span','zok-af-card');n.style.background=colors[k];n.setAttribute('aria-label',({yellowCards:'Grogues',blueCards:'Blaves',redCards:'Vermelles'})[k]);return n}
function metric(label,value){const n=el('div','zok-af-metric');n.append(el('b','',fmt(value)),el('small','',label));return n}
function addFacts(parent,heading,items){const known=items.filter(([_,v])=>str(v)||int(v));if(!known.length)return;if(heading)parent.append(el('h3','',heading));for(const [k,v] of known){const line=el('div','zok-af-event');line.append(el('span','zok-af-muted',k),el('strong','',String(v)));parent.append(line)}}
function addStaff(parent,details,home,away){for(const [side,name] of [['home',home],['away',away]]){addFacts(parent,'Cos tècnic · '+name,(details.staff?.[side]||[]).map(p=>[p.role,p.name]))}}
function team(name,logo){const n=el('div','zok-af-team');if(/^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/\d+\.png$/.test(str(logo))){const img=el('img');img.src=logo;img.alt='';n.append(img)}n.append(el('strong','',name||'—'));return n}
function playerLink(a){const l=el('a','zok-af-player',a.name);l.href='jugadors.html?playerId='+encodeURIComponent(a.playerId);l.onclick=e=>{if(root.ZonaOKOpenActaPlayer){e.preventDefault();const dialog=active;active=null;dialog?.close();if(!root.ZonaOKOpenActaPlayer(a.playerId))location.href=l.href}};return l}
function open(row,url){
 const id=identity(url);if(!id||root.ZonaOKActaLinks?.savedUrl({actaUrl:url,leagueId:id.leagueId,matchId:id.matchId})==='')return;
 if(active?.open)active.close();
 const pos={x:scrollX,y:scrollY},d=el('dialog','zok-af-dialog');d.setAttribute('aria-label','Acta del partit');active=d;
 const head=el('header','zok-af-header'),label=el('div','');label.append(el('small','','ZONAOK · FECAPA'),el('strong','','ACTA DEL PARTIT'));
 const official=el('a','zok-af-official','Acta FECAPA ↗');official.href=id.url;official.target='_blank';official.rel='noopener noreferrer';
 const close=button('×',()=>d.close(),'zok-af-close');close.setAttribute('aria-label','Tancar acta');head.append(label,official,close);
 const body=el('div','zok-af-body'),top=el('div','zok-af-top'),tabs=el('div','zok-af-tabs'),content=el('div','zok-af-content');body.append(top,tabs,content);d.append(head,body);document.body.append(d);
 let current='Resum',loading=true,model=matchData(id,row,null,null,null);
 const names=['Resum','Jugadors','Incidències','Arbitratge'];const controls=names.map(n=>button(n,()=>{current=n;render()},''));
 tabs.append(...controls);
 function render(){
  const {fixture:f,sides,details}=model,home=f.home||'Local',away=f.away||'Visitant';
  const h=details.header||{};
  top.replaceChildren(el('h2','',h.competition||f.competition||f.category||'Acta del partit'),el('p','zok-af-muted',[h.round||f.round,[f.iso,f.time].filter(Boolean).join(' · ')||h.dateTime].filter(Boolean).join(' · ')));
  const score=el('div','zok-af-score');score.append(team(home,f.homeLogo),el('b','',fmt(f.homeScore)+' : '+fmt(f.awayScore)),team(away,f.awayLogo));top.append(score);
  if(h.venue||f.venue)top.append(el('p','zok-af-muted','📍 '+(h.venue||f.venue)));
  const fouls=el('div','zok-af-fouls');if(int(details.fouls?.home))fouls.append(metric('Faltes local',details.fouls.home));if(int(details.fouls?.away))fouls.append(metric('Faltes visitant',details.fouls.away));if(fouls.children.length)top.append(fouls);
  controls.forEach((b,i)=>b.setAttribute('aria-pressed',String(names[i]===current)));content.replaceChildren();
  if(loading)content.append(el('p','zok-af-muted','Carregant dades publicades…'));
  if(current==='Resum'){
   const grid=el('div','zok-af-grid');if(int(f.homeScore))grid.append(metric('Gols local',f.homeScore));if(int(f.awayScore))grid.append(metric('Gols visitant',f.awayScore));if(grid.children.length)content.append(grid);
   for(const side of ['home','away']){
    const line=el('div','zok-af-event'),values=el('div','');line.append(el('strong','',side==='home'?home:away));
    for(const k of Object.keys(colors)){
     const a=sides[side],known=a.filter(p=>int(p.stats?.[k]));const v=known.length?known.reduce((n,p)=>n+p.stats[k],0):null;
     if(int(v))values.append(icon(k),el('span','',fmt(v)+(known.length&&known.length!==a.length?'*':'')));
    }
    if(values.children.length){line.append(values);content.append(line);}
   }
   if([...sides.home,...sides.away].some(p=>Object.keys(colors).some(k=>int(p.stats?.[k]))))content.append(el('p','zok-af-muted','* Suma parcial de les targetes individuals disponibles.'));
   addFacts(content,'Dades del partit',[['Estat',f.status],['Temporada',h.season],['Localitat',h.town],['Hora real d’inici',h.startTime],['Àrbitre',h.referee1],['Segon àrbitre',h.referee2]]);
   addStaff(content,details,home,away);
   if(root.ZonaOKPrediction&&int(f.homeScore)&&int(f.awayScore)&&f.iso){content.append(button('▥ Comparar amb estimació prèvia',()=>root.ZonaOKPrediction.show(f,true),'zok-pred-retro'));}
   if(details.periods?.some(p=>p.period.toLowerCase()!=='total'&&p.score))addFacts(content,'Parcials',details.periods.filter(p=>p.period.toLowerCase()!=='total').map(p=>['Període '+p.period,p.score]));
  }else if(current==='Jugadors'){
   for(const side of ['home','away']){
    content.append(el('h3','',side==='home'?home:away));
    if(!sides[side].length){content.append(el('p','zok-af-muted','Encara no hi ha alineació importada.'));continue}
    const t=el('table','zok-af-table'),head=el('tr');const extra=[['assists','As'],['penalties','PEN'],['directFreeHits','FD'],['foulsCommitted','F→'],['foulsReceived','F←']].filter(([k])=>sides[side].some(a=>int(a.stats?.[k])));for(const k of ['D.','Jugador','G',...Object.keys(colors),...extra.map(x=>x[1])]){const th=el('th');if(colors[k])th.append(icon(k));else th.textContent=k;head.append(th)}const thead=el('thead');thead.append(head);t.append(thead);const tb=el('tbody');
    for(const a of sides[side]){const tr=el('tr'),name=el('td');name.append(playerLink(a));const tags=[a.captain?'Capità':'',a.position==='goalkeeper'?'Porter':'',a.startingFive?'5 inicial':'',a.playerCategory||''].filter(Boolean);if(tags.length)name.append(el('small','zok-af-muted',tags.join(' · ')));tr.append(el('td','',fmt(a.shirtNumber)),name,el('td','',fmt(a.stats?.goals)));for(const k of [...Object.keys(colors),...extra.map(x=>x[0])])tr.append(el('td','',fmt(a.stats?.[k])));tb.append(tr)}t.append(tb);content.append(t)
   }
  }else if(current==='Incidències'){
   content.append(el('h3','','Gols, targetes i faltes'));
   const list=[...sides.home,...sides.away].filter(a=>['goals',...Object.keys(colors)].some(k=>int(a.stats?.[k])&&a.stats[k]>0));
   for(const a of list){const r=el('div','zok-af-event'),vals=el('div','');r.append(playerLink(a));if(a.stats.goals>0)vals.append(el('b','',a.stats.goals+' gols'));for(const k of Object.keys(colors))if(a.stats[k]>0){vals.append(icon(k),el('span','',fmt(a.stats[k])))}r.append(vals);content.append(r)}
   if(!list.length)content.append(el('p','zok-af-muted','No hi ha incidències individuals importades.'));
   if(int(details.fouls?.home)||int(details.fouls?.away))content.append(el('p','zok-af-muted','Recompte de faltes a la capçalera.'));
  }else{
   addFacts(content,'Equip arbitral',[['Àrbitre 1',h.referee1],['Àrbitre 2',h.referee2],['Àrbitre auxiliar',h.assistantReferee],['Cronometrador',h.timekeeper],['Delegat de pista',h.rinkDelegate],['Delegat FCP',h.federationDelegate],['Delegat d’acta',h.reportDelegate]]);
  }
  if(!loading)content.append(el('p','zok-af-muted','Font: FECAPA · Dades publicades a ZonaOK. Les dades poden ser parcials.'));
 }
 d.addEventListener('close',()=>{d.remove();if(active===d){active=null;requestAnimationFrame(()=>scrollTo(pos.x,pos.y))}},{once:true});
 render();d.showModal();data().then(([catalog,master,state])=>{if(!d.open)return;model=matchData(id,row,catalog,master,state);loading=false;render()});
}
root.ZonaOKActaFitxa={open};
})(typeof window!=='undefined'?window:globalThis);
