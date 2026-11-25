(function(root){
'use strict';
const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Z0-9]/gi,' ').replace(/\s+/g,' ').trim().toUpperCase();
function select(entries,favorites,leagueIds={}){
 const selected=new Set(),missing=[];
 for(const f of favorites){
  if(!f||!f.category)continue;
  const category=norm(f.category),league=String(leagueIds[f.id]||'');
  let candidates=entries.filter(e=>e.rows?.length&&norm(e.name)===category);
  // FECAPA pot donar el mateix leagueId a tots els grups d'una categoria.
  // Mai seleccionar per leagueId sol, ni per prefix de categoria.
  if(candidates.length>1){
   const exact=candidates.filter(e=>String(e.id).split(':')[0]===league);
   if(exact.length)candidates=exact;
  }
  if(candidates.length>1){
   const matching=candidates.filter(e=>e.rows.some(row=>norm(row.team)===norm(f.team)));
   if(matching.length===1)candidates=matching;
  }
  if(candidates.length===1)selected.add(candidates[0]);else missing.push(f.id);
 }
 return {entries:entries.filter(e=>selected.has(e)),missing};
}
const api={select};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ZonaOKStandingScope=api;
})(typeof window!=='undefined'?window:globalThis);
