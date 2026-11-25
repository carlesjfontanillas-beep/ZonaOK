(()=>{
'use strict';
const $=s=>document.querySelector(s),el=(t,c,v)=>{const n=document.createElement(t);if(c)n.className=c;if(v!==undefined)n.textContent=v;return n};
const version='20261125-ranking-nav3';
function go(tab){const u=new URL('index.html',location.href);u.searchParams.set('v',version);if(tab!=='home')u.searchParams.set('tab',tab);location.href=u.href}
function prefs(){try{return JSON.parse(localStorage.getItem('ZONAOK_FAVORITS_V1')||'{}')||{}}catch{return {}}}
function logo(value){try{const u=new URL(value,location.href);if(u.protocol==='https:'&&u.hostname==='sidgad.cloud'&&/^\/fecapa\/images\/logos_clubes\/[0-9]+(?:_[0-9]+)?\.(?:png|gif)$/i.test(u.pathname))return u.href}catch{}return ''}
function playerPageNav(){
 const bar=$('.zok-jp-bottom'),host=$('#zok-nav-favorites');if(!bar||!host)return;
 function render(){window.ZonaOKSharedNav.render(host)}
 render();void window.ZonaOKSharedNav.loadLogos().then(render);
 window.addEventListener('pageshow',render);window.addEventListener('storage',e=>{if(e.key==='ZONAOK_FAVORITS_V1'||e.key===null)render()});
 bar.addEventListener('click',e=>{const b=e.target.closest('button[data-destination],button[data-tab]');if(b)go(b.dataset.destination||b.dataset.tab)});
}
function mount(){
 const fixed=$('.zok-nav-fixed');if(!fixed)return;
 const isPlayers=!!$('.zok-jp-bottom');
 if(!document.getElementById('zok-nav-jugadors')){
 const b=el('button','navbtn');b.type='button';b.id='zok-nav-jugadors';b.setAttribute('aria-label','Jugadors');b.title='Jugadors';const icon=el('span','','👥');icon.setAttribute('aria-hidden','true');b.append(icon,el('strong','','Jugadors'));const results=document.getElementById('zok-nav-resultats-7dies');if(results)results.after(b);else fixed.append(b);
 if(isPlayers){b.classList.add('active');b.setAttribute('aria-current','page');b.onclick=()=>{const back=$('#jp-profile-panel:not([hidden]) .zok-jp-profile-title button');if(back)back.click();else window.scrollTo({top:0,behavior:'auto'})}}
 else b.onclick=()=>location.href='jugadors.html?v='+version;
 }
 if(isPlayers){playerPageNav();$('.zok-home-top').onclick=()=>go('home');$('#refresh-home').onclick=()=>go('import');const demo=new URLSearchParams(location.search).get('demo');if(['1','2'].includes(demo))document.querySelectorAll('a[href^="favorits.html"]').forEach(link=>{const u=new URL(link.href);u.searchParams.set('demo',demo);link.href=u.href})}else{
 const tab=new URLSearchParams(location.search).get('tab');
 if(tab==='import'){document.getElementById('refresh-home')?.click();}else if(tab&&/^(?:classificacions|resultats|favclub[1-9]\d*|favteam[1-9]\d*)$/.test(tab)){
 const target=tab==='resultats'?document.getElementById('zok-nav-resultats-7dies'):document.querySelector('.zok-bottom-nav [data-tab="'+tab+'"]');
 if(target)target.click();
 }
 }
}
if(document.readyState==='complete')mount();else document.addEventListener('DOMContentLoaded',mount,{once:true});
})();
