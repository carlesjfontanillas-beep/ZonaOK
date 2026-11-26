/* ZonaOK Pronòstic v1 — exclusivament resultats FECAPA. */
(function(root){
'use strict';
const norm=x=>String(x??'').normalize('NFD').replace(/\p{M}/gu,'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();
const group=r=>norm(r.competition||r.groupName||r.category||'');
const baseGroup=g=>g.replace(/ (?:GRUP|GRUPO|GROUP) [A-Z0-9]+$/,'').replace(/ (OR|PLATA|BRONZE|BRONCE) \d+$/,' $1');
const score=x=>x!==null&&x!==undefined&&x!==''&&Number.isInteger(Number(x))&&Number(x)>=0&&Number(x)<100;
const scored=r=>score(r.homeScore)&&score(r.awayScore);
const invalid=r=>/CANCEL|ANUL|SUSP|AJORN|APLAZ|NO DISPUT/.test(norm(r.status));
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const average=(a,f)=>a.length?a.reduce((s,x)=>s+f(x),0)/a.length:0;
function todayTime(){const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date());const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));return p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute}
function pending(r){return !scored(r)&&!invalid(r)&&/^\d{4}-\d{2}-\d{2}$/.test(r.iso||'')&&/^\d{2}:\d{2}$/.test(r.time||'')&&r.iso+'T'+r.time>todayTime()}
function history(rows,cutoff){
 const dedup=new Map();
 for(const r of rows||[]){
  if(!r||!scored(r)||invalid(r)||!r.iso||r.iso>=cutoff||!/^\d{4}-\d{2}-\d{2}$/.test(r.iso))continue;
  const g=group(r),h=norm(r.home),a=norm(r.away);if(!g||!h||!a||h===a)continue;
  const k=[g,r.iso,r.time||'',h,a].join('|'),v={g,h,a,iso:r.iso,time:r.time||'',hs:Number(r.homeScore),as:Number(r.awayScore)};
  if(!dedup.has(k))dedup.set(k,v);
  else if(dedup.get(k)&& (dedup.get(k).hs!==v.hs||dedup.get(k).as!==v.as))dedup.set(k,null);
 }
 return [...dedup.values()].filter(Boolean).sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time));
}
function poisson(l){const p=[Math.exp(-l)];for(let i=1;i<=80;i++){p.push(p[i-1]*l/i);if(i>l+12&&p[i]<1e-12)break}const sum=p.reduce((a,b)=>a+b,0);return p.map(x=>x/sum)}
function distribution(lh,la){const a=poisson(lh),b=poisson(la);let home=0,draw=0,away=0;const top=[];
 for(let i=0;i<a.length;i++)for(let j=0;j<b.length;j++){const p=a[i]*b[j];if(i>j)home+=p;else if(i===j)draw+=p;else away+=p;top.push({h:i,a:j,p})}
 top.sort((x,y)=>y.p-x.p);return {home,draw,away,top:top.slice(0,5)};
}
function predict(row,rows,asOf){
 const cutoff=[String(row.iso||''),asOf||todayTime().slice(0,10)].sort()[0];
 const g=group(row),h=norm(row.home),a=norm(row.away);
 if(!g||!h||!a||h===a||!cutoff)return {ok:false,reason:'No s’ha identificat la competició o els equips.'};
 const all=history(rows,cutoff),league=all.filter(x=>x.g===g),pool=all.filter(x=>baseGroup(x.g)===baseGroup(g));
 const hs=league.filter(x=>x.h===h||x.a===h),as=league.filter(x=>x.h===a||x.a===a);
 if(hs.length<3||as.length<3||league.length<6)return {ok:false,reason:'Calen almenys 3 partits previs de cada equip al mateix grup.',nHome:hs.length,nAway:as.length,cutoff};
 const prior=pool.length>=12?pool:league,meanH=clamp(average(prior,x=>x.hs),.7,30),meanA=clamp(average(prior,x=>x.as),.7,30),mean=(meanH+meanA)/2;
 const elo=new Map(),rating=t=>elo.get(t)??1500;
 const homeAdv=clamp(400*Math.log10((meanH+.5)/(meanA+.5)),0,75);
 for(const x of league){const rh=rating(x.h),ra=rating(x.a),expected=1/(1+10**((ra-rh-homeAdv)/400)),actual=x.hs>x.as?1:x.hs===x.as?.5:0,k=24*(1+Math.min(1,Math.log1p(Math.abs(x.hs-x.as))*.3)),d=k*(actual-expected);elo.set(x.h,rh+d);elo.set(x.a,ra-d)}
 const sides=(rows,t)=>rows.map(x=>({opp:x.h===t?x.a:x.h,gf:x.h===t?x.hs:x.as,ga:x.h===t?x.as:x.hs,home:x.h===t}));
 const hv=sides(hs,h),av=sides(as,a);
 function stats(v,t,home){
  let gf=mean*3,ga=mean*3,w=3;
  for(let i=0;i<v.length;i++){const x=v[i],recent=i>=v.length-5?1.5:1,venue=x.home===home?1.15:1,weight=recent*venue;
   const opp=clamp((rating(x.opp)-1500)/400,-.5,.5);
   gf+=weight*x.gf*Math.exp(opp*.35);ga+=weight*x.ga*Math.exp(-opp*.35);w+=weight;
  }return {gf:gf/w,ga:ga/w,form:v.slice(-5).map(x=>x.gf>x.ga?'V':x.gf===x.ga?'E':'D').join(' '),pts:v.reduce((s,x)=>s+(x.gf>x.ga?3:x.gf===x.ga?1:0),0)/v.length};
 }
 const H=stats(hv,h,true),A=stats(av,a,false),diff=clamp((rating(h)-rating(a))/400,-.8,.8);
 const common=[...new Set(hv.map(x=>x.opp))].filter(o=>o!==a&&o!==h&&av.some(x=>x.opp===o));
 const gd=(v,o)=>average(v.filter(x=>x.opp===o),x=>x.gf-x.ga);
 const shared=common.length?average(common,o=>gd(hv,o)-gd(av,o)):0;
 const direct=hv.filter(x=>x.opp===a),headDiff=average(direct,x=>x.gf-x.ga);
 const adj=clamp(.17*diff+.10*(H.pts-A.pts)/3+.12*clamp(shared/(mean+1),-1,1)*common.length/(common.length+3)+.08*clamp(headDiff/(mean+1),-1,1)*direct.length/(direct.length+3),-.4,.4);
 const lh=clamp(Math.sqrt(Math.max(.05,H.gf*A.ga))*meanH/mean*Math.exp(adj),.12,35);
 const la=clamp(Math.sqrt(Math.max(.05,A.gf*H.ga))*meanA/mean*Math.exp(-adj),.12,35);
 return {ok:true,cutoff,nHome:hs.length,nAway:as.length,leagueCount:league.length,common:common.length,direct:direct.length,homeRating:Math.round(rating(h)),awayRating:Math.round(rating(a)),homeForm:H.form,awayForm:A.form,homePoints:H.pts,awayPoints:A.pts,lh,la,coverage:Math.min(hs.length,as.length)>=10&&league.length>=35?'Àmplia':Math.min(hs.length,as.length)>=5?'Mitjana':'Baixa',...distribution(lh,la)};
}
// Estimate goal shares using prior team matches with reconciled individual goals.
// Escenari coherent amb el marcador modal, amb reserva per a altres golejadors.
function allocateGoals(players,total){
 const n=Number.isInteger(total)&&total>=0?total:0;
 const weights=players.map(x=>Math.max(0,Number(x.share)||0)),sum=weights.reduce((a,b)=>a+b,0),den=Math.max(1,sum);
 const shares=[...weights.map(w=>w/den),Math.max(0,1-sum/den)];
 const parts=shares.map((share,i)=>({i,goals:Math.floor(n*share),remainder:n*share-Math.floor(n*share)}));
 const remaining=n-parts.reduce((a,x)=>a+x.goals,0);
 const order=parts.slice().sort((a,b)=>b.remainder-a.remainder||a.i-b.i);
 for(let i=0;i<remaining;i++)order[i%order.length].goals++;
 return {players:players.map((x,i)=>({...x,predictedGoals:parts[i].goals})),otherGoals:parts[players.length].goals};
}
function scorers(row,p,master,catalog){
 const empty=()=>({home:[],away:[],homeOther:0,awayOther:0});
 if(master?.schema!=='zonaok-jugadors-v1'||master.source!=='FECAPA'||!master.players||!master.matchAppearances||!Array.isArray(catalog?.matches))return empty();
 const leagueId=r=>String(r.leagueId||r.league||r.liga||'');
 const matchId=r=>String(r.matchId||r.id||'');
 const key=r=>leagueId(r)+'|'+matchId(r);
 const g=group(row),h=norm(row.home),a=norm(row.away);
 const target=catalog.matches.filter(f=>f.iso===row.iso&&norm(f.home)===h&&norm(f.away)===a&&(group(f)===g||!group(f))&&(!row.time||!f.time||row.time===f.time));
 const explicit=leagueId(row),inferred=target.length===1?leagueId(target[0]):'', league=explicit||inferred;
 if(explicit&&inferred&&explicit!==inferred)return empty();
 const fixtures=new Map();
 for(const f of catalog.matches){
  if(!leagueId(f)||!matchId(f)||!f.iso||f.iso>=p.cutoff||!scored(f)||invalid(f)||/EN JOC|EN DIRECTE|LIVE|PLAYING|IN PROGRESS/.test(norm(f.status)))continue;
  if(league?leagueId(f)!==league:(group(f)!==g||!g))continue;
  const k=key(f);if(fixtures.has(k)){fixtures.set(k,null);continue}fixtures.set(k,f);
 }
 const entries=new Map();
 for(const x of Object.values(master.matchAppearances)){
  if(x.seasonId!==master.seasonId||!['home','away'].includes(x.side)||!['played','listed'].includes(x.participation)||!master.players[x.playerId])continue;
  const f=fixtures.get(key(x));if(!f)continue;
  const team=norm(f[x.side]);if((team!==h&&team!==a)||(x.teamName&&norm(x.teamName)!==team))continue;
  const k=key(x)+'|'+x.side;if(!entries.has(k))entries.set(k,new Map());
  const m=entries.get(k);if(m.has(x.playerId)){m.set(x.playerId,null);continue}m.set(x.playerId,x);
 }
 function side(team,expected,modal){
  const games=[];
  for(const [k,f] of fixtures){if(!f)continue;const side=norm(f.home)===team?'home':norm(f.away)===team?'away':'';if(!side)continue;
   const m=entries.get(k+'|'+side);if(!m||m.size<4||[...m.values()].some(x=>!x))continue;
   const xs=[...m.values()],known=xs.filter(x=>Number.isInteger(x.stats?.goals)&&x.stats.goals>=0);
   const goals=Number(f[side+'Score']);
   if(known.length<3||known.length<xs.length*.7||known.reduce((sum,x)=>sum+x.stats.goals,0)!==goals)continue;
   games.push({f,xs:known,goals})
  }
  games.sort((x,y)=>(x.f.iso+(x.f.time||'')).localeCompare(y.f.iso+(y.f.time||'')));
  if(games.length<3)return {players:[],otherGoals:0};
  const recent=new Set(games.slice(-3).flatMap(x=>x.xs.map(a=>a.playerId)));
  const all=new Map();let total=0;
  games.forEach((game,i)=>{const w=i>=games.length-5?1.5:1;total+=game.goals*w;
   for(const x of game.xs){const old=all.get(x.playerId)||{id:x.playerId,goals:0,weighted:0};old.goals+=x.stats.goals;old.weighted+=w*x.stats.goals;all.set(x.playerId,old)}
  });
  if(total<=0)return {players:[],otherGoals:0};
  const candidates=[...all.values()].filter(x=>x.goals>0&&recent.has(x.id)&&typeof master.players[x.id]?.name==='string'&&master.players[x.id].name.trim()).map(x=>({id:x.id,name:master.players[x.id].name,share:x.weighted/(total+2),prob:1-Math.exp(-expected*x.weighted/(total+2)),goals:x.goals})).sort((x,y)=>y.prob-x.prob||x.name.localeCompare(y.name,'ca'));
  if(!candidates.length)return {players:[],otherGoals:0};
  const allocated=allocateGoals(candidates,modal);
  const players=allocated.players.sort((x,y)=>y.predictedGoals-x.predictedGoals||y.prob-x.prob||x.name.localeCompare(y.name,'ca')).slice(0,5);
  return {players,otherGoals:Math.max(0,modal-players.reduce((s,x)=>s+x.predictedGoals,0))};
 }
 const H=side(h,p.lh,p.top[0].h),A=side(a,p.la,p.top[0].a);
 return {home:H.players,away:A.players,homeOther:H.otherGoals,awayOther:A.otherGoals};
}
const api={predict,pending,distribution,history,scorers,allocateGoals};
if(typeof module!=='undefined'&&module.exports){module.exports=api;return}
const el=(tag,cls,t)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(t!==undefined)n.textContent=t;return n};
let dataPromise=null;
function data(){if(Array.isArray(root.ZonaOKFullAgendaRows)&&root.ZonaOKFullAgendaRows.length)return Promise.resolve(root.ZonaOKFullAgendaRows);if(!dataPromise)dataPromise=fetch('zonaok-tots-agenda.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(x=>{if(!Array.isArray(x.rows))throw Error('Agenda');return x.rows}).catch(e=>{dataPromise=null;throw e});return dataPromise}
function pct(p){return (p*100).toLocaleString('ca-ES',{maximumFractionDigits:1})+'%'}
function line(parent,label,value){const n=el('div','zok-af-event');n.append(el('span','zok-af-muted',label),el('strong','',value));parent.append(n)}
function resultsChart(p){
 const chart=el('section','zok-pred-results');chart.setAttribute('aria-label','Probabilitats dels cinc marcadors més probables');
 const max=Math.min(1,Math.max(.05,Math.ceil(p.top[0].p*20)/20));
 for(const [i,x] of p.top.entries()){
  const line=el('div','zok-pred-result-line'),label=el('strong','zok-pred-result-score',x.h+' : '+x.a),track=el('div','zok-pred-result-track'),fill=el('span','zok-pred-result-fill'+(i===0?' first':''));
  fill.style.width=clamp(x.p/max*100,0,100)+'%';track.append(fill);track.setAttribute('aria-hidden','true');
  line.append(label,track,el('b','zok-pred-result-percent',pct(x.p)));chart.append(line)
 }
 const axis=el('div','zok-pred-result-axis');axis.append(el('span','','0%'),el('span','',pct(max)));chart.append(axis);
 chart.append(el('p','zok-pred-result-note','Altres marcadors: '+pct(clamp(1-p.top.reduce((s,x)=>s+x.p,0),0,1))));
 return chart;
}
let scorerCache=null;
function scorerData(){
 if(!scorerCache){
  const opts={cache:'no-cache',credentials:'same-origin'};
  scorerCache=Promise.all([
   fetch('imports/jugadors-master.json.gz',opts).then(r=>{if(!r.ok||typeof DecompressionStream==='undefined')throw Error('Jugadors');return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json()}),
   fetch('zonaok-tots-partits.json',opts).then(r=>{if(!r.ok)throw Error('Partits');return r.json()})
  ]).catch(e=>{scorerCache=null;throw e});
  setTimeout(()=>{scorerCache=null},60000);
 }
 return scorerCache;
}
function renderScorers(host,row,p,d){
 host.append(el('p','zok-af-muted','Carregant golejadors…'));
 scorerData().then(([master,catalog])=>{
  if(!d.open)return;const lists=scorers(row,p,master,catalog);host.replaceChildren();
  const max=Math.max(1,...lists.home.map(x=>x.predictedGoals),...lists.away.map(x=>x.predictedGoals),lists.homeOther,lists.awayOther);
  const label=n=>n===1?'1 gol':n+' gols';
  function bar(chart,name,goals,prob,first){
   const item=el('div','zok-pred-scorer-column'),plot=el('div','zok-pred-scorer-plot'),stack=el('div','zok-pred-scorer-stack'),count=el('b','zok-pred-scorer-count',String(goals)),fill=el('span','zok-pred-scorer-fill'+(first?' first':''));
   fill.style.height=clamp(goals/max*100,0,100)+'%';
   plot.append(fill,count);plot.setAttribute('aria-hidden','true');
   stack.append(el('strong','zok-pred-scorer-name',name));
   if(prob!==null){const small=el('small','zok-pred-scorer-prob',pct(prob));small.title='Probabilitat estimada de marcar almenys un gol';stack.append(small)}
   item.append(plot,stack);
   item.setAttribute('aria-label',name+': '+label(goals)+(prob===null?'':', '+pct(prob)+' de marcar almenys un gol'));
   chart.append(item);
  }
  for(const [side,name,total,other] of [['home',row.home,p.top[0].h,lists.homeOther],['away',row.away,p.top[0].a,lists.awayOther]]){
   const section=el('section','zok-pred-scorer-team'),head=el('div','zok-pred-scorer-heading');head.append(el('h4','',name),el('b','',label(total)));section.append(head);
   const list=lists[side];
   if(!list.length){section.append(el('p','zok-af-muted','No hi ha prou actes amb gols individuals verificables.'));host.append(section);continue}
   const chart=el('div','zok-pred-scorer-columns');chart.style.gridTemplateColumns='repeat('+(list.length+(other>0?1:0))+', minmax(59px, 1fr))';chart.setAttribute('aria-label','Gràfica de gols previstos · '+name);
   for(const [i,x] of list.entries())bar(chart,x.name,x.predictedGoals,x.prob,i===0);
   if(other>0)bar(chart,'Altres golejadors',other,null,false);
   section.append(chart);host.append(section)
  }
  if(lists.home.length||lists.away.length)host.append(el('p','zok-af-muted','Repartiment orientatiu dels gols del marcador previst. El percentatge indica la probabilitat de marcar almenys un gol. Alineacions no confirmades.'));
 }).catch(()=>{if(d.open)host.replaceChildren(el('p','zok-af-muted','No s’han pogut carregar les estadístiques individuals.'))});
}
function show(row,retro=false){
 const d=el('dialog','zok-af-dialog zok-prediction-dialog');d.setAttribute('aria-label','Pronòstic ZonaOK');
 const head=el('header','zok-af-header'),title=el('div');title.append(el('small','','ZONAOK · FECAPA'),el('strong','','PRONÒSTIC DEL PARTIT'));const close=el('button','zok-af-close','×');close.type='button';close.setAttribute('aria-label','Tancar pronòstic');close.onclick=()=>d.close();head.append(title,close);
 const body=el('div','zok-af-body'),summary=el('div','zok-af-top'),content=el('div','zok-af-content');summary.append(el('h2','',row.competition||'Partit'),el('p','zok-af-muted',[row.iso,row.time].filter(Boolean).join(' · ')));body.append(summary,content);d.append(head,body);content.append(el('p','zok-af-muted','Calculant amb els resultats FECAPA…'));document.body.append(d);d.addEventListener('close',()=>d.remove(),{once:true});d.showModal();
 data().then(rows=>{if(!d.open)return;const p=predict(row,rows);content.replaceChildren();if(!p.ok){content.append(el('h3','','Pronòstic no disponible'),el('p','zok-af-muted','No hi ha prou dades disponibles per a aquest partit.'));return}
 const score=el('div','zok-af-score');score.append(el('strong','zok-af-team',row.home),el('b','',p.top[0].h+' : '+p.top[0].a),el('strong','zok-af-team',row.away));content.append(score,el('p','zok-af-muted','Marcador exacte més probable · '+pct(p.top[0].p)));
 const bar=el('div','zok-pred-bar');for(const [v,c] of [[p.home,'#53b58a'],[p.draw,'#fbc252'],[p.away,'#df777b']]){const n=el('span');n.style.width=v*100+'%';n.style.background=c;bar.append(n)}content.append(bar);
 const grid=el('div','zok-pred-probs');for(const [label,v] of [['Victòria local',p.home],['Empat',p.draw],['Victòria visitant',p.away]]){const n=el('div','zok-af-metric');n.append(el('b','',pct(v)),el('small','',label));grid.append(n)}content.append(grid);
 content.append(el('h3','','Marcadors més probables'),resultsChart(p));
 const scorersHost=el('div','zok-pred-scorers');content.append(el('h3','','Golejadors més probables'),scorersHost);renderScorers(scorersHost,row,p,d);
 if(retro&&scored(row))line(content,'Resultat real FECAPA',row.homeScore+' : '+row.awayScore);
 content.append(el('p','zok-af-muted',(retro?'Estimació retrospectiva, no arxivada abans del partit. ':'')+'Pronòstic orientatiu i experimental. Probabilitats no calibrades. Font: FECAPA.'));
 }).catch(()=>{if(d.open)content.replaceChildren(el('p','zok-af-muted','No s’han pogut carregar les dades de FECAPA. Torna-ho a provar.'))});
}
function button(row){const b=el('button','zok-acta-action zok-prediction-action','▥ Pronòstic');b.type='button';b.setAttribute('aria-label','Pronòstic de '+row.home+' contra '+row.away);b.onclick=e=>{e.stopPropagation();show(row)};return b}
root.ZonaOKPrediction={...api,show,button};
})(typeof window!=='undefined'?window:globalThis);
