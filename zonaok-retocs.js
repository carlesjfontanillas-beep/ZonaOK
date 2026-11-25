/* ZonaOK · Retocs visuals 2026-11-18 (V6: colors, categoria i interfície compacta)
   Carregar DESPRES d'app.js. No modifica les dades ni la importacio FECAPA.
*/
(() => {
  'use strict';
  const STYLE_ID = 'zonaok-retocs-20261118';
  const css = `
/* Els colors de les targetes es resolen a Favorits. */

/* Targetes dels llistats: data, hora, categoria, clubs i marcador. */
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
  flex-direction: row;
  flex-wrap: wrap;
  row-gap: 3px;
  justify-content: flex-start;
  align-items: center;
}
#results-list .match.zok-compact .match-date strong { order: 1; font-size: 14px; letter-spacing: 0; }
#results-list .match.zok-compact .match-date small { order: 0; font-size: 12px; color: #314b63; }
/* La categoria s'extreu de la pill original i es posa a la mateixa linia. */
#results-list .match.zok-compact .match-date[data-zok-categoria]::after {
  content: attr(data-zok-categoria);
  order: 2;
  margin-left: auto;
  max-width: 48%;
  padding: 3px 7px;
  border-radius: 999px;
  background: var(--accent, #355b79);
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
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
/* Les actes són una acció pròpia, no formen part de .match-actions, que s'amaga. */
.match .zok-acta-chip{display:inline-flex!important;align-items:center;justify-content:center;align-self:center;white-space:nowrap;margin:3px auto 0!important;padding:3px 6px!important;border:0!important;border-radius:6px!important;background:var(--accent,#647b92)!important;color:#fff!important;font-size:10px!important;font-weight:800!important;line-height:1.2!important;min-height:20px!important;cursor:pointer!important}
#results-list .match.zok-compact.zok-acta-available{cursor:pointer;}
#results-list .match.zok-compact .zok-acta-chip{display:inline-flex!important;position:static!important;opacity:1!important;visibility:visible!important}
#results-list.cards { gap: 7px; }

/* CLASSIFICACIONS: mateix codi de colors que els tres equips. */
#results-list h3.zok-taula-titol {
  margin: 17px 0 4px;
  padding: 10px 12px;
  border-radius: 10px;
  border-left: 5px solid var(--zok-color);
  background: var(--zok-fons-titol);
  color: var(--zok-text-titol);
  font-size: 16px;
  line-height: 1.25;
}
#results-list .standings.zok-taula th {
  background: var(--zok-color);
  color: var(--zok-text-cap);
}
#results-list .standings.zok-taula tr:not(:first-child):not(.highlight) {
  background: var(--zok-fons-fila, #e7edf8);
}
#results-list .standings.zok-taula tr.highlight {
  background: var(--zok-fons-destacat);
  color: #112b42;
  font-weight: 850;
}
#results-list .standings.zok-taula tr.highlight td:first-child {
  box-shadow: inset 4px 0 var(--zok-color);
}
#results-list .zok-standings-alevi {
  --zok-color: #8d2446;
  --zok-text-cap: #fff;
  --zok-fons-fila: #f4eaf0;
  --zok-fons-destacat: #edc4d2;
  --zok-fons-titol: #512039;
  --zok-text-titol: #ffdee9;
}
#results-list .zok-standings-infantil {
  --zok-color: #245bb0;
  --zok-text-cap: #fff;
  --zok-fons-fila: #e7efff;
  --zok-fons-destacat: #bfd7ff;
  --zok-fons-titol: #173b6b;
  --zok-text-titol: #d6e7ff;
}
#results-list .zok-standings-juvenil {
  --zok-color: #e9be35;
  --zok-text-cap: #13263a;
  --zok-fons-fila: #fff9e8;
  --zok-fons-destacat: #ffebad;
  --zok-fons-titol: #554317;
  --zok-text-titol: #fff0b1;
}

/* V6 - Eliminem el panell inicial gran i recuperem espai útil. */
.app{padding-top:calc(5px + env(safe-area-inset-top));padding-bottom:calc(70px + env(safe-area-inset-bottom))}
.mast{padding:2px 3px 5px;min-height:29px}
.mast .brand{font-size:21px;line-height:1.1}
.mast .strap,.mast .emblem{display:none}
.hero{display:flex;align-items:center;justify-content:space-between;gap:8px;
  padding:2px 2px 4px;margin:0;border:0;box-shadow:none;border-radius:0;background:transparent;overflow:visible}
.hero::before,.hero .rink,.hero h1,.hero .overline{display:none!important}
.hero .week{margin:0;line-height:1.25;font-size:11px;color:#ffce99;font-weight:750;flex:1;min-width:0}
.hero-actions{display:flex;align-items:center;gap:5px;flex:0 0 auto;margin:0}
.hero-actions button{flex:0 0 auto;min-width:35px;width:35px;height:34px;min-height:34px;padding:2px;border-radius:10px;font-size:0;line-height:1}
#refresh-home::after{content:'↻';font-size:21px}
#ask-home::after{content:'?';font-size:18px}
.keyline{margin:6px 2px 8px;font-size:10px;flex-wrap:wrap}
.section{margin-top:13px}
.section-head{margin-bottom:9px}
.section-head h2{font-size:18px}
/* Barra d'accés ràpid: sis icones en UNA fila, sense peu ni títol. */
.bottom{padding:5px 6px calc(5px + env(safe-area-inset-bottom));box-shadow:0 -6px 20px #00101fa6}
.bottom-title,.navbtn strong,.navbtn small{display:none!important}
.navgrid{grid-template-columns:repeat(6,minmax(0,1fr));gap:5px}
.navbtn{min-width:0;min-height:43px;height:43px;border-radius:11px;padding:3px 0;gap:0}
.navbtn span{font-size:23px;line-height:1}
.navbtn.active{background:#305a77;border-color:#ffbc78}
/* Botons secundaris llegibles a l'iPhone sense línies exagerades. */
.import-card .context-actions{display:flex;flex-wrap:wrap;gap:7px;margin:9px 0}
.import-card .context-actions>*{display:flex;align-items:center;justify-content:center;text-align:center;
  flex:1 1 calc(50% - 5px);min-width:0;min-height:38px;padding:7px 5px;font-size:11px;
  line-height:1.18;overflow-wrap:anywhere;text-decoration:none}
#results-section .context-actions>*{font-size:11px;padding:9px 6px}
/* La pista literal només apareix a Inici; el llistat es manté compacte. */
#home-cards .match.zok-v5 .venue{margin-top:10px;padding-top:8px}
#home-cards .match.zok-v5 .venue strong{font-size:11px}

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

  // Es mira el club dins la targeta, no nomes la categoria de competicio.
  // Un partit del Barca es SEMPRE granat, encara que sigui juvenil.
  function normalitzar(text) {
    return String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim();
  }
  function colorEquip(card) {
    const equips = normalitzar(Array.from(card.querySelectorAll('.teams .side strong'))
      .map(el => el.textContent).join(' | '));
    const categoria = normalitzar(card.querySelector('.pill')?.textContent);

    // Coincidencia d'equip: Barca, FC Barcelona o FCB.
    if (/\bBARCA\b|\bBARCELONA\b|\bFCB\b|\bFCBETRANS\b|\bFCBETERANS\b/.test(equips)) return 'zok-barca';

    // Sant Celoni nomes en les dues categories favorites. La lliga pot venir
    // com a INFANTIL OR 10 / JUVENIL OR 6 i el nom pot ometre la lletra B.
    const esCeloni = /SANT\s*CELONI|\bCPSC\b|\bCP\s*SC\b/.test(equips);
    if (esCeloni) {
      if (/\bINFANTIL\b/.test(categoria) &&
          (/\bINFANTIL\b.*\bOR\s*10\b/.test(categoria) ||
           /\bSANT\s*CELONI\s+B\b/.test(equips) || /\bCPSC\s+B\b/.test(equips))) return 'zok-infantil';
      if (/\bJUVENIL\b/.test(categoria) &&
          (/\bJUVENIL\b.*\bOR\s*6\b/.test(categoria) ||
           /\bSANT\s*CELONI\s+B\b/.test(equips) || /\bCPSC\s+B\b/.test(equips))) return 'zok-juvenil';
    }
    return ''; // Altres equips/casos ambigus mantenen el color neutre.
  }
  const classes = ['zok-barca', 'zok-infantil', 'zok-juvenil', 'zok-alevi'];
  function decorate() {
    for (const card of document.querySelectorAll('#home-cards .match, #results-list .match')) {
      for (const cls of classes) if (card.classList.contains(cls)) card.classList.remove(cls);
      const compact = !!card.closest('#results-list');
      if (card.classList.contains('zok-compact') !== compact) card.classList.toggle('zok-compact', compact);

      // Recuperem la categoria real de la targeta original, que el mode
      // compacte amaga amb .match-top. Mai no l'inferim del club.
      const date = card.querySelector('.match-date');
      if (date && compact) {
        const categoria = (card.querySelector('.pill')?.textContent || '').trim();
        if (categoria) date.dataset.zokCategoria = categoria;
        else date.removeAttribute('data-zok-categoria');
      } else if (date) {
        date.removeAttribute('data-zok-categoria');
      }
    }
  }
  // Les taules de classificacio es generen amb un h3 i una taula .standings.
  // Identifiquem cada taula pel titol anterior, sense dependre de la seva posicio.
  const standingsClasses = ['zok-standings-alevi', 'zok-standings-infantil', 'zok-standings-juvenil'];
  function categoryFromTitle(text) {
    const t = String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
    if (/ALEVI/.test(t)) return 'zok-standings-alevi';
    if (/INFANTIL/.test(t)) return 'zok-standings-infantil';
    if (/JUVENIL/.test(t)) return 'zok-standings-juvenil';
    return '';
  }
  function decorateStandings() {
    const root = document.getElementById('results-list');
    if (!root) return;
    let current = '';
    for (const el of root.children) {
      if (el.matches('h3')) {
        current = categoryFromTitle(el.textContent);
        el.classList.remove('zok-taula-titol', ...standingsClasses);
        if (current) el.classList.add('zok-taula-titol', current);
      } else if (el.matches('table.standings')) {
        el.classList.remove('zok-taula', ...standingsClasses);
        if (current) el.classList.add('zok-taula', current);
      }
    }
  }
  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; decorate(); decorateStandings(); });
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
