/* ZonaOK: un sol controlador tàctil, amb bloqueig de l'eix i sense buidar caches. */
(function(root){
'use strict';
function axis(dx,dy,week,pull){
 const x=Math.abs(dx),y=Math.abs(dy);
 if(Math.max(x,y)<12)return '';
 if(x>y*1.25)return week?'week':'native';
 if(y>x*1.25)return pull&&dy>0?'pull':'native';
 return Math.max(x,y)>30?'native':'';
}
function action(kind,dx,dy){
 if(kind==='week'&&Math.abs(dx)>=45&&Math.abs(dx)>Math.abs(dy)*1.15)return dx<0?'next':'previous';
 if(kind==='pull'&&dy>=72&&dy>Math.abs(dx)*1.25)return 'refresh';
 return '';
}
function refreshTarget(flags){
 if(flags.players)return 'ZonaOKRefreshPlayers';
 if(flags.recent)return 'ZonaOKRefreshRecent';
 if(flags.dashboard)return 'ZonaOKRefreshDashboard';
 return 'ZonaOKRefreshVisible';
}
if(typeof module!=='undefined'&&module.exports){module.exports={axis,action,refreshTarget};return}
const mount=()=>{
 const main=document.querySelector('main.app');if(!main||(!root.ZonaOKWeekGesture&&!main.classList.contains('zok-jp-app')))return;
 const status=document.createElement('div');status.id='zok-pull-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const css=document.createElement('style');css.textContent=`
 #zok-pull-status{position:fixed;top:max(9px,env(safe-area-inset-top));left:50%;transform:translate(-50%,-150%);z-index:9999;background:#06243e;color:#f6fbff;border:1px solid #6e9db6;border-radius:22px;padding:9px 15px;font-size:13px;font-weight:700;transition:transform .12s ease;max-width:92vw;text-align:center;pointer-events:none}
 #zok-pull-status.zok-visible{transform:translate(-50%,0)}
 .zok-nav-scroll{touch-action:pan-x!important}
 main.app button,main.app a{touch-action:manipulation}
 `;document.head.append(css);document.body.append(status);
 let gesture=null,refreshing=false,timer=0,blockedUntil=0,blockedPoint=null;
 const show=msg=>{if(status.textContent!==msg)status.textContent=msg;status.classList.add('zok-visible')};
 const hide=()=>{if(!refreshing)status.classList.remove('zok-visible')};
 async function refresh(){
  if(refreshing)return;refreshing=true;clearTimeout(timer);show('Actualitzant dades…');
  try{
   const target=refreshTarget({players:main.classList.contains('zok-jp-app'),recent:document.body.classList.contains('zok-recent-mode'),dashboard:document.body.classList.contains('zok-ui-import')});
   const fn=root[target],ok=typeof fn==='function'&&await fn();
   show(ok?'Dades de GitHub recarregades':'No s’han pogut recarregar totes les dades');
  }catch(_){show('Error de connexió · Es manté la vista actual')}
  finally{refreshing=false;timer=setTimeout(hide,2400)}
 }
 const ignore='input,textarea,select,summary,[contenteditable],dialog,.standings-wrap,.zok-ranking-scroll,.zok-nav-scroll,.zok-suggest-wrap';
 const top=()=>Math.max(0,window.scrollY||0,document.scrollingElement?.scrollTop||0)<=8;
 const nestedScroll=target=>{for(let n=target;n&&n!==main;n=n.parentElement){const c=getComputedStyle(n);if((/(auto|scroll)/.test(c.overflowX)&&n.scrollWidth>n.clientWidth+2)||(/(auto|scroll)/.test(c.overflowY)&&n.scrollHeight>n.clientHeight+2))return true}return false};
 main.addEventListener('touchstart',e=>{
  gesture=null;if(e.touches.length!==1||document.querySelector('dialog[open]')||e.target.closest?.(ignore)||nestedScroll(e.target))return;
  const t=e.touches[0];if(t.clientX<20||t.clientX>innerWidth-20)return;
  const control=e.target.closest?.('a,button,[role="button"]:not(.match),.zok-week-nav');
  const week=!control&&root.ZonaOKWeekGesture?.enabled(),pull=!control&&!refreshing&&top();
  if(week||pull)gesture={id:t.identifier,x:t.clientX,y:t.clientY,week,pull,kind:''};
 },{passive:true});
 main.addEventListener('touchmove',e=>{
  if(!gesture)return;if(e.touches.length!==1){gesture=null;hide();return}
  const t=e.touches[0];if(t.identifier!==gesture.id){gesture=null;hide();return}
  const dx=t.clientX-gesture.x,dy=t.clientY-gesture.y;
  if(!gesture.kind)gesture.kind=axis(dx,dy,gesture.week,gesture.pull&&top());
  if(gesture.kind==='native'){gesture=null;return}
  if(gesture.kind==='pull'){
   if(e.cancelable)e.preventDefault();
   show(dy>=72?'Deixa anar per actualitzar':'Estira per actualitzar');
  }else if(gesture.kind==='week'&&e.cancelable)e.preventDefault();
 },{passive:false});
 main.addEventListener('touchend',e=>{
  const g=gesture;gesture=null;if(!g)return;
  const t=Array.from(e.changedTouches).find(x=>x.identifier===g.id);if(!t||e.touches.length){hide();return}
  const dx=t.clientX-g.x,dy=t.clientY-g.y,kind=g.kind||axis(dx,dy,g.week,g.pull&&top()),result=action(kind,dx,dy);
  if(result==='refresh'&&!top()){hide();return}
  if(!result){hide();return}
  if((result==='next'||result==='previous')&&!root.ZonaOKWeekGesture?.enabled()){hide();return}
  if(e.cancelable)e.preventDefault();blockedUntil=performance.now()+350;blockedPoint={x:t.clientX,y:t.clientY};
  if(result==='refresh')void refresh();else{hide();requestAnimationFrame(()=>root.ZonaOKWeekGesture.change(result==='next'?1:-1))}
 },{passive:false});
 main.addEventListener('touchcancel',()=>{gesture=null;hide()},{passive:true});
 main.addEventListener('click',e=>{if(e.detail&&blockedPoint&&performance.now()<blockedUntil&&Math.hypot(e.clientX-blockedPoint.x,e.clientY-blockedPoint.y)<35){e.preventDefault();e.stopImmediatePropagation()}},true);
 root.ZonaOKPullRefresh=refresh;
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})(typeof window!=='undefined'?window:globalThis);
