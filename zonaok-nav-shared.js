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

const ORDER_KEY='ZONAOK_NAV_ORDER_V1', bindings=new WeakMap();
function orderRead(){try{const a=JSON.parse(localStorage.getItem(ORDER_KEY)||'[]');return Array.isArray(a)?a.filter(x=>typeof x==='string'):[]}catch{return []}}
function buttons(host){return Array.from(host.children).filter(b=>b.dataset.navOrderId)}
function applyOrder(host){
 const list=buttons(host), rank=new Map(orderRead().map((id,i)=>[id,i]));
 const ordered=list.slice().sort((a,b)=>(rank.get(a.dataset.navOrderId)??Infinity)-(rank.get(b.dataset.navOrderId)??Infinity));
 if(ordered.some((b,i)=>b!==list[i]))ordered.forEach(b=>host.append(b));
}
function saveOrder(host){try{localStorage.setItem(ORDER_KEY,JSON.stringify(buttons(host).map(b=>b.dataset.navOrderId)))}catch{}}
function bindOrder(host){
 if(bindings.has(host))return bindings.get(host);
 if(!document.getElementById('zok-nav-order-style')){
  const css=document.createElement('style');css.id='zok-nav-order-style';css.textContent=
  '[data-nav-order-id]{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none} [data-nav-order-id] img{-webkit-user-drag:none} [data-nav-order-id].zok-nav-moving{outline:2px solid #ffc76f!important;outline-offset:-3px;opacity:.72;cursor:grabbing!important} .zok-nav-reordering{cursor:grabbing!important}';
  document.head.append(css);
 }
 let drag=null, timer=0, frame=0, suppressUntil=0;
 const scroll=host.closest('.zok-nav-scroll')||host.parentElement;
 const status=document.createElement('span');status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.style.cssText='position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;pointer-events:none';host.parentElement.append(status);
 const announce=b=>{status.textContent=b.title+', posició '+(buttons(host).indexOf(b)+1)+' de '+buttons(host).length};
 function finish(commit){
  clearTimeout(timer);cancelAnimationFrame(frame);
  if(!drag)return;
  const {b,active,original}=drag;drag=null;
  if(!active)return;
  b.classList.remove('zok-nav-moving');host.classList.remove('zok-nav-reordering');
  if(commit){saveOrder(host);announce(b)}else if(original.every(x=>x.parentElement===host))original.forEach(x=>host.append(x));
  suppressUntil=Date.now()+850;
 }
 function place(x){
  if(!drag?.active)return;
  const list=buttons(host).filter(b=>b!==drag.b);
  const target=list.find(b=>x<b.getBoundingClientRect().left+b.getBoundingClientRect().width/2);
  if(target){if(drag.b.nextElementSibling!==target)host.insertBefore(drag.b,target)}
  else if(host.lastElementChild!==drag.b)host.append(drag.b);
 }
 function edge(){
  if(!drag?.active)return;
  const r=scroll.getBoundingClientRect(), x=drag.x;
  if(x>=r.left-24&&x<r.left+26)scroll.scrollLeft-=5;
  else if(x<=r.right+24&&x>r.right-26)scroll.scrollLeft+=5;
  place(x);frame=requestAnimationFrame(edge);
 }
 function start(b,x,y,kind,id){
  finish(false);suppressUntil=0;
  if(!b||buttons(host).length<2)return;
  drag={b,x,y,startX:x,startY:y,kind,id,active:false,original:buttons(host)};
  timer=setTimeout(()=>{
   if(!drag||!host.contains(b))return;
   drag.active=true;b.classList.add('zok-nav-moving');host.classList.add('zok-nav-reordering');
   status.textContent='Reordena '+b.title+' arrossegant a esquerra o dreta';
   frame=requestAnimationFrame(edge);
  },500);
 }
 function move(x,y,e){
  if(!drag)return;
  if(!drag.active){if(Math.hypot(x-drag.startX,y-drag.startY)>9)finish(false);return}
  if(e.cancelable)e.preventDefault();drag.x=x;drag.y=y;place(x);
 }
 const target=e=>e.target.closest?.('button[data-nav-order-id]');
 host.addEventListener('touchstart',e=>{if(e.touches.length!==1){finish(false);return}const t=e.changedTouches[0];start(target(e),t.clientX,t.clientY,'touch',t.identifier)},{passive:true});
 host.addEventListener('touchmove',e=>{if(drag?.kind!=='touch')return;const t=Array.from(e.touches).find(t=>t.identifier===drag.id);if(t)move(t.clientX,t.clientY,e)},{passive:false});
 host.addEventListener('touchend',e=>{if(drag?.kind!=='touch'||!Array.from(e.changedTouches).some(t=>t.identifier===drag.id))return;if(drag.active&&e.cancelable)e.preventDefault();finish(true)},{passive:false});
 host.addEventListener('touchcancel',()=>finish(false));
 host.addEventListener('mousedown',e=>{if(e.button!==0||e.sourceCapabilities?.firesTouchEvents)return;start(target(e),e.clientX,e.clientY,'mouse',0)});
 window.addEventListener('mousemove',e=>{if(drag?.kind==='mouse')move(e.clientX,e.clientY,e)});
 window.addEventListener('mouseup',()=>{if(drag?.kind==='mouse')finish(true)});
 window.addEventListener('blur',()=>finish(false));
 host.addEventListener('contextmenu',e=>{if(target(e))e.preventDefault()});
 host.addEventListener('dragstart',e=>{if(target(e))e.preventDefault()});
 host.addEventListener('click',e=>{if(target(e)&&(drag?.active||Date.now()<suppressUntil)){e.preventDefault();e.stopImmediatePropagation()}},true);
 host.addEventListener('keydown',e=>{
  const b=target(e);if(!b||!e.altKey||!['ArrowLeft','ArrowRight'].includes(e.key))return;
  e.preventDefault();e.stopPropagation();const list=buttons(host),i=list.indexOf(b),other=list[i+(e.key==='ArrowLeft'?-1:1)];
  if(!other)return;if(e.key==='ArrowLeft')host.insertBefore(b,other);else host.insertBefore(b,other.nextElementSibling);
  saveOrder(host);b.focus({preventScroll:true});b.scrollIntoView({block:'nearest',inline:'nearest'});announce(b);
 });
 window.addEventListener('storage',e=>{if(e.key===ORDER_KEY&&!drag)applyOrder(host)});
 const binding={cancel:()=>finish(false)};bindings.set(host,binding);return binding;
}

