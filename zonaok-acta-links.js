/* ZonaOK: mostrar Acta només si hi ha un enllaç oficial guardat. */
(function(root){
  'use strict';
  function savedUrl(row){
    if(!row || typeof row.actaUrl!=='string' || !row.actaUrl.trim())return '';
    try{
      const u=new URL(row.actaUrl);
      const league=u.searchParams.get('liga')||'', match=u.searchParams.get('partido')||'';
      if(u.protocol!=='https:'||!['www.hoqueipatins.fecapa.cat','hoqueipatins.fecapa.cat'].includes(u.hostname)
          ||u.username||u.password||u.port||!/^\d{3,10}$/.test(league)||!/^\d{3,10}$/.test(match))return '';
      const lid=String(row.leagueId||row.league||row.liga||'').trim();
      const mid=String(row.matchId||row.id||'').trim();
      if(/^\d{3,10}$/.test(lid)&&lid!==league)return '';
      if(/^\d{3,10}$/.test(mid)&&mid!==match)return '';
      return u.href;
    }catch(_){return '';}
  }
  const api={savedUrl};
  root.ZonaOKActaLinks=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
