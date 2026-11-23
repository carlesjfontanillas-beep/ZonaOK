/* ZonaOK · accés als golejadors de Magí i Ton. */
'use strict';
(()=>{
  const urls={
    grupalevi:{title:'Golejadors · Magí',url:'https://www.hoqueipatins.fecapa.cat/?liga=4789&vista=estadisticas'},
    grupinfantil:{title:'Golejadors · Ton',url:'https://www.hoqueipatins.fecapa.cat/?liga=4786&vista=estadisticas'}
  };
  const byId=id=>document.getElementById(id);
  const goalsButton=byId('open-golejadors');
  const fecapaButton=byId('open-fecapa');
  const chatButton=byId('ask-section');
  if(!goalsButton||!fecapaButton||!chatButton)return;

  const style=document.createElement('style');
  style.textContent=`
    body[data-zok-goals-menu="grupalevi"] #results-section,
    body[data-zok-goals-menu="grupinfantil"] #results-section{margin-top:7px}
    body[data-zok-goals-menu="grupalevi"] #results-section .section-head,
    body[data-zok-goals-menu="grupinfantil"] #results-section .section-head{margin-bottom:6px}
    body[data-zok-goals-menu="grupalevi"] #results-section .section-head h2,
    body[data-zok-goals-menu="grupinfantil"] #results-section .section-head h2{margin:3px 0;font-size:clamp(21px,5.8vw,25px);line-height:1.08}
    body[data-zok-goals-menu="grupalevi"] #results-actions,
    body[data-zok-goals-menu="grupinfantil"] #results-actions{margin:6px 0 8px}
    body[data-zok-goals-menu="grupalevi"] #open-golejadors,
    body[data-zok-goals-menu="grupinfantil"] #open-golejadors{flex:1 1 100%;min-height:38px;padding:8px 12px;font-size:13px}
    .zok-golejadors-dialog:not([open]){display:none}
    .zok-golejadors-dialog[open]{display:flex;flex-direction:column}
    .zok-golejadors-dialog{position:fixed;margin:auto;inset:0;box-sizing:border-box;width:min(98vw,1050px);max-width:98vw;height:min(93vh,940px);height:min(93dvh,940px);max-height:93vh;max-height:93dvh;padding:0;overflow:hidden;border:1px solid #34536d;border-radius:17px;background:#f3f6fa;color:#082238;box-shadow:0 20px 70px #000a}
    .zok-golejadors-dialog::backdrop{background:#03172bd9}
    .zok-golejadors-header{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#061f38;color:#fff;padding:12px 14px;min-height:48px}
    .zok-golejadors-header strong{font-size:1rem;line-height:1.25}
    .zok-golejadors-close{flex:0 0 auto;border:1px solid #b5c9d3;border-radius:10px;background:#244860;color:#fff;font-size:1.5rem;font-weight:800;line-height:1;padding:6px 11px;cursor:pointer}
    .zok-golejadors-subtitle{background:#e3eaf0;padding:8px 14px;font-weight:700;font-size:.9rem;line-height:1.3}
    .zok-golejadors-frame{display:block;flex:1 1 auto;min-height:0;width:100%;border:0;background:#fff}
    .zok-golejadors-footer{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;background:#e3eaf0;padding:10px 12px}
    .zok-golejadors-hint{flex:1 1 200px;margin:0;font-size:.78rem;line-height:1.3;color:#234259}
    .zok-golejadors-external{display:inline-flex;align-items:center;justify-content:center;border-radius:10px;padding:10px 12px;background:#8f224c;color:#fff!important;text-decoration:none;font-weight:700;font-size:.85rem;white-space:nowrap}
    @media(max-width:600px){.zok-golejadors-dialog{width:96vw;max-width:96vw;height:94dvh;max-height:94dvh;border-radius:15px}.zok-golejadors-footer{padding-bottom:max(10px,env(safe-area-inset-bottom))}}
  `;
  document.head.append(style);

  let dialog,frame;
  function buildDialog(){
    dialog=document.createElement('dialog');
    dialog.className='zok-golejadors-dialog';
    dialog.setAttribute('aria-label','Golejadors oficials de FECAPA');
    const header=document.createElement('div');header.className='zok-golejadors-header';
    const heading=document.createElement('strong');heading.textContent='GOLEJADORS · FECAPA';
    const close=document.createElement('button');close.type='button';close.className='zok-golejadors-close';close.textContent='×';close.setAttribute('aria-label','Tancar golejadors');close.onclick=()=>dialog.close();
    header.append(heading,close);
    const subtitle=document.createElement('div');subtitle.className='zok-golejadors-subtitle';
    frame=document.createElement('iframe');frame.className='zok-golejadors-frame';frame.title='Golejadors oficials de FECAPA';frame.loading='eager';
    frame.setAttribute('sandbox','allow-forms allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox');
    const footer=document.createElement('div');footer.className='zok-golejadors-footer';
    const hint=document.createElement('p');hint.className='zok-golejadors-hint';hint.textContent='Si FECAPA no mostra la taula dins la finestra, obre-la directament amb el botó.';
    const external=document.createElement('a');external.className='zok-golejadors-external';external.target='_blank';external.rel='noopener';external.textContent='Obrir a FECAPA ↗';
    footer.append(hint,external);dialog.append(header,subtitle,frame,footer);document.body.append(dialog);
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
    dialog.addEventListener('close',()=>frame.removeAttribute('src'));
    return {subtitle,external};
  }
  let parts;
  function activeMenu(){return document.querySelector('.navbtn.active')?.dataset.tab||'home';}
  function updateButtons(){
    const show=Object.hasOwn(urls,activeMenu());
    document.body.dataset.zokGoalsMenu=show?activeMenu():'';
    goalsButton.hidden=!show;fecapaButton.hidden=show;chatButton.hidden=show;
    goalsButton.setAttribute('aria-label',show?'Obrir golejadors oficials de '+(activeMenu()==='grupalevi'?'Magí':'Ton'):'Golejadors');
  }
  goalsButton.addEventListener('click',()=>{
    const page=urls[activeMenu()];if(!page)return;
    if(!dialog)parts=buildDialog();
    parts.subtitle.textContent=page.title;
    parts.external.href=page.url;
    dialog.showModal();frame.src=page.url;
  });
  document.addEventListener('click',event=>{
    if(event.target.closest?.('[data-tab]'))requestAnimationFrame(updateButtons);
  });
  updateButtons();
})();
