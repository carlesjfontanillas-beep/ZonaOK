/* ZonaOK · Campanyes emergents, independents de les notificacions push. */
(() => {
  'use strict';
  if (window.ZonaOKPromocions) return;
  window.ZonaOKPromocions = true;
  const KEY = 'ZONAOK_PROMOCIONS_V1';
  const base = new URL('./', document.currentScript.src);
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
  function show(c, state) {
    if (document.visibilityState !== 'visible' || document.querySelector('#zok-promo-dialog')) return false;
    const dialog = element('dialog');
    if (typeof dialog.showModal !== 'function') return false;
    dialog.id = 'zok-promo-dialog';
    dialog.setAttribute('aria-labelledby', 'zok-promo-title');
    dialog.setAttribute('aria-describedby', 'zok-promo-message');
    dialog.style.cssText = 'box-sizing:border-box;width:min(92vw,400px);max-height:85vh;max-height:85dvh;overflow:auto;overscroll-behavior:contain;border:1px solid #33536c;border-radius:20px;padding:20px;background:#0c263e;color:#f2f7fb;text-align:center;box-shadow:0 12px 50px #0008;font:inherit;margin:auto;';
    const style = element('style', '#zok-promo-dialog::backdrop{background:rgba(0,12,25,.75)} #zok-promo-dialog button:focus-visible,#zok-promo-dialog a:focus-visible{outline:2px solid #fff;outline-offset:3px}');
    const close = element('button', '×');
    close.type = 'button'; close.setAttribute('aria-label', 'Tanca el missatge');
    close.style.cssText = 'display:block;margin:0 0 0 auto;min-width:44px;min-height:44px;background:transparent;border:0;color:#e3edf6;font-size:30px;line-height:1;cursor:pointer;';
    close.addEventListener('click', () => dialog.close());
    const brand = element('div', 'ZONAOK · El teu hoquei');
    brand.style.cssText = 'font-weight:800;font-size:13px;color:#ffd54a;letter-spacing:.03em;margin:4px 0 16px;';
    const title = element('h2', text(c.title)); title.id = 'zok-promo-title';
    title.style.cssText = 'font-size:23px;line-height:1.2;margin:14px 0 10px;color:inherit;overflow-wrap:anywhere;';
    const message = element('p', text(c.message)); message.id = 'zok-promo-message';
    message.style.cssText = 'font-size:15px;line-height:1.5;margin:0 0 20px;white-space:pre-wrap;overflow-wrap:anywhere;color:inherit;';
    dialog.append(close, brand);
    const imgUrl = safeUrl(c.image, true);
    if (imgUrl) {
      const img = element('img'); img.src = imgUrl; img.alt = text(c.imageAlt);
      img.style.cssText = 'display:block;max-width:100%;max-height:220px;object-fit:contain;margin:0 auto 12px;border-radius:10px;';
      img.addEventListener('error', () => img.remove(), {once:true}); dialog.append(img);
    }
    dialog.append(title, message);
    const url = safeUrl(c.buttonUrl);
    if (url && text(c.buttonText)) {
      const link = element('a', text(c.buttonText)); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.style.cssText = 'display:block;background:#ffd54a;color:#061d33;border-radius:12px;padding:13px;text-decoration:none;font-weight:800;margin-bottom:12px;overflow-wrap:anywhere;';
      link.addEventListener('click', () => dialog.close()); dialog.append(link);
    }
    const dismiss = element('button', 'Tancar');
    dismiss.type = 'button'; dismiss.style.cssText = 'min-height:44px;padding:8px 18px;background:transparent;border:0;color:#dce7f0;cursor:pointer;font:inherit;';
    dismiss.addEventListener('click', () => dialog.close()); dialog.append(dismiss);
    const previous = document.activeElement;
    dialog.addEventListener('close', () => { dialog.remove(); style.remove(); if (previous && previous.isConnected) previous.focus({preventScroll:true}); }, {once:true});
    document.head.append(style); document.body.append(dialog);
    try { dialog.showModal(); } catch { dialog.remove(); style.remove(); return false; }
    const updated = {...state, shown: [...state.shown, c.id]};
    if (!save(updated)) { dialog.close(); return false; }
    close.focus({preventScroll:true});
    return true;
  }
  async function opening() {
    if (busy || document.visibilityState !== 'visible') return;
    busy = true;
    try {
      const response = await fetch(new URL('promocions.json', base), {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return;
      const cfg = await response.json();
      if (cfg?.schema !== 1 || !Array.isArray(cfg.campaigns)) return;
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
    if (externalEntry()) void opening();
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') { hiddenAt = Date.now(); return; }
    if (document.visibilityState !== 'visible') return;
    const elapsed = hiddenAt === null ? 0 : Date.now() - hiddenAt;
    hiddenAt = null;
    if (initialPending) { initial(); return; }
    if (elapsed >= returnAfter) void opening();
  });
  window.addEventListener('pagehide', () => { hiddenAt = null; });
  window.addEventListener('pageshow', event => { if (event.persisted) hiddenAt = null; });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initial, {once:true});
  else initial();
})();
