/* Navegació compartida de les dues pàgines de configuració.
   No toca imports, estat de notificacions ni dades esportives. */
(()=>{'use strict';
const version='20261126-disseny1';
function go(tab){if(tab==='players'){location.href='jugadors.html?v='+version;return}const u=new URL('index.html',location.href);u.searchParams.set('v',version);if(tab!=='home')u.searchParams.set('tab',tab);location.href=u.href}
function mount(){
 const mast=document.querySelector('main.app > .mast');
 if(!mast)return;
 // En Resultats, els accessos de capçalera han de sortir del mode de resultats.
 if(document.getElementById('home-cards'))mast.addEventListener('click',e=>{
  if(!document.body.classList.contains('zok-recent-mode')||!e.target.closest('.zok-home-top,#refresh-home'))return;
  document.body.classList.remove('zok-recent-mode');const panel=document.getElementById('zok-resultats-7dies');if(panel)panel.hidden=true;
 },true);
 if(!document.querySelector('main.zok-favorites-app')||document.querySelector('.zok-bottom-nav'))return;
 const nav=document.createElement('nav');nav.className='bottom zok-bottom-nav';nav.setAttribute('aria-label','Consultes ràpides');
 const scroll=document.createElement('div');scroll.className='zok-nav-scroll';scroll.setAttribute('aria-label','Clubs i equips favorits');
 const host=document.createElement('div');host.className='navgrid';scroll.append(host);
 const divider=document.createElement('span');divider.className='zok-nav-divider';divider.setAttribute('aria-hidden','true');
 const fixed=document.createElement('div');fixed.className='zok-nav-fixed';
 for(const [tab,label,icon] of [['classificacions','Classificacions','🏆'],['resultats','Resultats','🏁'],['players','Jugadors','👥']]){
  const b=document.createElement('button');b.type='button';b.className='navbtn';b.dataset.tab=tab;b.title=label;b.setAttribute('aria-label',label);
  const span=document.createElement('span');span.textContent=icon;span.setAttribute('aria-hidden','true');b.append(span);fixed.append(b)
 }
 nav.append(scroll,divider,fixed);document.body.append(nav);
 const render=()=>window.ZonaOKSharedNav?.render(host);
 render();window.addEventListener('zonaok:favorites-updated',render);window.addEventListener('storage',render);window.addEventListener('pageshow',render);
 document.addEventListener('change',e=>{if(e.target.matches('input[type="checkbox"],input[type="color"],input.zok-favorite-child-name'))requestAnimationFrame(render)});
 nav.addEventListener('click',e=>{const b=e.target.closest('button[data-tab]');if(b)go(b.dataset.tab)});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();