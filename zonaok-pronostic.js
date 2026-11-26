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
const api={predict,pending,distribution,history};
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
function show(row,retro=false){
 const d=el('dialog','zok-af-dialog zok-prediction-dialog');d.setAttribute('aria-label','Pronòstic ZonaOK');
 const head=el('header','zok-af-header'),title=el('div');title.append(el('small','','ZONAOK · FECAPA'),el('strong','','PRONÒSTIC DEL PARTIT'));const close=el('button','zok-af-close','×');close.type='button';close.setAttribute('aria-label','Tancar pronòstic');close.onclick=()=>d.close();head.append(title,close);
 const body=el('div','zok-af-body'),summary=el('div','zok-af-top'),content=el('div','zok-af-content');summary.append(el('h2','',row.competition||'Partit'),el('p','zok-af-muted',[row.iso,row.time].filter(Boolean).join(' · ')));body.append(summary,content);d.append(head,body);content.append(el('p','zok-af-muted','Calculant amb els resultats FECAPA…'));document.body.append(d);d.addEventListener('close',()=>d.remove(),{once:true});d.showModal();
 data().then(rows=>{if(!d.open)return;const p=predict(row,rows);content.replaceChildren();if(!p.ok){content.append(el('h3','','Pronòstic no disponible'),el('p','zok-af-muted','No hi ha prou dades disponibles per a aquest partit.'));return}
 const score=el('div','zok-af-score');score.append(el('strong','zok-af-team',row.home),el('b','',p.top[0].h+' : '+p.top[0].a),el('strong','zok-af-team',row.away));content.append(score,el('p','zok-af-muted','Marcador exacte més probable · '+pct(p.top[0].p)));
 const bar=el('div','zok-pred-bar');for(const [v,c] of [[p.home,'#53b58a'],[p.draw,'#fbc252'],[p.away,'#df777b']]){const n=el('span');n.style.width=v*100+'%';n.style.background=c;bar.append(n)}content.append(bar);
 const grid=el('div','zok-pred-probs');for(const [label,v] of [['Victòria local',p.home],['Empat',p.draw],['Victòria visitant',p.away]]){const n=el('div','zok-af-metric');n.append(el('b','',pct(v)),el('small','',label));grid.append(n)}content.append(grid);
 content.append(el('h3','','Marcadors més probables'),resultsChart(p));
 if(retro&&scored(row))line(content,'Resultat real FECAPA',row.homeScore+' : '+row.awayScore);
 content.append(el('p','zok-af-muted',(retro?'Estimació retrospectiva, no arxivada abans del partit. ':'')+'Pronòstic orientatiu i experimental. Probabilitats no calibrades. Font: FECAPA.'));
 }).catch(()=>{if(d.open)content.replaceChildren(el('p','zok-af-muted','No s’han pogut carregar les dades de FECAPA. Torna-ho a provar.'))});
}
function button(row){const b=el('button','zok-acta-action zok-prediction-action','▥ Pronòstic');b.type='button';b.setAttribute('aria-label','Pronòstic de '+row.home+' contra '+row.away);b.onclick=e=>{e.stopPropagation();show(row)};return b}
root.ZonaOKPrediction={...api,show,button};
})(typeof window!=='undefined'?window:globalThis);
