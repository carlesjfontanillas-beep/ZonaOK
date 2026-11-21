/*
 * ZonaOK — Resultats dels darrers 7 dies · V5 · TOTS ELS CLUBS + TARGETES COMPACTES (21/11/2026)
 * Instal·lació: <script defer src="zonaok-resultats-7dies.js?v=20261121-tots-r5"></script>
 * al final de <body> d'index.html, després dels scripts existents.
 *
 * Font principal: zonaok-data.json / data.agenda.rows. Els scoreUpdates i live
 * només complementen marcadors d'un partit d'Agenda inequívocament relacionat.
 * No modifica les dreceres, les dades importades, ni el render de les altres pestanyes.
 */
(() => {
  'use strict';
  const ID = 'zok-resultats-7dies';
  const NAV_ID = 'zok-nav-resultats-7dies';
  const CLUBS = [
    ['barca', 'Barça'],
    ['celoni', 'CP Sant Celoni']
  ];
  const norm = s => String(s ?? '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, ' ')
    .trim().toUpperCase();
  const make = (tag, className, value) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (value !== undefined) el.textContent = value;
    return el;
  };
  const hasScore = s => s !== '' && s !== null && s !== undefined &&
    Number.isInteger(Number(s)) && Number(s) >= 0 && Number(s) < 200;
  const validResult = r => hasScore(r.homeScore) && hasScore(r.awayScore);
  const clubOf = name => {
    const s = norm(name);
    if (/^(?:BAR|BARCA|FC BARCELONA|F C BARCELONA|FCBETERANS|FCBETRANS)(?: [A-Z0-9]+)?$/.test(s)) return 'barca';
    if (/^CPSC(?:[AB]| [AB])?$/.test(s) || /\bSANT CELONI\b/.test(s)) return 'celoni';
    return '';
  };
  const teamKey = (name, logo) => {
    const known = clubOf(name);
    if (known) return known;
    const match = String(logo || '').match(/^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/(\d+)\.png$/);
    return match ? 'logo:' + match[1] : 'team:' + norm(name);
  };
  const teamLabel = (name, key) => {
    if (key === 'barca') return 'Barça';
    if (key === 'celoni') return 'CP Sant Celoni';
    return String(name || '').trim();
  };
  const canonical = name => {
    const raw = norm(name);
    const club = clubOf(name);
    const suffix = raw.match(/(?:^| )([AB])$/)?.[1] || raw.match(/^CPSC([AB])$/)?.[1] || '';
    if (club === 'barca') return 'BARCA' + (suffix ? ' ' + suffix : '');
    if (club === 'celoni') return 'SANT CELONI' + (suffix ? ' ' + suffix : '');
    return raw;
  };
  const categoryCore = text => norm(text).replace(/\s+\d+$/, '').replace(/\s+(?:GRUP|GRUPO)\s+[A-Z0-9]+$/, '');
  const key = r => [r.iso, r.time, norm(r.competition), norm(r.home), norm(r.away)].join('|');
  const pairsMatch = (agenda, score) => {
    if (agenda.iso !== score.iso || agenda.time !== score.time) return false;
    if (canonical(agenda.home) === canonical(score.home) &&
        canonical(agenda.away) === canonical(score.away)) return true;
    if (categoryCore(agenda.competition) && categoryCore(score.competition) &&
        categoryCore(agenda.competition) !== categoryCore(score.competition)) return false;
    // Les abreviatures només es relacionen si el club és al mateix costat.
    return Boolean((clubOf(agenda.home) && clubOf(agenda.home) === clubOf(score.home)) ||
      (clubOf(agenda.away) && clubOf(agenda.away) === clubOf(score.away)));
  };
  const madridTimeKey = instant => {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/Madrid', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(instant).filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  };
  const rowDateKey = r => `${r.iso}T${String(r.time || '').padStart(5, '0')}`;
  const prettyDate = iso => {
    try {
      return new Intl.DateTimeFormat('ca-ES', {
        weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC'
      }).format(new Date(`${iso}T12:00:00Z`));
    } catch (_) { return iso; }
  };
  const sameCategory = (a, b) => norm(a) === norm(b);
  const newest = (a, b) => String(b.capturedAt || b.scoreCapturedAt || '').localeCompare(String(a.capturedAt || a.scoreCapturedAt || ''));

  let matches = [];
  let publishedAt = '';
  let panel, navButton, clubFilter, categoryFilter, content, counter, status;

  function combinedAgenda(data) {
    const source = Array.isArray(data?.agenda?.rows) ? data.agenda.rows : [];
    // L'Agenda defineix els partits; ni En directe ni SCORE creen partits nous.
    const byKey = new Map();
    for (const r of source) {
      if (!r || !/^20\d\d-\d\d-\d\d$/.test(String(r.iso)) ||
          !/^\d{1,2}:\d\d$/.test(String(r.time)) || !r.home || !r.away) continue;
      const normalized = {...r, time: String(r.time).padStart(5, '0')};
      const k = key(normalized);
      if (!byKey.has(k) || newest(normalized, byKey.get(k)) < 0) byKey.set(k, normalized);
    }
    const agenda = [...byKey.values()];
    const scored = [...(Array.isArray(data?.scoreUpdates?.rows) ? data.scoreUpdates.rows : []),
      ...(Array.isArray(data?.live?.rows) ? data.live.rows : [])]
      .filter(s => s && validResult(s));
    const prepared = agenda.map(a => {
      const candidates = scored.filter(s => pairsMatch(a, {...s, time: String(s.time || '').padStart(5, '0')}))
        .filter(s => agenda.filter(other => pairsMatch(other, {...s, time: String(s.time || '').padStart(5, '0')})).length === 1)
        .sort(newest);
      if (!candidates.length) return a;
      const result = candidates[0];
      return {...a, homeScore: Number(result.homeScore), awayScore: Number(result.awayScore),
        scoreSource: 'En directe', scoreCapturedAt: result.capturedAt || ''};
    });
    const upper = madridTimeKey(new Date());
    const lower = madridTimeKey(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000));
    return prepared.filter(r => {
      const dt = rowDateKey(r);
      return dt >= lower && dt <= upper && validResult(r) &&
        !/EN JOC|EN DIRECTE|PLAYING|LIVE|IN PROGRESS/i.test(String(r.status || ''));
    }).sort((a, b) => rowDateKey(b).localeCompare(rowDateKey(a)) ||
      norm(a.competition).localeCompare(norm(b.competition), 'ca'));
  }

  function rowsInLastSevenDays(rows) {
    const upper = madridTimeKey(new Date());
    const lower = madridTimeKey(new Date(Date.now() - 7 * 86400000));
    return rows.filter(r => r && /^20\d\d-\d\d-\d\d$/.test(String(r.iso)) &&
      /^\d{2}:\d{2}$/.test(String(r.time)) && r.home && r.away && validResult(r) &&
      rowDateKey(r) >= lower && rowDateKey(r) <= upper &&
      !/EN JOC|EN DIRECTE|LIVE|IN PROGRESS|PLAYING|DESCANS|PRIMERA PART|SEGONA PART/i.test(String(r.status || '')))
      .sort((a,b) => rowDateKey(b).localeCompare(rowDateKey(a)) ||
        norm(a.competition).localeCompare(norm(b.competition),'ca'));
  }

  async function loadData() {
    // Nou sistema independent de 2 JSONs: agenda completa + resultats de 7 dies.
    // En directe MAI publica un catàleg de partits, només actualitza l’agenda.
    try {
      const res = await fetch(`zonaok-tots-resultats-7dies.json?t=${Date.now()}`, {cache:'no-store'});
      if (res.ok) {
        const pack = await res.json();
        if (pack?.schema === 'zonaok-all-v1' && pack?.kind === 'resultats-7dies' &&
            Array.isArray(pack.rows) && (pack.rows.length > 0 || pack.agendaCount > 0)) {
          publishedAt = pack.publishedAt || '';
          return {__all:true, rows:pack.rows};
        }
      }
    } catch (_) { /* encara no publicat; mantenim la V3 actual */ }
    let remote = null;
    try {
      const response = await fetch(`zonaok-data.json?t=${Date.now()}`, {cache:'no-store'});
      if (response.ok) {
        const packet = await response.json();
        if (packet?.version === 3 && Array.isArray(packet.data?.agenda?.rows)) {
          remote = packet.data;
          publishedAt = packet.publishedAt || packet.data.agenda?.capturedAt || '';
        }
      }
    } catch (_) { /* desconnectat */ }
    let memory = null;
    try { memory = window.ZonaOKSafeStorage?.read?.() || null; } catch (_) {}
    if (!remote && !Array.isArray(memory?.agenda?.rows)) throw new Error('No s’han pogut carregar els JSON publicats.');
    return remote || memory;
  }

  function buildTeam(name, importedLogo) {
    const team = make('div', 'side');
    const crest = make('div', 'crest');
    const club = clubOf(name);
    const logo = club === 'barca' ? '234' : club === 'celoni' ? '281' : '';
    const trusted = /^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/\d+\.png$/.test(String(importedLogo||'')) ? importedLogo : '';
    if (logo || trusted) {
      const image = make('img');
      image.src = trusted || `https://sidgad.cloud/fecapa/images/logos_clubes/${logo}.png`;
      image.alt = '';
      image.loading = 'lazy';
      image.onerror = () => crest.replaceChildren(make('span', 'crest-fallback', name.charAt(0)));
      crest.append(image);
    } else crest.append(make('span', 'crest-fallback', String(name).charAt(0).toUpperCase()));
    team.append(crest, make('strong', '', name));
    return team;
  }

  function buildCard(row) {
    const club = clubOf(row.home) || clubOf(row.away);
    const card = make('article', 'match ' + (club === 'barca' ? 'pink' : club === 'celoni' ? 'blue' : 'gray'));
    card.classList.add('zok-recent-card');

    // Disseny compacte de la versió facilitada: només dues línies per partit.
    // Capçalera: categoria, hora, data i Acta (sense pista ni «Marcador Agenda»).
    const top = make('div', 'match-top');
    const category = make('span', 'pill', row.competition || 'Categoria no informada');
    category.title = row.competition || 'Categoria no informada';
    const time = make('strong', 'zok-recent-time', row.time);
    const date = make('small', 'zok-recent-day', prettyDate(row.iso));
    const acta = make('button', 'zok-recent-acta', 'Acta');
    acta.type = 'button';
    acta.setAttribute('aria-label', 'Veure la fitxa i l’acta del partit');
    acta.onclick = () => {
      if (typeof window.ZonaOKActes?.open === 'function') {
        // Preservem els identificadors del nou JSON, necessaris per localitzar l'acta.
        window.ZonaOKActes.open({
          ...row,
          id: row.id || row.matchId || '',
          leagueId: row.leagueId || '',
          actaUrl: row.actaUrl || ''
        }, row.leagueId || 'live');
      } else alert('La funció d’actes de ZonaOK no està disponible en aquesta versió.');
    };
    top.append(category, time, date, acta);

    // Segona línia: escuts (inclosos els clubs nous), equips i marcador.
    const teams = make('div', 'teams');
    const center = make('div', 'middle');
    center.append(make('strong', 'score', `${Number(row.homeScore)} : ${Number(row.awayScore)}`));
    teams.append(buildTeam(row.home, row.homeLogo), center, buildTeam(row.away, row.awayLogo));
    card.append(top, teams);
    return card;
  }

  function updateClubOptions() {
    const chosen = clubFilter.value;
    const clubs = new Map();
    for (const r of matches) for (const [name, logo] of [[r.home,r.homeLogo],[r.away,r.awayLogo]]) {
      const k=teamKey(name,logo);
      if (!clubs.has(k)) clubs.set(k,teamLabel(name,k));
    }
    const options = [...clubs.entries()].sort((a,b)=>a[1].localeCompare(b[1],'ca',{sensitivity:'base'}));
    clubFilter.replaceChildren(new Option('Tots els clubs',''));
    for (const [key,label] of options) clubFilter.add(new Option(label,key));
    clubFilter.value = clubs.has(chosen) ? chosen : '';
  }

  function updateCategoryOptions() {
    const chosen = categoryFilter.value;
    const selectedClub = clubFilter.value;
    const categories = [...new Set(matches.filter(r => !selectedClub ||
      teamKey(r.home,r.homeLogo) === selectedClub || teamKey(r.away,r.awayLogo) === selectedClub)
      .map(r => String(r.competition || 'Categoria no informada')))]
      .sort((a, b) => a.localeCompare(b, 'ca', {sensitivity: 'base'}));
    categoryFilter.replaceChildren(new Option('Totes les categories', ''));
    for (const category of categories) categoryFilter.add(new Option(category, category));
    categoryFilter.value = categories.some(c => sameCategory(c, chosen)) ? chosen : '';
  }

  function renderCards() {
    const club = clubFilter.value, category = categoryFilter.value;
    const selected = matches.filter(r =>
      (!club || teamKey(r.home,r.homeLogo) === club || teamKey(r.away,r.awayLogo) === club) &&
      (!category || sameCategory(r.competition, category)));
    counter.textContent = `${selected.length} ${selected.length === 1 ? 'partit' : 'partits'}`;
    content.replaceChildren();
    if (!selected.length) {
      content.append(make('div', 'empty', matches.length ?
        'No hi ha resultats d’aquest club i categoria en els darrers 7 dies.' :
        'No hi ha partits amb marcadors importats en els darrers 7 dies. Això no confirma que no s’hagin disputat partits.'));
    } else for (const row of selected) content.append(buildCard(row));
    if (publishedAt) {
      try {
        const stamp = new Intl.DateTimeFormat('ca-ES', {
          timeZone: 'Europe/Madrid', dateStyle: 'short', timeStyle: 'short'
        }).format(new Date(publishedAt));
        status.textContent = `Font: FECAPA · JSON publicats · Actualització ${stamp}`;
      } catch (_) { status.textContent = 'Font: FECAPA · JSON publicats a GitHub'; }
    }
  }

  async function openResults() {
    document.body.classList.add('zok-recent-mode');
    panel.hidden = false;
    document.querySelectorAll('.bottom .navbtn').forEach(button =>
      button.classList.toggle('active', button === navButton));
    panel.scrollIntoView({block: 'start', behavior: 'auto'});
    status.textContent = 'Carregant dades de GitHub…';
    try {
      const data = await loadData();
      matches = data.__all ? rowsInLastSevenDays(data.rows) : combinedAgenda(data);
      updateClubOptions();
      updateCategoryOptions();
      renderCards();
    } catch (error) {
      matches = [];
      content.replaceChildren(make('div', 'empty', error.message || 'No s’han pogut carregar els resultats.'));
      counter.textContent = '0 partits';
      status.textContent = 'No s’han pogut llegir els JSON publicats';
    }
  }

  function install() {
    const grid = document.querySelector('.bottom .navgrid');
    const main = document.querySelector('main.app');
    if (!grid || !main || document.getElementById(ID)) return;
    const stylesheet = make('style');
    stylesheet.textContent = `
      /* V2 · SET botons compactes en UNA fila, també a l'iPhone. */
      .bottom{padding:6px 5px calc(env(safe-area-inset-bottom) + 6px)}
      .bottom .bottom-title{display:none}
      .bottom .navgrid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px;align-items:stretch}
      .bottom .navbtn{min-width:0;width:100%;min-height:57px;height:57px;padding:5px 1px;gap:3px;border-radius:10px}
      .bottom .navbtn > span{font-size:19px;line-height:1;display:grid;place-items:center;max-width:100%;min-width:0;min-height:24px}
      .bottom .navbtn > .club-icon{width:28px;height:28px;padding:1px;border-radius:8px;overflow:hidden}
      .bottom .navbtn > .club-icon img{display:block;width:26px;height:26px;max-width:100%;max-height:100%;object-fit:contain}
      .bottom .navbtn strong{width:100%;min-width:0;font-size:9px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:clip;text-align:center}
      .bottom .navbtn small{display:none}
      /* Etiquetes curtes només a la barra: mantenim els noms accessibles originals. */
      .bottom .navbtn[data-tab="celoni"] strong,
      .bottom .navbtn[data-tab="classificacions"] strong,
      .bottom .navbtn[data-tab="home"] strong{font-size:0}
      .bottom .navbtn[data-tab="celoni"] strong::after{content:"Celoni";font-size:9px}
      .bottom .navbtn[data-tab="classificacions"] strong::after{content:"Class.";font-size:9px}
      .bottom .navbtn[data-tab="home"] strong::after{content:"Inici";font-size:9px}
      .bottom .navbtn[data-tab="grupalevi"] strong,
      .bottom .navbtn[data-tab="grupinfantil"] strong{display:none}
      .bottom .navbtn > .nav-name{font-size:13px;font-weight:850;color:#ffc17c}
      @media(max-width:370px){
        .bottom{padding-left:3px;padding-right:3px}
        .bottom .navgrid{gap:2px}
        .bottom .navbtn{height:54px;min-height:54px;padding:4px 0}
        .bottom .navbtn strong,
        .bottom .navbtn[data-tab="celoni"] strong::after,
        .bottom .navbtn[data-tab="classificacions"] strong::after,
        .bottom .navbtn[data-tab="home"] strong::after{font-size:8px}
        #zok-nav-resultats-7dies strong{font-size:8px}
      }
      #${ID}{display:none!important}
      body.zok-recent-mode main.app > :not(.mast):not(#${ID}){display:none!important}
      body.zok-recent-mode #${ID}{display:block!important}
      body.zok-recent-mode #${ID} .zok-recent-filters{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px;margin:14px 0 7px}
      #${ID} .zok-recent-filters label{display:grid;gap:6px;font-size:12px;font-weight:850;color:#b9dbec}
      #${ID} .zok-recent-filters select{width:100%;min-width:0;padding:12px 8px;border:1px solid #7597b0;border-radius:11px;background:#183d5b;color:#fff;font:inherit;font-size:12px}
      #${ID} .zok-recent-period{font-size:12px;color:#b3cee1;margin:7px 0 14px}
      /* V4 · Dues línies i sense franja inferior: només menú Resultats. */
      #${ID} .cards{display:grid;grid-template-columns:minmax(0,1fr);gap:5px}
      #${ID} .zok-recent-card{width:100%;min-width:0;max-width:100%;min-height:0;height:auto;box-sizing:border-box;padding:5px 8px;border-radius:12px;display:flex;flex-direction:column;gap:3px}
      #${ID} .zok-recent-card::before{pointer-events:none}
      #${ID} .zok-recent-card .match-top{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;align-items:center;column-gap:6px;min-width:0;min-height:0;margin:0;padding:0;flex-wrap:nowrap}
      #${ID} .zok-recent-card .pill{display:block;min-width:0;max-width:100%;padding:3px 6px;font-size:9px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      #${ID} .zok-recent-card .zok-recent-time{font-size:12px;line-height:1.1;white-space:nowrap;color:#17324a}
      #${ID} .zok-recent-card .zok-recent-day{font-size:10px;line-height:1.1;white-space:nowrap;color:#526d85}
      #${ID} .zok-recent-card .zok-recent-acta{display:inline-flex;align-items:center;justify-content:center;min-width:0;min-height:24px;width:auto;height:24px;max-width:none;margin:0;padding:3px 8px;flex:0 0 auto;font-size:10px;line-height:1;border-radius:7px;background:#163e5d;color:#fff;white-space:nowrap}
      #${ID} .zok-recent-card .teams{display:grid;grid-template-columns:minmax(0,1fr) 52px minmax(0,1fr);align-items:center;gap:4px;min-width:0;min-height:32px;height:auto;margin:0;padding:0}
      #${ID} .zok-recent-card .side{width:auto;min-width:0;max-width:100%;display:flex;flex-direction:row;align-items:center;justify-content:flex-start;gap:4px;text-align:left}
      #${ID} .zok-recent-card .side:last-child{flex-direction:row-reverse;text-align:right}
      #${ID} .zok-recent-card .side strong{flex:1 1 auto;min-width:0;max-width:100%;font-size:10px;line-height:1.12;overflow-wrap:break-word;word-break:normal;text-align:left}
      #${ID} .zok-recent-card .side:last-child strong{text-align:right}
      #${ID} .zok-recent-card .crest{flex:0 0 26px;width:26px;height:26px;min-width:26px;max-width:26px;border-radius:7px}
      #${ID} .zok-recent-card .crest img{width:23px;height:23px;object-fit:contain}
      #${ID} .zok-recent-card .middle{min-width:0;max-width:52px;width:52px;align-self:center;justify-items:center;gap:0}
      #${ID} .zok-recent-card .score{font-size:19px;line-height:1.1;white-space:nowrap}
      #${ID} .zok-recent-stamp{font-size:11px;color:#b6d2e5;margin-top:14px;line-height:1.45}
      @media(max-width:370px){
        #${ID} .zok-recent-card{padding:4px 6px}
        #${ID} .zok-recent-card .match-top{column-gap:4px}
        #${ID} .zok-recent-card .pill{padding:3px 4px;font-size:8px}
        #${ID} .zok-recent-card .zok-recent-time{font-size:11px}
        #${ID} .zok-recent-card .zok-recent-day{font-size:9px}
        #${ID} .zok-recent-card .zok-recent-acta{padding:3px 6px;font-size:9px}
        #${ID} .zok-recent-card .teams{grid-template-columns:minmax(0,1fr) 44px minmax(0,1fr);gap:3px}
        #${ID} .zok-recent-card .crest{flex-basis:24px;min-width:24px;max-width:24px;width:24px;height:24px}
        #${ID} .zok-recent-card .crest img{width:21px;height:21px}
        #${ID} .zok-recent-card .side strong{font-size:9px}
        #${ID} .zok-recent-card .middle{width:44px;max-width:44px}
        #${ID} .zok-recent-card .score{font-size:17px}
      }
    `;
    document.head.append(stylesheet);

    navButton = make('button', 'navbtn');
    navButton.type = 'button';
    navButton.id = NAV_ID;
    navButton.setAttribute('aria-label', 'Resultats dels darrers set dies');
    navButton.append(make('span', '', '🏁'), make('strong', '', 'Resultats'), make('small', '', 'Últims 7 dies'));
    const home = grid.querySelector('[data-tab="home"]');
    grid.insertBefore(navButton, home || null);

    panel = make('section', 'section');
    panel.id = ID;
    panel.hidden = true;
    const header = make('div', 'section-head');
    const left = make('div');
    left.append(make('span', 'overline', 'AGENDA · MARCADORS'), make('h2', '', 'Últims resultats'));
    counter = make('span', 'section-tag', '0 partits');
    header.append(left, counter);
    const filterRow = make('div', 'zok-recent-filters');
    const clubLabel = make('label', '', 'Club');
    clubFilter = make('select');
    clubFilter.setAttribute('aria-label', 'Filtra els resultats per club');
    clubFilter.append(new Option('Tots els clubs', ''));
    for (const [value, label] of CLUBS) clubFilter.add(new Option(label, value));
    clubLabel.append(clubFilter);
    const categoryLabel = make('label', '', 'Categoria');
    categoryFilter = make('select');
    categoryFilter.setAttribute('aria-label', 'Filtra els resultats per categoria');
    categoryFilter.append(new Option('Totes les categories', ''));
    categoryLabel.append(categoryFilter);
    filterRow.append(clubLabel, categoryLabel);
    content = make('div', 'cards');
    status = make('p', 'zok-recent-stamp', 'Font: Agenda i En directe');
    panel.append(header, filterRow,
      make('p', 'zok-recent-period', 'Darrers 7 dies · Partits amb marcador · Més recents primer'),
      content, status);
    const footer = main.querySelector('.footer');
    main.insertBefore(panel, footer || null);

    // El botó nou no té data-tab: no interfereix amb el selectSection d'app.js.
    navButton.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      void openResults();
    });
    grid.addEventListener('click', event => {
      const other = event.target.closest('.navbtn');
      if (other && other !== navButton) {
        document.body.classList.remove('zok-recent-mode');
        panel.hidden = true;
      }
    }, true);
    clubFilter.addEventListener('change', () => { updateCategoryOptions(); renderCards(); });
    categoryFilter.addEventListener('change', renderCards);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once: true});
  else install();
})();
