/* ZonaOK · Preferències push (fase 1, sense connexió ni enviaments). */
(() => {
  'use strict';
  const root = document.getElementById('zok-push-settings');
  if (!root) return;
  const key = 'ZONAOK_PUSH_PREFS_V1';
  const groups = [['clubs','Clubs'],['teams','Equips'],['categories','Categories'],['competitions','Competicions']];
  const events = ['start','goal','card','finish'];
  const status = root.querySelector('[data-push-status]');
  const host = root.querySelector('[data-push-targets]');
  function read(key) { try { return JSON.parse(localStorage.getItem(key) || '{}') || {}; } catch (_) { return {}; } }
  function defaults() {
    const p = read(key);
    return {events: Array.isArray(p.events) ? p.events.filter(v => events.includes(v)) : ['start','finish'],
      targets: Array.isArray(p.targets) ? p.targets.filter(v => typeof v === 'string') : []};
  }
  let prefs = defaults();
  function save() {
    try { localStorage.setItem(key, JSON.stringify(prefs)); status.textContent = 'Preferències desades en aquest dispositiu. Enviaments encara desactivats.'; }
    catch (_) { status.textContent = 'No s’han pogut desar les preferències.'; }
  }
  function renderTargets() {
    const fav = read('ZONAOK_FAVORITS_V1');
    host.replaceChildren();
    const catalog = window.ZonaOKPushFavoriteCatalog?.() || {};
    const teamLabels = new Map((catalog.teams || []).map(option => [option.id, option.label]));
    for (const [group,title] of groups) {
      const saved = Array.isArray(fav[group]) ? fav[group] : [];
      const available = group === 'categories' || group === 'competitions' ? (catalog[group] || []) : [];
      const previous = prefs.targets.flatMap(value => { try { const [kind,id] = JSON.parse(value); return kind === group && typeof id === 'string' ? [id] : []; } catch (_) { return []; } });
      const values = [...new Set([...saved, ...available, ...((group === 'categories' || group === 'competitions') ? previous : [])].filter(v => typeof v === 'string' && v))];
      const card = document.createElement('section'); card.className = 'zok-favorite-group zok-push-card';
      const heading = document.createElement('h2'); heading.textContent = title; card.append(heading);
      const list = document.createElement('div'); list.className = 'zok-favorite-list zok-push-list';
      card.append(list); host.append(card);
      if (!values.length) {
        const empty = document.createElement('p'); empty.className = 'zok-favorite-empty';
        empty.textContent = group === 'clubs' || group === 'teams' ? 'Marca favorits per configurar els seus avisos.' : 'No hi ha opcions disponibles amb els filtres actuals.';
        list.append(empty);
      }
      for (const id of values) {
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
        });
        label.append(input,span); list.append(label);
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
    });
  });
  function refresh() { renderTargets(); }
  root.querySelector('details').addEventListener('toggle', refresh);
  root.querySelector('[data-push-refresh]').addEventListener('click', refresh);
  window.addEventListener('zonaok:favorites-updated', refresh);
  window.addEventListener('zonaok:team-pickers-rendered', refresh);
  window.addEventListener('pageshow', refresh);
  window.addEventListener('storage', event => {
    if (event.key === 'ZONAOK_FAVORITS_V1') refresh();
  });
  renderTargets();
})();
