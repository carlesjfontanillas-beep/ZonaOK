/* ZonaOK · accessos a classificació i golejadors de Magí i Ton. */
'use strict';
(()=>{
  const pages={
    grupalevi:{name:'Magí · Aleví OR 3',league:'4789'},
    grupinfantil:{name:'Ton · Infantil OR 10',league:'4786'}
  };
  const byId=id=>document.getElementById(id);
  const goalsButton=byId('open-golejadors');
  const standingsButton=byId('open-classificacio');
  const fecapaButton=byId('open-fecapa');
  const chatButton=byId('ask-section');
  if(!goalsButton||!standingsButton||!fecapaButton||!chatButton)return;

  const css=document.createElement('style');
  css.textContent=`
    body[data-zok-special-menu="grupalevi"] #results-section,
    body[data-zok-special-menu="grupinfantil"] #results-section{margin-top:7px}
    body[data-zok-special-menu="grupalevi"] #results-section .section-head,
    body[data-zok-special-menu="grupinfantil"] #results-section .section-head{margin-bottom:6px}
    body[data-zok-special-menu="grupalevi"] #results-section .section-head h2,
    body[data-zok-special-menu="grupinfantil"] #results-section .section-head h2{margin:3px 0;font-size:clamp(21px,5.8vw,25px);line-height:1.08}
    body[data-zok-special-menu="grupalevi"] #results-actions,
    body[data-zok-special-menu="grupinfantil"] #results-actions{margin:6px 0 8px}
    body[data-zok-special-menu="grupalevi"] #open-classificacio,
    body[data-zok-special-menu="grupinfantil"] #open-classificacio,
    body[data-zok-special-menu="grupalevi"] #open-golejadors,
    body[data-zok-special-menu="grupinfantil"] #open-golejadors{flex:1 1 calc(50% - 4px);min-width:0;min-height:38px;padding:8px 5px;font-size:13px}
    .zok-special-dialog:not([open]){display:none}
    .zok-special-dialog[open]{display:flex;flex-direction:column}
    .zok-special-dialog{position:fixed;margin:auto;inset:0;box-sizing:border-box;width:min(98vw,1050px);max-width:98vw;height:min(93vh,940px);height:min(93dvh,940px);max-height:93vh;max-height:93dvh;padding:0;overflow:hidden;border:1px solid #34536d;border-radius:17px;background:#f3f6fa;color:#082238;box-shadow:0 20px 70px #000a}
    .zok-special-dialog::backdrop{background:#03172bd9}
    .zok-special-header{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#061f38;color:#fff;padding:12px 14px;min-height:48px}
    .zok-special-header strong{font-size:1rem;line-height:1.25}
    .zok-special-close{flex:0 0 auto;border:1px solid #b5c9d3;border-radius:10px;background:#244860;color:#fff;font-size:1.5rem;font-weight:800;line-height:1;padding:6px 11px;cursor:pointer}
    .zok-special-subtitle{background:#e3eaf0;padding:8px 14px;font-weight:700;font-size:.9rem;line-height:1.3}
    .zok-special-frame{display:block;flex:1 1 auto;min-height:0;width:100%;border:0;background:#fff}
    .zok-special-footer{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;background:#e3eaf0;padding:10px 12px}
    .zok-special-hint{flex:1 1 200px;margin:0;font-size:.78rem;line-height:1.3;color:#234259}
    .zok-special-link{display:inline-flex;align-items:center;justify-content:center;border-radius:10px;padding:10px 12px;background:#8f224c;color:#fff!important;text-decoration:none;font-weight:700;font-size:.85rem;white-space:nowrap}
    .zok-special-dialog[data-kind="standings"] .zok-special-link{background:#245d9f}
    @media(max-width:600px){.zok-special-dialog{width:96vw;max-width:96vw;height:94dvh;max-height:94dvh;border-radius:15px}.zok-special-footer{padding-bottom:max(10px,env(safe-area-inset-bottom))}}
  `;
  document.head.append(css);

  const dialogs={};
  function openDialog(kind,page){
    let item=dialogs[kind];
    if(!item){
      const dialog=document.createElement('dialog');dialog.className='zok-special-dialog';dialog.dataset.kind=kind;
      dialog.setAttribute('aria-label',kind==='standings'?'Classificació oficial de FECAPA':'Golejadors oficials de FECAPA');
      const header=document.createElement('div');header.className='zok-special-header';
      const heading=document.createElement('strong');heading.textContent=kind==='standings'?'CLASSIFICACIÓ · FECAPA':'GOLEJADORS · FECAPA';
      const close=document.createElement('button');close.type='button';close.className='zok-special-close';close.textContent='×';close.setAttribute('aria-label','Tancar finestra');close.onclick=()=>dialog.close();header.append(heading,close);
      const subtitle=document.createElement('div');subtitle.className='zok-special-subtitle';
      const frame=document.createElement('iframe');frame.className='zok-special-frame';frame.loading='eager';frame.title=kind==='standings'?'Classificació oficial de FECAPA':'Golejadors oficials de FECAPA';
      frame.setAttribute('sandbox','allow-forms allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox');
      const footer=document.createElement('div');footer.className='zok-special-footer';
      const hint=document.createElement('p');hint.className='zok-special-hint';hint.textContent='Si FECAPA no mostra la taula dins la finestra, obre-la directament amb el botó.';
      const link=document.createElement('a');link.className='zok-special-link';link.target='_blank';link.rel='noopener';link.textContent='Obrir a FECAPA ↗';footer.append(hint,link);
      dialog.append(header,subtitle,frame,footer);document.body.append(dialog);
      dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
      dialog.addEventListener('close',()=>frame.removeAttribute('src'));
      item=dialogs[kind]={dialog,subtitle,frame,link};
    }
    const view=kind==='standings'?'clasificaciones':'estadisticas';
    const url='https://www.hoqueipatins.fecapa.cat/?liga='+page.league+'&vista='+view;
    item.subtitle.textContent=(kind==='standings'?'Classificació':'Golejadors')+' · '+page.name;
    item.link.href=url;item.dialog.showModal();item.frame.src=url;
  }
  function activeMenu(){return document.querySelector('.navbtn.active')?.dataset.tab||'home';}
  function updateButtons(){
    const menu=activeMenu(),show=Object.hasOwn(pages,menu);
    document.body.dataset.zokSpecialMenu=show?menu:'';
    goalsButton.hidden=!show;standingsButton.hidden=!show;fecapaButton.hidden=show;chatButton.hidden=show;
    goalsButton.setAttribute('aria-label',show?'Obrir golejadors oficials de '+pages[menu].name:'Golejadors');
    standingsButton.setAttribute('aria-label',show?'Obrir classificació de '+pages[menu].name:'Classificació');
  }
  goalsButton.addEventListener('click',()=>{const page=pages[activeMenu()];if(page)openDialog('goals',page);});
  standingsButton.addEventListener('click',()=>{const page=pages[activeMenu()];if(!page)return;if(typeof window.ZonaOKShowStanding==='function')window.ZonaOKShowStanding(page.league);else openDialog('standings',page);});
  document.addEventListener('click',event=>{if(event.target.closest?.('[data-tab]'))requestAnimationFrame(updateButtons);});
  updateButtons();
})();
