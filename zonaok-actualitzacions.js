/* ZonaOK — resum de dades publicades, no de miralls ni del rellotge local. */
(function(root){
'use strict';
const num=v=>Number.isInteger(v)&&v>=0;
const norm=v=>String(v||'').normalize('NFD').replace(/\p{M}/gu,'').toUpperCase().replace(/\s+/g,' ').trim();
const stamp=v=>typeof v==='string'&&Number.isFinite(Date.parse(v))?v:null;
const latest=xs=>xs.filter(stamp).sort((a,b)=>Date.parse(b)-Date.parse(a))[0]||null;
const score=r=>num(r.homeScore)&&num(r.awayScore);
const text=v=>typeof v==='string'?v.trim():'';
function categoryName(group){
 return group.replace(/\s+(?:GRUP|GRUPO|GROUP)\s+[A-Z0-9]+$/i,'').replace(/(\b(?:OR|PLATA|BRONZE|BRONCE|GOLD|SILVER))\s+\d+$/i,'$1').trim()||group;
}
function summarize(doc,standings,master){
 const rows=Array.isArray(doc?.matches)?doc.matches:null;
 const groups=standings?.competitions&&typeof standings.competitions==='object'?Object.values(standings.competitions).filter(Boolean):null;
 const groupNames=new Map();
 for(const g of groups||[]){const k=norm(g.name),v=text(g.competition)||text(g.category);if(!k||!v)continue;if(groupNames.has(k)&&groupNames.get(k)!==v)groupNames.set(k,null);else if(!groupNames.has(k))groupNames.set(k,v)}
 const categories=new Map();
 let results=0,links=0,verified=0,pending=0;
 for(const r of rows||[]){
  const group=text(r.competition)||'Sense categoria',key=norm(group),category=groupNames.get(key)||categoryName(group),ck=norm(category);
  if(!categories.has(ck))categories.set(ck,{name:category,total:0,results:0,links:0,verified:0,groups:new Map()});
  const c=categories.get(ck);if(!c.groups.has(key))c.groups.set(key,{name:group,total:0,results:0,links:0,verified:0});
  const g=c.groups.get(key);
  const hasScore=score(r),hasLink=!!text(r.actaUrl),hasAct=r.actaState==='available'&&hasLink;
  for(const x of [c,g]){x.total++;if(hasScore)x.results++;if(hasLink)x.links++;if(hasAct)x.verified++}
  if(hasScore)results++;if(hasLink)links++;if(hasAct)verified++;if(hasScore&&!hasAct)pending++;
 }
 const sort=(a,b)=>a.name.localeCompare(b.name,'ca',{numeric:true,sensitivity:'base'});
 const source=doc?.sources||{};
 const players=master?.players&&typeof master.players==='object'?Object.keys(master.players).length:null;
 const memberships=master?.memberships&&typeof master.memberships==='object'?Object.keys(master.memberships).length:null;
 const appearances=master?.matchAppearances&&typeof master.matchAppearances==='object'?Object.keys(master.matchAppearances).length:null;
 return {season:text(doc?.season),updatedAt:stamp(doc?.updatedAt),total:rows?rows.length:null,results:rows?results:null,links:rows?links:null,verified:rows?verified:null,pending:rows?pending:null,players,memberships,appearances,groups:groups?groups.length:null,teams:groups?groups.reduce((n,g)=>n+(Array.isArray(g.standings)?g.standings.length:0),0):null,
 sources:{agenda:stamp(source.agenda?.capturedAt),directe:stamp(source.directe?.capturedAt),actes:stamp(source.actes?.capturedAt),classificacions:latest([standings?.capturedAt,...(groups||[]).map(g=>g.standingsAt)]),jugadors:stamp(master?.updatedAt)},categories:[...categories.values()].sort(sort).map(c=>({...c,groups:[...c.groups.values()].sort(sort)}))};
}
if(typeof module!=='undefined'&&module.exports){module.exports={summarize,categoryName};return}
const el=(tag,cls,value)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(value!==undefined)n.textContent=value;return n};
const $=id=>document.getElementById(id),nf=new Intl.NumberFormat('ca-ES'),df=new Intl.DateTimeFormat('ca-ES',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Madrid'});
const fmt=v=>num(v)?nf.format(v):'—',date=v=>v?df.format(new Date(v)):'Sense data registrada';
const repo='https://github.com/carlesjfontanillas-beep/ZonaOK/actions/workflows/';
const definitions=[
 ['agenda','Agenda TOTAL','zonaok-auto-agenda.yml',s=>fmt(s.total)+' partits · temporada '+(s.season||'—')],
 ['directe','En directe / resultats','zonaok-auto-directe.yml',s=>fmt(s.results)+' partits amb marcador'],
 ['actes','Actes','zonaok-auto-actes.yml',s=>fmt(s.verified)+' verificades · '+fmt(s.links)+' amb enllaç'],
 ['classificacions','Classificacions','zonaok-classificacions-auto.yml',s=>fmt(s.groups)+' grups · '+fmt(s.teams)+' places d’equip'],
 ['jugadors','Jugadors','jugadors-public.yml',s=>fmt(s.players)+' jugadors · '+fmt(s.appearances)+' participacions']
];
function sourceCards(s){
 const host=$('zok-dashboard-sources');host.replaceChildren();
 for(const [key,label,file,detail] of definitions){
  const row=el('div','zok-dashboard-source'),info=el('div','zok-dashboard-info');
  info.append(el('strong','',label),el('span','zok-dashboard-date',date(s.sources[key])),el('small','',detail(s)));
  const link=el('a','zok-dashboard-flash','⚡ Flash ↗');link.href=repo+file+'?ref=main';link.target='_blank';link.rel='noopener noreferrer';link.setAttribute('aria-label','Importació ràpida: '+label);
  row.append(info,link);host.append(row);
 }
}
function table(cats){
 const t=el('table','zok-dashboard-table'),head=el('thead'),tr=el('tr');
 for(const v of ['Categoria / grup','Partits','Resultats','Actes']){const th=el('th','',v);th.scope='col';tr.append(th)}head.append(tr);t.append(head);
 const body=el('tbody');
 for(const c of cats){const tr=el('tr');const cell=el('td');const detail=el('details'),summary=el('summary','',c.name);detail.append(summary);
  if(c.groups.length>1){for(const g of c.groups){const line=el('div','zok-dashboard-group',g.name+' · '+fmt(g.total)+' P · '+fmt(g.results)+' R · '+fmt(g.verified)+' A');detail.append(line)}cell.append(detail)}
  else cell.textContent=c.name;
  tr.append(cell,el('td','',fmt(c.total)),el('td','',fmt(c.results)),el('td','',fmt(c.verified)));body.append(tr)
 }t.append(body);return t;
}
function render(s){
 sourceCards(s);$('zok-dashboard-total').textContent=fmt(s.total)+' partits';
 const host=$('zok-dashboard-overview');host.replaceChildren();
 for(const [label,value] of [['Partits temporada',s.total],['Amb marcador',s.results],['Actes amb enllaç',s.links],['Actes verificades',s.verified],['Amb marcador, acta no verificada',s.pending],['Jugadors',s.players],['Vinculacions',s.memberships],['Participacions en actes',s.appearances]]){const c=el('div','zok-dashboard-metric');c.append(el('strong','',fmt(value)),el('small','',label));host.append(c)}
 const cats=$('zok-dashboard-categories');cats.replaceChildren(el('h3','','Partits per categoria'),el('p','zok-dashboard-hint','Resultats = amb marcador · Actes = verificades. Prem una categoria per veure els grups.'));
 if(s.total===null)cats.append(el('p','helper','No s’ha pogut carregar el catàleg de partits.'));else cats.append(table(s.categories));
}
let pending=false;
async function json(path,gzip=false){
 const response=await fetch(path,{cache:'no-cache',credentials:'same-origin'});
 if(!response.ok)throw Error('HTTP '+response.status);
 if(gzip){if(typeof DecompressionStream==='undefined')throw Error('gzip no disponible');return new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).json()}
 return response.json();
}
async function refresh(){
 if(pending)return;pending=true;const button=$('zok-dashboard-refresh'),status=$('zok-dashboard-status');button.disabled=true;status.textContent='Llegint les darreres dades publicades…';
 try{
  const names=['Partits','Classificacions','Jugadors'];
  const res=await Promise.allSettled([json('zonaok-tots-partits.json'),json('zonaok-classificacions.json'),json('imports/jugadors-master.json.gz',true)]);
  const data=res.map(x=>x.status==='fulfilled'?x.value:null),failed=res.map((x,i)=>x.status==='rejected'?names[i]:null).filter(Boolean);
  const s=summarize(...data);render(s);
  status.textContent=(s.updatedAt?'Catàleg de partits publicat: '+date(s.updatedAt):'Data del catàleg no disponible')+(failed.length?' · Sense lectura: '+failed.join(', '):'');
 }catch(e){status.textContent='No s’ha pogut actualitzar el resum. Torna a provar.'}
 finally{pending=false;button.disabled=false}
}
function mount(){
 if(!$('zok-dashboard-sources'))return;
 sourceCards(summarize(null,null,null));$('zok-dashboard-refresh').onclick=refresh;
 let visible=false;const check=()=>{const next=document.body.classList.contains('zok-ui-import');if(next&&!visible)refresh();visible=next};
 new MutationObserver(check).observe(document.body,{attributes:true,attributeFilter:['class']});check();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})(typeof window!=='undefined'?window:globalThis);
