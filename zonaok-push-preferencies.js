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
    let count = 0;
    for (const [group,title] of groups) {
      const values = Array.isArray(fav[group]) ? [...new Set(fav[group].filter(v => typeof v === 'string' && v))] : [];
      if (!values.length) continue;
      const heading = document.createElement('h3'); heading.textContent = title; host.append(heading);
      for (const id of values) {
        count++;
        const target = JSON.stringify([group,id]);
        const label = document.createElement('label'); label.className = 'zok-push-choice';
        const input = document.createElement('input'); input.type = 'checkbox'; input.checked = prefs.targets.includes(target);
        const name = group === 'teams' ? (fav.teamNames?.[id] || id.split('|').slice(1).join(' · ')) : id;
        const span = document.createElement('span'); span.textContent = name;
        input.addEventListener('change', () => {
          prefs.targets = prefs.targets.filter(v => v !== target);
          if (input.checked) prefs.targets.push(target);
          save();
        });
        label.append(input,span); host.append(label);
      }
    }
    if (!count) {
      const p = document.createElement('p'); p.textContent = 'Marca favorits per poder configurar els seus avisos aquí.'; host.append(p);
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
