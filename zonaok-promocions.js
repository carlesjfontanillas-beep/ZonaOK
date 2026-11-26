/* ZonaOK · Campanyes emergents, independents de les notificacions push. */
(() => {
  'use strict';
  if (window.ZonaOKPromocions) return;
  window.ZonaOKPromocions = true;
  const KEY = 'ZONAOK_PROMOCIONS_V1';
  const base = new URL('./', document.currentScript.src);
  const previewOpening = new URL(window.location.href).searchParams.get('promo');
  let busy = false, hiddenAt = null, returnAfter = 60000, initialPending = true;
  const text = v => typeof v === 'string' ? v.trim() : '';
  function read() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || '{}');
      return { opens: Number.isSafeInteger(raw.opens) && raw.opens >= 0 ? raw.opens : 0,
        shown: Array.isArray(raw.shown) ? raw.shown.filter(x => typeof x === 'string') : [] };
    } catch { return { opens: 0, shown: [] }; }
  }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); return true; }
    catch { return false; }
  }
  function safeUrl(value, image = false) {
    if (!text(value)) return '';
    try {
      const u = new URL(value, base);
      if (u.protocol !== 'https:' || u.username || u.password) return '';
      if (image && (u.origin !== base.origin || !u.pathname.startsWith(base.pathname))) return '';
      return u.href;
    } catch { return ''; }
  }
  function eligible(c, state, now) {
    if (!c || c.enabled !== true || !text(c.id) || state.shown.includes(c.id) ||
        c.opening !== state.opens || !text(c.title) || !text(c.message)) return false;
    const start = c.startsAt == null ? -Infinity : Date.parse(c.startsAt);
    const end = c.endsAt == null ? Infinity : Date.parse(c.endsAt);
    return start <= now && now < end;
  }
  function element(tag, value) {
    const node = document.createElement(tag);
    if (value) node.textContent = value;
    return node;
  }
  const icons = {
    share:'<path d="M12 16V3m-5 5 5-5 5 5M6 11H4v10h16V11h-2"/>',
    star:'<path d="m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z"/>',
    layers:'<path d="m12 3 10 5-10 5L2 8zm-10 9 10 5 10-5M2 16l10 5 10-5"/>',
    heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
    phone:'<rect x="6" y="2" width="12" height="20" rx="3"/><path d="m9 12 4-4m-2 7 4-4M10 19h4"/>',
    copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h3"/>',
    network:'<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m9 11 6-4m-6 6 6 4"/>'
  };
  function icon(name) {
    const s = document.createElementNS('http://www.w3.org/2000/svg','svg');
    s.setAttribute('viewBox','0 0 24 24'); s.setAttribute('fill','none');
    s.setAttribute('stroke','currentColor'); s.setAttribute('stroke-width','1.9');
    s.setAttribute('stroke-linecap','round'); s.setAttribute('stroke-linejoin','round');
    s.setAttribute('aria-hidden','true'); s.innerHTML = icons[name] || icons.star; return s;
  }
  function show(c, state, preview = false) {
    if (document.visibilityState !== 'visible' || document.querySelector('#zok-promo-dialog')) return false;
    const dialog = element('dialog');
    if (typeof dialog.showModal !== 'function') return false;
    dialog.id = 'zok-promo-dialog';
    dialog.setAttribute('aria-labelledby','zok-promo-title');
    dialog.setAttribute('aria-describedby','zok-promo-message');
    const style = element('style', `
      #zok-promo-dialog{box-sizing:border-box;width:min(92vw,400px);max-height:88vh;max-height:88dvh;overflow:auto;overscroll-behavior:contain;border:2px solid #7295b0;border-radius:22px;padding:14px 20px 20px;background:linear-gradient(155deg,#082a45,#061d33 80%);color:#f2f7fb;text-align:center;box-shadow:0 12px 50px #0009;font:inherit;margin:auto}
      #zok-promo-dialog::backdrop{background:rgba(0,12,25,.76)}
      #zok-promo-dialog *{box-sizing:border-box} #zok-promo-dialog button{font:inherit;cursor:pointer}
      #zok-promo-dialog button:focus-visible,#zok-promo-dialog a:focus-visible{outline:2px solid #fff;outline-offset:3px}
      #zok-promo-dialog .zp-close{position:absolute;top:5px;right:5px;background:none;border:0;color:#fff;width:44px;height:44px;font-size:30px}
      #zok-promo-dialog .zp-brand{font-weight:950;font-size:26px;letter-spacing:-.06em;margin:10px 24px 0}
      #zok-promo-dialog .zp-brand span{color:#ffd54a}
      #zok-promo-dialog .zp-strap{font-size:11px;font-weight:700;color:#d4e5f3;margin:0 0 16px}
      #zok-promo-dialog h2{color:#fff;font-size:clamp(23px,6.6vw,32px);line-height:1.08;letter-spacing:-.035em;font-weight:900;margin:10px 0 12px}
      #zok-promo-dialog .zp-underline{width:76px;height:4px;background:#ffd54a;border-radius:99px;margin:0 auto 15px}
      #zok-promo-dialog p{color:#e1edf7;line-height:1.35;font-size:14px;margin:0 0 12px;white-space:pre-wrap;overflow-wrap:anywhere}
      #zok-promo-dialog .zp-step{display:flex;align-items:center;gap:12px;text-align:left;padding:13px 0;border-bottom:1px solid #41647c}
      #zok-promo-dialog .zp-step:last-child{border:0}
      #zok-promo-dialog svg{width:32px;height:32px;flex:none;color:#ffd54a}
      #zok-promo-dialog .zp-step strong{display:block;color:#fff;font-size:16px;line-height:1.15;margin-bottom:4px}
      #zok-promo-dialog .zp-step p{font-size:13px;margin:0}
      #zok-promo-dialog .zp-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:18px 0}
      #zok-promo-dialog .zp-action{min-height:105px;border:0;border-radius:12px;background:#123650;color:#fff;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:8px;padding:10px;font-size:14px;font-weight:800;line-height:1.2}
      #zok-promo-dialog .zp-action svg{width:38px;height:38px}
      #zok-promo-dialog .zp-number{width:100%;display:flex;justify-content:center;align-items:center;gap:9px;color:#061d33;background:#ffe699;border:0;border-radius:99px;padding:10px 12px;min-height:48px;font-size:clamp(21px,6vw,28px);font-weight:900;letter-spacing:.02em}
      #zok-promo-dialog .zp-number svg{color:#061d33;width:20px;height:20px}
      #zok-promo-dialog .zp-status{font-size:12px;min-height:18px;margin:5px 0;color:#d4e5f3}
      #zok-promo-dialog .zp-dismiss{display:block;width:100%;min-height:46px;background:#ffd000;color:#061d33;border:0;border-radius:99px;padding:11px 15px;font-weight:900;font-size:16px;margin-top:12px}
      #zok-promo-dialog .zp-heart svg{width:54px;height:54px}
      #zok-promo-dialog .zp-milestone{font-size:64px;color:#ffd54a;font-weight:950;line-height:1}
      #zok-promo-dialog .zp-milestone small{display:block;color:#fff;font-size:17px}
      #zok-promo-dialog .zp-preview{color:#b4d2e8;font-size:11px;margin-top:5px}
      #zok-promo-dialog a.zp-link{display:block;color:#ffd54a;font-weight:750;margin:12px 0}
    `);
    const button = (label, cls, handler) => {
      const b=element('button',label); b.type='button'; b.className=cls;
      b.addEventListener('click',handler); return b;
    };
    const close=button('×','zp-close',()=>dialog.close());
    close.setAttribute('aria-label','Tanca el missatge');
    const brand=element('div','Zona'); brand.className='zp-brand'; brand.append(element('span','OK'));
    const strap=element('div','El teu hoquei'); strap.className='zp-strap';
    dialog.append(close,brand,strap);
    if(preview){const mark=element('div','PREVISUALITZACIÓ · '+c.opening+'a obertura');mark.className='zp-preview';dialog.append(mark);}
    if(c.kind==='support' && c.opening===50){
      const milestone=element('div','50');milestone.className='zp-milestone';milestone.append(element('small','obertures'));dialog.append(milestone);
    }else if(c.kind==='support' && c.opening===25){
      const heart=element('div');heart.className='zp-heart';heart.append(icon('heart'));dialog.append(heart);
    }
    const title=element('h2',text(c.title));title.id='zok-promo-title';
    const underline=element('div');underline.className='zp-underline';dialog.append(title,underline);
    const message=element('p',text(c.message));message.id='zok-promo-message';dialog.append(message);
    const imgUrl=safeUrl(c.image,true);
    if(imgUrl){const img=element('img');img.src=imgUrl;img.alt=text(c.imageAlt);img.style.cssText='max-width:100%;max-height:180px;object-fit:contain';img.addEventListener('error',()=>img.remove(),{once:true});dialog.append(img);}
    if(c.kind==='welcome'){
      const steps=element('div');
      for(const step of Array.isArray(c.steps)?c.steps:[]){
        const row=element('div');row.className='zp-step';
        const copy=element('div');copy.append(element('strong',text(step.title)),element('p',text(step.message)));
        row.append(icon(step.icon),copy);steps.append(row);
      }
      dialog.append(steps);
    }
    if(c.kind==='support'){
      const status=element('p');status.className='zp-status';status.setAttribute('role','status');
      const phone=text(c.bizumPhone).replace(/[^0-9]/g,'');
      async function copyValue(value,success){
        try{await navigator.clipboard.writeText(value);status.textContent=success;}
        catch{status.textContent='Copia manualment: '+value;}
      }
      const actions=element('div');actions.className='zp-actions';
      const share=button('','zp-action',async()=>{
        const data={title:'ZonaOK · El teu hoquei',text:'Tot el hoquei català, al teu mòbil!',url:base.href};
        if(typeof navigator.share==='function'){try{await navigator.share(data);return;}catch(e){if(e?.name==='AbortError')return;}}
        await copyValue(base.href,'Enllaç copiat!');
      });
      share.append(icon('network'),element('span','Comparteix-la a les xarxes'));
      const support=button('','zp-action',()=>{if(phone)void copyValue(phone,'Número de Bizum copiat!');});
      support.append(icon('phone'),element('span','Col·labora amb un Bizum'));
      actions.append(share,support);dialog.append(actions);
      if(phone){
        const number=button('','zp-number',()=>void copyValue(phone,'Número de Bizum copiat!'));
        number.append(element('span',phone.replace(/(\d{3})(?=\d)/g,'$1 ')),icon('copy'));
        number.setAttribute('aria-label','Copia el número de Bizum '+phone);dialog.append(number);
      }
      dialog.append(status);
    }
    const url=safeUrl(c.buttonUrl);
    if(url&&text(c.buttonText)){const link=element('a',text(c.buttonText));link.className='zp-link';link.href=url;link.target='_blank';link.rel='noopener noreferrer';dialog.append(link);}
    dialog.append(button(text(c.dismissText)||'Tancar','zp-dismiss',()=>dialog.close()));
    const previous=document.activeElement;
    dialog.addEventListener('close',()=>{dialog.remove();style.remove();if(previous&&previous.isConnected)previous.focus({preventScroll:true});},{once:true});
    document.head.append(style);document.body.append(dialog);
    try{dialog.showModal();}catch{dialog.remove();style.remove();return false;}
    if(!preview&&!save({...state,shown:[...state.shown,c.id]})){dialog.close();return false;}
    close.focus({preventScroll:true});return true;
  }
  async function opening() {
    if (busy || document.visibilityState !== 'visible') return;
    busy = true;
    try {
      const response = await fetch(new URL('promocions.json', base), {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return;
      const cfg = await response.json();
      if (cfg?.schema !== 1 || !Array.isArray(cfg.campaigns)) return;
      if (previewOpening !== null) {
        const c = cfg.campaigns.find(c => String(c.opening) === previewOpening);
        if(c) show(c,null,true);
        return;
      }
      if (Number.isFinite(cfg.returnAfterSeconds) && cfg.returnAfterSeconds >= 10)
        returnAfter = cfg.returnAfterSeconds * 1000;
      if (cfg.enabled !== true || !cfg.campaigns.some(c => c?.enabled === true) ||
          document.visibilityState !== 'visible') return;
      const state = read(); state.opens += 1;
      if (!save(state)) return;
      const campaign = cfg.campaigns.find(c => eligible(c, state, Date.now()));
      if (campaign) show(campaign, state);
    } catch { /* L'app continua sense promocions si no hi ha connexió o dades vàlides. */ }
    finally { busy = false; }
  }
  function externalEntry() {
    const nav = performance.getEntriesByType?.('navigation')?.[0];
    if (nav && nav.type !== 'navigate') return false;
    if (!document.referrer) return true;
    try { const ref = new URL(document.referrer); return !(ref.origin === base.origin && ref.pathname.startsWith(base.pathname)); }
    catch { return true; }
  }
  function initial() {
    if (!initialPending || document.visibilityState !== 'visible') return;
    initialPending = false;
    if (previewOpening !== null || externalEntry()) void opening();
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') { hiddenAt = Date.now(); return; }
    if (document.visibilityState !== 'visible') return;
    const elapsed = hiddenAt === null ? 0 : Date.now() - hiddenAt;
    hiddenAt = null;
    if (initialPending) { initial(); return; }
    if (previewOpening === null && elapsed >= returnAfter) void opening();
  });
  window.addEventListener('pagehide', () => { hiddenAt = null; });
  window.addEventListener('pageshow', event => { if (event.persisted) hiddenAt = null; });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initial, {once:true});
  else initial();
})();