function render(host,s=state()){
 if(!host)return;
 bindOrder(host).cancel();
 host.replaceChildren();
 const add=(tab,label,sub,logo,player=false,initial='',color='',orderId='')=>{
  const b=document.createElement('button');b.type='button';b.className='navbtn';b.dataset.tab=tab;b.dataset.navOrderId=orderId;b.title=label;b.setAttribute('aria-keyshortcuts','Alt+ArrowLeft Alt+ArrowRight');b.setAttribute('aria-label',label);
  const icon=document.createElement('span');
  if(logo){icon.className='club-icon';const img=document.createElement('img');img.src=logo;img.alt='';img.loading='lazy';img.decoding='async';icon.append(img)}
  else if(player){icon.className='nav-person';icon.style.cssText='display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1';const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.style.cssText='display:block;width:28px;height:28px;flex:none';const silhouette=document.createElementNS(svg.namespaceURI,'path');silhouette.setAttribute('d','M12 2a5 5 0 0 1 5 5v2a5 5 0 0 1-2.5 4.33v1.5c.2.85 1.5 1.4 3.6 2.35C20.7 18.35 23 20 23 23H1c0-3 2.3-4.65 4.9-5.82 2.1-.95 3.4-1.5 3.6-2.35v-1.5A5 5 0 0 1 7 9V7a5 5 0 0 1 5-5Z');silhouette.setAttribute('fill',/^#[0-9a-f]{6}$/i.test(color)?color:'#8bb5ce');svg.append(silhouette);icon.append(svg);if(initial){const letter=document.createElement('b');letter.className='nav-player-initial';letter.textContent=initial;letter.style.cssText='display:block;color:#ffb66f;font-size:13px;line-height:1;font-weight:900;margin-top:-2px';icon.append(letter)}}
  else {icon.className='nav-name';icon.textContent='☆'}
  const strong=document.createElement('strong');strong.textContent=label;
  const small=document.createElement('small');small.textContent=sub;
  b.append(icon,strong,small);host.append(b);
 };
 (s.clubs||[]).forEach((name,i)=>add('favclub'+(i+1),name,'Setmana',logoFor(name)||'',false,'','','club:'+name));
 (s.teams||[]).forEach((id,i)=>{const f=teamFromId(id,s);if(!f)return;const child=String(s.teamNames?.[id]||'').trim(),playerName=child||String(f.name||f.team).trim(),initial=Array.from(playerName)[0]?.toLocaleUpperCase('ca')||'';add('favteam'+(i+1),playerName||((f.name||f.team)+' · '+f.category),child?'Temporada':f.category,'',true,initial,s.teamColors?.[id]||'','team:'+id)});
 applyOrder(host);

}
async function loadLogos(){try{const r=await fetch('zonaok-tots-agenda.json',{cache:'no-store'});if(!r.ok)return;const d=await r.json();logos=d.clubLogos||{};rows=Array.isArray(d.rows)?d.rows:[]}catch{}}
window.ZonaOKSharedNav={render,state,loadLogos};
})();
