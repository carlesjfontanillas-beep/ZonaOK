(()=>{
'use strict';
// Preferència local de visibilitat, no autenticació de servidor.
// GitHub Actions continua exigint permisos GitHub per executar workflows.
const KEY='ZONAOK_ADMIN_DEVICE_V1', DIGEST='a4031c0ee20c4c528a132c9b612c607ac398dcd1ed7e09a44caa2ebccf91e4c6';
const allowed=()=>{try{return localStorage.getItem(KEY)==='enabled'}catch{return false}};
const style=document.createElement('style');style.textContent='html:not(.zok-admin-device) #refresh-home,html:not(.zok-admin-device) body .zok-ui-import-section{display:none!important}.zok-brand-home{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}';document.head.append(style);
function sync(){
 const yes=allowed();document.documentElement.classList.toggle('zok-admin-device',yes);
 if(!yes&&document.body?.classList.contains('zok-ui-import'))document.querySelector('.zok-home-top')?.click();
 return yes;
}
sync();window.ZonaOKAdminDevice={allowed};
let busy=false;
async function activate(){
 if(busy)return;busy=true;
 try{
  if(allowed()){
   if(confirm('Desactivar les eines d’administració en aquest dispositiu?')){localStorage.removeItem(KEY);sync()}
   return;
  }
  const code=prompt('ZONAOK · Codi privat per activar les actualitzacions en aquest dispositiu:');
  if(code===null)return;
  if(!globalThis.crypto?.subtle){alert('Cal obrir ZONAOK amb HTTPS.');return}
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(code.trim()))),x=>x.toString(16).padStart(2,'0')).join('');
  if(hash!==DIGEST){alert('Codi incorrecte.');return}
  localStorage.setItem(KEY,'enabled');sync();alert('Actualitzacions activades en aquest dispositiu.');
 }catch{alert('No s’ha pogut desar la preferència en aquest dispositiu.')}
 finally{busy=false}
}
document.addEventListener('click',e=>{if(e.target.closest?.('#refresh-home')&&!allowed()){e.preventDefault();e.stopImmediatePropagation()}},true);
function setup(){
 const logo=document.querySelector('.zok-brand-home');let timer=0,held=false,x=0,y=0;
 const stop=()=>clearTimeout(timer);
 if(logo){
  logo.addEventListener('pointerdown',e=>{if(e.button!==0||!e.isPrimary)return;stop();held=false;x=e.clientX;y=e.clientY;timer=setTimeout(()=>{held=true;activate()},1100)});
  window.addEventListener('pointermove',e=>{if(Math.hypot(e.clientX-x,e.clientY-y)>10)stop()});
  window.addEventListener('pointerup',stop);window.addEventListener('pointercancel',stop);window.addEventListener('blur',stop);
  logo.addEventListener('contextmenu',e=>e.preventDefault());
  logo.addEventListener('click',e=>{if(held){held=false;e.preventDefault();e.stopImmediatePropagation()}},true);
 }
 const url=new URL(location.href);
 if(url.searchParams.get('admin')==='1'){url.searchParams.delete('admin');history.replaceState(null,'',url.href);activate()}
 sync();
}
window.addEventListener('storage',e=>{if(e.key===KEY||e.key===null)sync()});
window.addEventListener('pageshow',sync);
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();
