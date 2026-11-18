/* ZonaOK · Retocs visuals 2026-11-18
   Carregar DESPRES d'app.js. No modifica les dades ni la importacio FECAPA.
*/
(() => {
  'use strict';
  const STYLE_ID = 'zonaok-retocs-20261118';
  const css = `
/* Colors per categoria tant a Inici com als llistats */
.match.zok-alevi { --accent: #8d2446; --tint: #eed0da; }
.match.zok-infantil { --accent: #245bb0; --tint: #d9e8ff; }
.match.zok-juvenil { --accent: #bc9214; --tint: #fff0b4; }
.match.zok-juvenil .pill { color: #172b3d; }

/* Targetes dels llistats: nomes data, hora, clubs i marcador. */
#results-list .match.zok-compact {
  border-radius: 13px;
  padding: 10px 12px;
  box-shadow: 0 5px 14px #0003;
}
#results-list .match.zok-compact:before { display: none; }
#results-list .match.zok-compact .match-top,
#results-list .match.zok-compact .venue,
#results-list .match.zok-compact .match-actions,
#results-list .match.zok-compact > .helper { display: none !important; }
#results-list .match.zok-compact .match-date {
  margin: 0 0 7px;
  gap: 8px;
  flex-direction: row-reverse;
  justify-content: flex-end;
  align-items: baseline;
}
#results-list .match.zok-compact .match-date strong { font-size: 14px; letter-spacing: 0; }
#results-list .match.zok-compact .match-date small { font-size: 12px; color: #314b63; }
#results-list .match.zok-compact .teams {
  display: grid;
  grid-template-columns: minmax(0,1fr) 62px minmax(0,1fr);
  align-items: center;
  gap: 5px;
}
#results-list .match.zok-compact .side {
  width: auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: row;
  gap: 6px;
  text-align: left;
}
#results-list .match.zok-compact .side:last-child { flex-direction: row-reverse; text-align: right; }
#results-list .match.zok-compact .side strong {
  font-size: 11px;
  line-height: 1.2;
  overflow-wrap: anywhere;
}
#results-list .match.zok-compact .crest {
  flex: 0 0 29px;
  width: 29px;
  height: 29px;
  border-radius: 8px;
  box-shadow: none;
}
#results-list .match.zok-compact .crest img { width: 26px; height: 26px; }
#results-list .match.zok-compact .crest-fallback { font-size: 11px; }
#results-list .match.zok-compact .middle { min-width: 0; gap: 0; }
#results-list .match.zok-compact .score { font-size: 16px; }
#results-list .match.zok-compact .score-note { display: none; }
#results-list.cards { gap: 7px; }
@media(max-width:360px) {
  #results-list .match.zok-compact { padding: 9px 8px; }
  #results-list .match.zok-compact .teams { grid-template-columns: minmax(0,1fr) 50px minmax(0,1fr); gap: 3px; }
  #results-list .match.zok-compact .side { gap: 4px; }
  #results-list .match.zok-compact .side strong { font-size: 10px; }
  #results-list .match.zok-compact .score { font-size: 14px; }
}
`;
  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = css;
    document.head.appendChild(style);
  }

  function category(card) {
    const title = (card.querySelector('.pill')?.textContent || '').normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '').toUpperCase();
    if (/ALEVI/.test(title)) return 'zok-alevi';
    if (/INFANTIL/.test(title)) return 'zok-infantil';
    if (/JUVENIL/.test(title)) return 'zok-juvenil';
    return '';
  }
  const classes = ['zok-alevi', 'zok-infantil', 'zok-juvenil'];
  function decorate() {
    for (const card of document.querySelectorAll('#home-cards .match, #results-list .match')) {
      const expected = category(card);
      for (const cls of classes) {
        if (cls !== expected && card.classList.contains(cls)) card.classList.remove(cls);
      }
      if (expected && !card.classList.contains(expected)) card.classList.add(expected);
      const compact = !!card.closest('#results-list');
      if (card.classList.contains('zok-compact') !== compact) card.classList.toggle('zok-compact', compact);
    }
  }
  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; decorate(); });
  };
  // Vigilem nomes canvis en els contenidors, no els canvis de classe que fem nosaltres.
  function observe(id) {
    const root = document.getElementById(id);
    if (root) new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { observe('home-cards'); observe('results-list'); schedule(); }, { once: true });
  } else { observe('home-cards'); observe('results-list'); schedule(); }
})();
