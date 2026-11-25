(()=>{
'use strict';
const norm=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Z0-9]/gi,' ').replace(/\s+/g,' ').trim().toUpperCase();
const state=()=>{try{return JSON.parse(localStorage.getItem('ZONAOK_FAVORITS_V1')||'{}')||{}}catch{return {}}};
function teamFromId(id,s){if(typeof id!=='string'||!id)return null;const p=id.split('|');return p.length>=3?{id,team:norm(p[1]),category:norm(p.slice(2).join('|')),name:String(s.teamNames?.[id]||'').trim()}:null}
function safe(url){return /^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(String(url||''))?url:''}
let logos={},rows=[];
function logoFor(name){
 if(typeof window.ZonaOKFavoriteLogoFor==='function'){const url=safe(window.ZonaOKFavoriteLogoFor(name));if(url)return url}
 const n=norm(name);
 if(/^(?:BAR|BARCA|FC BARCELONA|FCBETRANS|FCBETERANS)(?: |$)/.test(n))return 'https://sidgad.cloud/fecapa/images/logos_clubes/234.png';
 if(/^(?:CPSC|CP SANT CELONI|SANT CELONI)(?: |$)/.test(n))return 'https://sidgad.cloud/fecapa/images/logos_clubes/281.png';
 const s=state(),key=x=>norm(x).replace(/\s+[A-Z]$/,'').trim(),target=key(name);
 const match=x=>{const k=key(x);return k&&target&&(target===k||target.startsWith(k+' ')||k.startsWith(target+' '))};
 for(const [k,url] of Object.entries({...s.clubLogoUrls,...s.teamLogoUrls,...logos}))if(match(k)&&safe(url))return url;
 for(const r of rows)for(const side of ['home','away'])if(match(r?.[side])&&safe(r?.[side+'Logo']))return r[side+'Logo'];
 return '';
}
function render(host,s=state()){
 if(!host)return;
 host.replaceChildren();
 const add=(tab,label,sub,logo,player=false,initial='')=>{
  const b=document.createElement('button');b.type='button';b.className='navbtn';b.dataset.tab=tab;b.title=label;b.setAttribute('aria-label',label);
  const icon=document.createElement('span');
  if(logo){icon.className='club-icon';const img=document.createElement('img');img.src=logo;img.alt='';img.loading='lazy';img.decoding='async';icon.append(img)}
  else if(player){icon.className='nav-person';icon.style.cssText='display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1';icon.textContent='👤';if(initial){const letter=document.createElement('b');letter.className='nav-player-initial';letter.textContent=initial;letter.style.cssText='display:block;color:#ffb66f;font-size:13px;line-height:1;font-weight:900;margin-top:-2px';icon.append(letter)}}
  else {icon.className='nav-name';icon.textContent='☆'}
  const strong=document.createElement('strong');strong.textContent=label;
  const small=document.createElement('small');small.textContent=sub;
  b.append(icon,strong,small);host.append(b);
 };
 (s.clubs||[]).forEach((name,i)=>add('favclub'+(i+1),name,'Setmana',logoFor(name)||''));
 (s.teams||[]).forEach((id,i)=>{const f=teamFromId(id,s);if(!f)return;const child=String(s.teamNames?.[id]||'').trim(),playerName=child||String(f.name||f.team).trim(),initial=Array.from(playerName)[0]?.toLocaleUpperCase('ca')||'';add('favteam'+(i+1),playerName||((f.name||f.team)+' · '+f.category),child?'Temporada':f.category,'',true,initial)});

}
async function loadLogos(){try{const r=await fetch('zonaok-tots-agenda.json',{cache:'no-store'});if(!r.ok)return;const d=await r.json();logos=d.clubLogos||{};rows=Array.isArray(d.rows)?d.rows:[]}catch{}}
window.ZonaOKSharedNav={render,state,loadLogos};
})();
