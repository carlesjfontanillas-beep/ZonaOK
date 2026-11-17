/* ZonaOK · launcher independent de ChatGPT · sense API, cap dada esportiva local */
'use strict';
const URLS = Object.freeze({alevi:'https://www.hoqueipatins.fecapa.cat/?liga=4789&vista=calendar',infantil:'https://www.hoqueipatins.fecapa.cat/?liga=4786&vista=calendar',juvenil:'https://www.hoqueipatins.fecapa.cat/?liga=4784&vista=calendar',agenda:'https://www.hoqueipatins.fecapa.cat/ag/'});
const COMMON=`Respon en català. Consulta ARA la informació esportiva exclusivament al lloc oficial https://www.hoqueipatins.fecapa.cat (no altres webs ni dades antigues de converses). Per a les pistes i resultats consulta també ${URLS.agenda}. Si FECAPA no permet recuperar les dades dinàmiques, explica-ho i no reutilitzis una captura o consulta anterior com a informació actual. No inventis dates, rivals, classificacions, resultats, pistes ni escuts. Mostra les dades verificades en targetes agradables per a iPhone, amb escuts dels clubs si es poden verificar, marcadors quan existeixin, data, hora a Europe/Madrid, pista, botó o enllaç de Google Maps i accés per afegir el partit al calendari quan data i hora siguin confirmades. Si no pots verificar un camp, indica "Pendent de verificar". Quan calgui, cita l'enllaç oficial de cada competició.`;
const prompts={
 home:`Consulta els partits de la setmana actual (dilluns-diumenge, Europe/Madrid) EXACTAMENT d'aquests equips: Barça Aleví OR 3 (lliga 4789, ${URLS.alevi}); CP Sant Celoni B Infantil OR 10 (lliga 4786, ${URLS.infantil}); CP Sant Celoni B Juvenil OR 6 (lliga 4784, ${URLS.juvenil}). Ordena per data i hora. ${COMMON}`,
 alevi:`Consulta els partits de la setmana actual del Barça ALEVI OR 3 a la competició ${URLS.alevi}. Filtra exclusivament l'equip Barça d'aquest grup. ${COMMON}`,
 infantil:`Consulta els partits de la setmana actual del CP Sant Celoni B INFANTIL OR 10 a ${URLS.infantil}. ${COMMON}`,
 juvenil:`Consulta els partits de la setmana actual del CP Sant Celoni B JUVENIL OR 6 a ${URLS.juvenil}. ${COMMON}`,
 celoni:`Consulta TOTS els partits disputats i programats de la setmana actual de TOTS els equips del CP Sant Celoni a FECAPA (no només Infantil B i Juvenil B). Busca totes les seves competicions dins de FECAPA, agrupa per dia i categoria, mostra resultats dels ja disputats. ${COMMON}`,
 barca:`Consulta TOTS els partits disputats i programats de la setmana actual de TOTS els equips d'hoquei patins del FC Barcelona a FECAPA (no només l'Aleví). Busca totes les competicions del club dins de FECAPA, agrupa per dia i categoria, mostra resultats dels ja disputats. ${COMMON}`,
 classificacions:`Consulta les classificacions ACTUALS completes de FECAPA: Aleví OR 3 ${URLS.alevi.replace('vista=calendar','vista=clasificaciones')}; Infantil OR 10 ${URLS.infantil.replace('vista=calendar','vista=clasificaciones')}; Juvenil OR 6 ${URLS.juvenil.replace('vista=calendar','vista=clasificaciones')}. Destaca respectivament el Barça, CP Sant Celoni B Infantil i CP Sant Celoni B Juvenil. Mostra posició, punts, PJ, PG, PE, PP, GF, GC si la font els ofereix. ${COMMON}`,
 grupalevi:`Consulta TOTS els partits i resultats disponibles de la competició FECAPA ALEVÍ OR 3 (lliga 4789) ${URLS.alevi}, no només Barça. Ordena els partits per data DESCENDENT, el més recent a dalt, incloent resultats quan constin, rivals i pistes. ${COMMON}`,
 grupinfantil:`Consulta TOTS els partits i resultats disponibles de la competició FECAPA INFANTIL OR 10 (lliga 4786) ${URLS.infantil}, no només Sant Celoni. Ordena els partits per data DESCENDENT, el més recent a dalt, incloent resultats quan constin, rivals i pistes. ${COMMON}`
};
const notice=document.getElementById('notice'),text=document.getElementById('notice-text');let last='home';
function openChat(key){
  if(!prompts[key])return;
  last=key; const prompt=prompts[key];
  const url='https://chatgpt.com/?q='+encodeURIComponent(prompt);
  // The URL parameter is not an official guaranteed API. It may prefill only.
  notice.classList.add('show');
  text.textContent='Obrint ChatGPT amb la consulta preparada. Si no apareix o no s’envia, prem «Copiar pregunta» i enganxa-la al xat.';
  window.open(url,'_blank','noopener,noreferrer');
}
document.querySelectorAll('[data-query]').forEach(el=>el.addEventListener('click',()=>openChat(el.dataset.query)));
document.getElementById('main-query').addEventListener('click',()=>openChat('home'));
document.getElementById('retry-query').addEventListener('click',()=>openChat(last));
document.getElementById('dismiss').addEventListener('click',()=>notice.classList.remove('show'));
document.getElementById('copy-query').addEventListener('click',async()=>{const prompt=prompts[last];try{await navigator.clipboard.writeText(prompt);text.textContent='Pregunta copiada. Obre ChatGPT i enganxa-la al quadre del missatge.';}catch(e){const area=document.createElement('textarea');area.value=prompt;area.style.cssText='position:fixed;left:-9999px';document.body.appendChild(area);area.select();try{document.execCommand('copy');text.textContent='Pregunta copiada. Enganxa-la a ChatGPT.';}catch(e2){text.textContent='No s’ha pogut copiar automàticament. Obre ChatGPT i prova de nou.';}area.remove();}});
function weekLabel(){const now=new Date();const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);const y=+parts.find(p=>p.type==='year').value,m=+parts.find(p=>p.type==='month').value,d=+parts.find(p=>p.type==='day').value;const ref=new Date(Date.UTC(y,m-1,d));const wd=(ref.getUTCDay()+6)%7;const mon=new Date(ref);mon.setUTCDate(ref.getUTCDate()-wd);const sun=new Date(mon);sun.setUTCDate(mon.getUTCDate()+6);const fmt=x=>new Intl.DateTimeFormat('ca-ES',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(x);document.getElementById('week').textContent=fmt(mon)+' – '+fmt(sun);}
weekLabel();
