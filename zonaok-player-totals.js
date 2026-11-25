/* Els totals FECAPA de categoria poden repetir-se en cada grup. */
(function(root){
'use strict';
const fields=['played','goals','assists','yellowCards','blueCards','redCards'];
const num=x=>Number.isInteger(x)&&x>=0;
const memberKey=m=>m.leagueId+'|'+m.teamFilterId;
const category=m=>{
 const raw=String(m.groupName||m.leagueName||'').trim();
 const label=raw.replace(/\s+(?:GRUP|GRUPO|GROUP)\s+[A-Z0-9]+$/i,'').replace(/(\b(?:OR|PLATA|BRONZE|BRONCE|GOLD|SILVER))\s+\d+$/i,'$1').trim();
 const norm=label.normalize('NFD').replace(/\p{M}/gu,'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();
 return {key:String(m.seasonId||'')+'|'+(norm||'LLIGA '+m.leagueId),label:label||m.leagueName||'Competició '+m.leagueId};
};
const uniqueMembers=rows=>[...new Map(rows.map(m=>[memberKey(m),m])).values()];
const uniqueActs=rows=>[...new Map(rows.filter(a=>a.matchId&&a.leagueId).map(a=>[a.seasonId+'|'+a.leagueId+'|'+a.matchId,a])).values()];
function groupActs(members,acts){
 const keys=new Set(members.map(memberKey));
 const leagues=new Map();
 for(const m of members){if(!leagues.has(m.leagueId))leagues.set(m.leagueId,[]);leagues.get(m.leagueId).push(m)}
 return uniqueActs(acts.filter(a=>keys.has(memberKey(a))||(!a.teamFilterId&&leagues.get(a.leagueId)?.length===1)));
}
function totals(selected,allRows,allActs){
 const chosen=uniqueMembers(selected),universe=uniqueMembers(allRows),acts=uniqueActs(allActs);
 const cats=new Map();
 for(const m of chosen){const k=category(m).key;if(!cats.has(k))cats.set(k,[]);cats.get(k).push(m)}
 const sp={},partial=[];
 for(const field of fields){
  let sum=0,known=0,incomplete=false;
  for(const [cat,members] of cats){
   const all=universe.filter(m=>category(m).key===cat);
   const catActs=groupActs(all,acts),selectedActs=groupActs(members,acts);
   const values=all.map(m=>m.sports?.[field]).filter(num);
   // Coincident category totals are counted once. Divergent values are not
   // summed blindly; they may be team totals, different snapshots or scopes.
   const official=values.length&&(all.length===1||values.length>=2)&&values.every(v=>v===values[0])?values[0]:undefined;
   const playedValues=all.map(m=>m.sports?.played).filter(num);
   const catPlayed=playedValues.length&&(all.length===1||playedValues.length>=2)&&playedValues.every(v=>v===playedValues[0])?playedValues[0]:undefined;
   const complete= num(catPlayed)&&catActs.length===catPlayed&&catActs.every(a=>
     all.filter(m=>memberKey(m)===memberKey(a)||(!a.teamFilterId&&m.leagueId===a.leagueId)).length===1);
   const whole=members.length===all.length;
   let val,exact=false;
   if(whole&&num(official)){val=official;exact=true}
   else if(field==='played'){
    if(complete){val=selectedActs.length;exact=true}
    else {const confirmed=selectedActs.filter(a=>a.participation==='played').length;if(confirmed)val=confirmed}
   }else{
    const selectedValues=selectedActs.map(a=>a.stats?.[field]).filter(num);
    const catValues=catActs.map(a=>a.stats?.[field]).filter(num);
    const catSum=catValues.reduce((a,b)=>a+b,0);
    const selectedSum=selectedValues.reduce((a,b)=>a+b,0);
    if(num(official)&&official===0&&catSum===0){val=0;exact=true}
    else if(complete&&num(official)&&catSum===official){val=selectedSum;exact=true}
    else if(complete&&selectedActs.length===selectedValues.length){val=selectedSum;exact=true}
    else if(selectedValues.length)val=selectedSum;
   }
   if(num(val)){sum+=val;known++}
   if(!exact)incomplete=true;
  }
  if(known)sp[field]=sum;
  if(incomplete||known!==cats.size)partial.push(field);
 }
 return {sp,partial,possibleOverlap:false};
}
const api={category,totals,groupActs};
root.ZonaOKPlayerTotals=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
