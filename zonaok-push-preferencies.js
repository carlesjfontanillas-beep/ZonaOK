/* ZonaOK · Preferències push (fase 1, sense connexió ni enviaments). */
(() => {
  'use strict';
  const root = document.getElementById('zok-push-settings');
  if (!root) return;
  const key = 'ZONAOK_PUSH_PREFS_V1';
  const groups = [['clubs','Clubs'],['teams','Equips'],['categories','Categories'],['competitions','Competicions']];
  const events = ['start','goal','card','directFoul','finish','scheduleChange'];
  const status = root.querySelector('[data-push-status]');
  const host = root.querySelector('[data-push-targets]');
  function read(key) { try { return JSON.parse(localStorage.getItem(key) || '{}') || {}; } catch (_) { return {}; } }
  function defaults() {
    const p = read(key);
    return {events: Array.isArray(p.events) ? p.events.filter(v => events.includes(v)) : ['start','finish'],
      targets: Array.isArray(p.targets) ? p.targets.filter(v => typeof v === 'string') : []};
  }
  let prefs = defaults();
  // Seleccionats primer; dins de cada grup es conserva l'ordre habitual.
  const selectedFirst = (a,b) => Number(b.input.checked) - Number(a.input.checked) || a.rank - b.rank;
  function reorderRows(list, rows, end = null) {
    const ordered = [...rows].sort(selectedFirst);
    let next = end;
    for (let i = ordered.length - 1; i >= 0; i--) {
      const node = ordered[i].label;
      if (node.nextSibling !== next) list.insertBefore(node,next);
      next = node;
    }
  }
  function reorderEvents() {
    const rows = [...root.querySelectorAll('[data-push-event]')].map(input => ({
      input,label:input.closest('label'),rank:events.indexOf(input.dataset.pushEvent)
    })).filter(row=>row.label);
    if (rows.length) reorderRows(rows[0].label.parentElement,rows);
  }
  // Les preferències del servidor prevalen en aquest dispositiu quan la Push subscription es recupera.
  window.addEventListener('zonaok:push-preferences-restored', event => {
    const saved = event.detail && typeof event.detail === 'object' ? event.detail : {};
    prefs = {
      events: Array.isArray(saved.events) ? saved.events.filter(v => events.includes(v)) : prefs.events,
      targets: Array.isArray(saved.targets) ? saved.targets.filter(v => typeof v === 'string') : prefs.targets
    };
    root.querySelectorAll('[data-push-event]').forEach(input => { input.checked = prefs.events.includes(input.dataset.pushEvent); });
    reorderEvents();
    try { localStorage.setItem(key, JSON.stringify(prefs)); } catch (_) {}
    renderTargets();
  });
  const queries = Object.create(null);
  const normalizeSearch = value => String(value ?? '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('ca')
    .replace(/[^\p{L}\p{N}]+/gu,' ').trim();
  const placeholders = {clubs:'Cerca un club…',teams:'Cerca un equip o categoria…',categories:'Cerca una categoria…',competitions:'Cerca una competició…'};
  function save() {
    try { localStorage.setItem(key, JSON.stringify(prefs)); status.textContent = 'Preferències desades en aquest dispositiu. Enviaments encara desactivats.'; }
    catch (_) { status.textContent = 'No s’han pogut desar les preferències.'; }
  }
  function renderTargets() {
    const fav = read('ZONAOK_FAVORITS_V1');
    const focusedGroup = document.activeElement?.dataset?.pushSearch;
    const cursor = focusedGroup ? document.activeElement.value.length : null;
    const previousCards = new Map([...host.querySelectorAll('details[data-push-group]')].map(card => [card.dataset.pushGroup,{open:card.open,scrollTop:card.scrollTop}]));
    host.replaceChildren();
    const catalog = window.ZonaOKPushFavoriteCatalog?.() || {};
    const teamLabels = new Map((catalog.teams || []).map(option => [option.id, option.label]));
    for (const [group,title] of groups) {
      const saved = Array.isArray(fav[group]) ? fav[group] : [];
      const available = (catalog[group] || []).map(option => typeof option === 'string' ? option : option?.id);
      const previous = prefs.targets.flatMap(value => { try { const [kind,id] = JSON.parse(value); return kind === group && typeof id === 'string' ? [id] : []; } catch (_) { return []; } });
      const favoriteIds = new Set(saved);
      const displayName = id => group === 'teams' ? (teamLabels.get(id) || id.split('|').slice(1).reverse().join(' · ')) : id;
      const values = [...new Set([...saved, ...available, ...previous].filter(v => typeof v === 'string' && v))].sort((a,b) =>
        Number(favoriteIds.has(b)) - Number(favoriteIds.has(a)) ||
        displayName(a).localeCompare(displayName(b),'ca',{sensitivity:'base',numeric:true}));
      const card = document.createElement('details'); card.className = 'zok-favorite-group zok-push-card zok-push-foldable';
      card.dataset.pushGroup = group; card.open = previousCards.get(group)?.open || false;
      const heading = document.createElement('summary'); heading.className = 'zok-push-fold-summary'; heading.textContent = title;
      const arrow = document.createElement('span'); arrow.className = 'zok-push-fold-arrow'; arrow.setAttribute('aria-hidden','true'); heading.append(arrow); card.append(heading);
      const searchWrap = document.createElement('div'); searchWrap.className = 'zok-push-search-wrap';
      const search = document.createElement('input');
      search.type = 'search'; search.className = 'zok-push-search'; search.placeholder = placeholders[group];
      search.setAttribute('aria-label', placeholders[group].replace('…','')); search.autocomplete = 'off';
      search.dataset.pushSearch = group; search.value = queries[group] || '';
      const counter = document.createElement('small'); counter.className = 'zok-push-search-count';
      counter.setAttribute('aria-live','polite');
      searchWrap.append(search,counter); card.append(searchWrap);
      const list = document.createElement('div'); list.className = 'zok-favorite-list zok-push-list';
      const rows = [];
      card.append(list); host.append(card);
      if (!values.length) {
        const empty = document.createElement('p'); empty.className = 'zok-favorite-empty';
        empty.textContent = 'Encara no hi ha dades del catàleg disponibles.';
        list.append(empty);
      }
      for (const [rank,id] of values.entries()) {
        const target = JSON.stringify([group,id]);
        const label = document.createElement('label'); label.className = 'zok-favorite-option zok-push-choice';
        const input = document.createElement('input'); input.type = 'checkbox'; input.checked = prefs.targets.includes(target);
        const parts = id.split('|');
        const name = group === 'teams' ? (teamLabels.get(id) || (parts.length >= 3 ? parts.slice(2).join(' · ') + ' · ' + parts[1] : id)) : id;
        const span = document.createElement('span'); span.className = 'zok-favorite-option-label'; span.textContent = name;
        input.addEventListener('change', () => {
          prefs.targets = prefs.targets.filter(v => v !== target);
          if (input.checked) prefs.targets.push(target);
          save();
          reorderRows(list,rows,noMatches);
        });
        label.append(input,span); list.append(label);
        rows.push({label,input,rank,text: normalizeSearch(name + ' ' + id)});
      }
      const noMatches = document.createElement('p'); noMatches.className = 'zok-favorite-empty';
      noMatches.textContent = 'No s’ha trobat cap coincidència.'; noMatches.hidden = true; list.append(noMatches);
      function applyFilter() {
        const tokens = normalizeSearch(search.value).split(' ').filter(Boolean);
        let visible = 0;
        for (const row of rows) {
          const match = tokens.every(token => row.text.includes(token));
          row.label.hidden = !match;
          if (match) visible++;
        }
        counter.textContent = visible + ' / ' + rows.length;
        noMatches.hidden = !rows.length || visible > 0;
      }
      search.addEventListener('input', () => {
        queries[group] = search.value; applyFilter(); card.scrollTop = 0;
      });
      reorderRows(list,rows,noMatches);
      applyFilter();
      if (card.open) card.scrollTop = previousCards.get(group)?.scrollTop || 0;
      if (focusedGroup === group && card.open) {
        search.focus({preventScroll:true});
        try { search.setSelectionRange(cursor,cursor); } catch (_) {}
      }
    }
  }
  const capability = root.querySelector('[data-push-capability]');
  const supported = window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  capability.textContent = supported ? 'Aquest navegador declara compatibilitat amb Web Push. Encara no s’ha provat el lliurament.' : 'Web Push no està disponible en aquesta vista. A l’iPhone, obre ZonaOK des de la pantalla d’inici (iOS 16.4 o posterior).';
  root.querySelectorAll('[data-push-event]').forEach(input => {
    const event = input.dataset.pushEvent;
    input.checked = prefs.events.includes(event);
    input.addEventListener('change', () => {
      prefs.events = prefs.events.filter(v => v !== event);
      if (input.checked) prefs.events.push(event);
      save();
      reorderEvents();
    });
  });
  reorderEvents();
  // Només en obrir manualment un bloc: mostrar la capçalera sota la barra fixa.
  root.addEventListener('click', event => {
    const heading = event.target.closest('.zok-push-fold-summary');
    if (!heading) return;
    const card = heading.parentElement;
    requestAnimationFrame(() => {
      if (card.open) card.scrollIntoView({block:'start',behavior:'auto'});
      else card.scrollTop = 0;
    });
  });
  function refresh() { renderTargets(); }
  const catalogStatus = root.querySelector('[data-push-catalog-status]');
  const refreshButton = root.querySelector('[data-push-refresh]');
  window.addEventListener('zonaok:push-catalog-ready', () => {
    if (catalogStatus) catalogStatus.textContent = 'Catàleg complet carregat.';
    refreshButton.disabled = false;
    refresh();
  });
  window.addEventListener('zonaok:push-catalog-error', () => {
    if (catalogStatus) catalogStatus.textContent = 'No s’ha pogut carregar el catàleg. Torna-ho a provar.';
    refreshButton.disabled = false;
  });
  refreshButton.addEventListener('click', () => {
    if (typeof window.ZonaOKReloadPushCatalog !== 'function') return refresh();
    if (catalogStatus) catalogStatus.textContent = 'Carregant el catàleg…';
    refreshButton.disabled = true;
    window.ZonaOKReloadPushCatalog();
  });
  window.addEventListener('zonaok:favorites-updated', refresh);
  window.addEventListener('zonaok:team-pickers-rendered', refresh);
  window.addEventListener('pageshow', refresh);
  window.addEventListener('storage', event => {
    if (event.key === 'ZONAOK_FAVORITS_V1') refresh();
  });
  renderTargets();
})();
