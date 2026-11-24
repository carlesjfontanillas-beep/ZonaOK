/* Favorits ZonaOK · seleccions independents sobre els catàlegs ja publicats. */
(() => {
  'use strict';
  const STORAGE_KEY = 'ZONAOK_FAVORITS_V1';
  const GROUPS = [
    ['clubs', 'Clubs'],
    ['teams', 'Equips'],
    ['categories', 'Categories'],
    ['competitions', 'Competicions']
  ];
  const norm = value => String(value ?? '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, ' ').trim().toUpperCase();
  const clean = value => String(value ?? '').trim().replace(/\s+/g, ' ');
  const sorted = values => [...new Set(values.map(clean).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, 'ca', {sensitivity: 'base'}));
  const emptySelection = () => ({...Object.fromEntries(GROUPS.map(([key]) => [key, []])), teamNames: {}, clubLogoUrls: {}, teamLogoUrls: {}, clubColors: {}, teamColors: {}, teamLeagueIds: {}, playerIds: {}});
  const nodes = {
    status: document.getElementById('favorites-status'),
    count: document.getElementById('favorites-count'),
    groups: document.getElementById('favorites-groups'),
    search: document.getElementById('favorites-search'),
    clear: document.getElementById('favorites-clear'),
    scope: document.getElementById('favorites-scope-toggle'),
    scopeNote: document.getElementById('favorites-scope-note')
  };
  let catalog = {clubs: [], teams: [], categories: [], competitions: [], clubLogos: {}};
  let selected = readSelection();
  let showAllOptions = false;

  function readSelection() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return {...Object.fromEntries(GROUPS.map(([key]) => [key,
        Array.isArray(value[key]) ? value[key].map(clean).filter(Boolean) : []])),
        teamNames: value.teamNames && typeof value.teamNames === 'object' ? value.teamNames : {},
        clubLogoUrls: value.clubLogoUrls && typeof value.clubLogoUrls === 'object' ? value.clubLogoUrls : {},
        teamLogoUrls: value.teamLogoUrls && typeof value.teamLogoUrls === 'object' ? value.teamLogoUrls : {},
        clubColors: value.clubColors && typeof value.clubColors === 'object' ? value.clubColors : {},
        teamColors: value.teamColors && typeof value.teamColors === 'object' ? value.teamColors : {},
        teamLeagueIds: value.teamLeagueIds && typeof value.teamLeagueIds === 'object' ? value.teamLeagueIds : {},
        playerIds: value.playerIds && typeof value.playerIds === 'object' ? value.playerIds : {}};
    } catch (_) {
      return emptySelection();
    }
  }
  function save() {
    try {
      const serialized = JSON.stringify(selected);
      localStorage.setItem(STORAGE_KEY, serialized);
      if (localStorage.getItem(STORAGE_KEY) !== serialized) throw new Error('Storage verification failed');
      nodes.status.textContent = location.protocol === 'file:'
        ? 'Desades a la previsualització local. Safari pot no compartir-les amb Inici; prova l’adreça web de ZonaOK.'
        : 'Seleccions desades en aquest navegador.';
    } catch (_) {
      nodes.status.textContent = 'No s’han pogut desar les seleccions en aquest navegador.';
    }
    renderCount();
  }
  function competitionName(value) {
    return clean(value)
      .replace(/\b(OR|PLATA|BRONZE)\s+\d+\b/gi, '$1')
      .replace(/\s+(?:GRUP|GRUPO)\s+[A-Z0-9]+\b/gi, '').trim();
  }
  function teamKey(team, category) {
    return ['team', team, category].map(norm).join('|');
  }
  function shortTeamName(value) {
    const name = norm(value);
    return clean(value);
  }
  function clubLabel(record) {
    const code = norm(record.clubCode);
    const team = norm(record.team);
    // Reutilitza les equivalències que l'app aplica als noms FECAPA.
    if (code === 'CELONI' || /^CPSC(?:[AB]| [AB])?$/.test(team) || /\bSANT CELONI\b/.test(team))
      return 'CP SANT CELONI';
    if (code === 'BARCA' || /^(?:BAR|BARCA|FC BARCELONA|F C BARCELONA|FCBETERANS|FCBETRANS)(?: [A-Z0-9]+)?$/.test(team))
      return 'BARÇA';
    return clubBaseName(record.team);
  }
  function clubBaseName(value) {
    return clean(value).replace(/\s*-\s*[A-Z]$/i, '').replace(/\s+[A-Z]$/i, '').replace(/\s*-\s*$/i, '').trim();
  }
  function buildCatalog(agenda, classifications, clubLogos = {}) {
    const teamRecords = new Map();
    const categories = [];
    const competitions = [];
    const entries = classifications && typeof classifications === 'object'
      ? Object.values(classifications.competitions || classifications.leagues || {}) : [];
    const classificationByKey = new Map();
    const classificationByName = new Map();
    for (const item of entries) {
      if (!item || typeof item !== 'object') continue;
      const exactName = clean(item.name || item.category || item.competition);
      const league = clean(item.leagueId);
      const descriptor = {category: exactName, competition: clean(item.competition) || competitionName(exactName)};
      if (exactName) {
        if (league) classificationByKey.set(`${norm(league)}|${norm(exactName)}`, descriptor);
        const nameKey = norm(exactName);
        if (!classificationByName.has(nameKey)) classificationByName.set(nameKey, descriptor);
        else classificationByName.set(nameKey, null);
      }
    }
    const addTeam = (team, category, competition, leagueId, clubCode) => {
      team = clean(team);
      if (!team) return;
      category = clean(category) || competitionName(competition);
      competition = clean(competition) || competitionName(category);
      const key = teamKey(team, category);
      const record = {key, team, category, competition, leagueId: clean(leagueId), clubCode: clean(clubCode)};
      const previous = teamRecords.get(key);
      teamRecords.set(key, previous ? {...previous, ...record, clubCode: record.clubCode || previous.clubCode} : record);
      categories.push(category);
      competitions.push(competition);
    };

    for (const row of agenda) {
      if (!row || typeof row !== 'object') continue;
      const exactName = clean(row.competition || row.category || row.categoria);
      const leagueId = clean(row.leagueId || row.league || '');
      const descriptor = classificationByKey.get(`${norm(leagueId)}|${norm(exactName)}`) ||
        classificationByName.get(norm(exactName));
      const category = descriptor?.category || exactName;
      const competition = descriptor?.competition || competitionName(exactName);
      addTeam(row.home, category, competition, leagueId, row.homeClub);
      addTeam(row.away, category, competition, leagueId, row.awayClub);
    }

    for (const item of entries) {
      if (!item || typeof item !== 'object') continue;
      const category = clean(item.name || item.category || item.competition);
      const competition = clean(item.competition) || competitionName(category);
      for (const row of Array.isArray(item.standings) ? item.standings : []) {
        addTeam(row && row.team, category, competition, item.leagueId || '', '');
      }
      categories.push(category);
      competitions.push(competition);
    }

    const records = [...teamRecords.values()];
    const enrichedRecords = records.map(record => ({...record, club: clubLabel(record)}));
    catalog = {
      clubs: sorted(enrichedRecords.map(record => record.club)),
      teams: enrichedRecords.sort((a, b) => a.team.localeCompare(b.team, 'ca', {sensitivity: 'base'}) ||
        a.category.localeCompare(b.category, 'ca', {sensitivity: 'base'})).map(record => ({
          id: record.key,
          label: record.category ? `${record.category} · ${shortTeamName(record.team)}` : shortTeamName(record.team),
          club: record.club
        })),
      categories: sorted(categories),
      competitions: sorted(competitions),
      teamRecords: enrichedRecords,
      agendaRows: agenda,
      clubLogos: clubLogos && typeof clubLogos === 'object' ? clubLogos : {}
    };
    const clubsByName = new Map(catalog.clubs.map(club => [norm(club), club]));
    const clubAliases = new Map(), migratedClubs = [];
    for (const oldClub of selected.clubs || []) {
      const canonical = clubsByName.get(norm(clubBaseName(oldClub))) || clubsByName.get(norm(oldClub));
      if (canonical) { clubAliases.set(oldClub, canonical); migratedClubs.push(canonical); }
    }
    const migrateClubMap = source => {
      const result = {...(source || {})};
      for (const [oldClub, canonical] of clubAliases) {
        if (oldClub === canonical) continue;
        if (!result[canonical] && result[oldClub]) result[canonical] = result[oldClub];
        delete result[oldClub];
      }
      return result;
    };
    selected = {...Object.fromEntries(GROUPS.map(([key]) => {
      const allowed = new Set(catalog[key].map(option => typeof option === 'string' ? option : option.id));
      const values = key === 'clubs' ? [...new Set(migratedClubs)] : selected[key];
      return [key, values.filter(value => allowed.has(value))];
    })), teamNames: selected.teamNames || {}, clubLogoUrls: migrateClubMap(selected.clubLogoUrls), teamLogoUrls: {}, clubColors: migrateClubMap(selected.clubColors), teamColors: selected.teamColors || {}, teamLeagueIds: {...(selected.teamLeagueIds||{}), ...Object.fromEntries(selected.teams.map(id=>{const record=catalog.teamRecords.find(item=>item.key===id);return [id,record?.leagueId||'']}))}, playerIds: selected.playerIds || {}};
    save();
    render();
  }
  function scopedOptions(key, matchingClubs = new Set()) {
    if (key === 'clubs') return catalog.clubs;
    if (showAllOptions) return catalog[key];

    let records = catalog.teamRecords;
    const matches = selected.clubs.filter(club => matchingClubs.has(norm(club)));
    let clubSearchScope = matches.length > 0;

    if (selected.clubs.length) {
      const allowed = new Set(clubSearchScope ? matches : selected.clubs);
      records = records.filter(record => allowed.has(record.club));
    } else if (matchingClubs.size) {
      records = records.filter(record => matchingClubs.has(norm(record.club)));
      clubSearchScope = records.length > 0;
    }

    if (key === 'teams') {
      const available = new Set(records.map(record => record.key));
      return catalog.teams.filter(option => available.has(option.id));
    }
    if (key === 'categories') return sorted(records.map(record => record.category));
    if (key === 'competitions') {
      if (!clubSearchScope) {
        const selectedTeams = new Set(selected.teams);
        const selectedCategories = new Set(selected.categories.map(norm));
        const selectedCompetitions = new Set(selected.competitions.map(norm));
        if (selectedTeams.size || selectedCategories.size || selectedCompetitions.size) {
          records = records.filter(record =>
            selectedTeams.has(record.key) ||
            selectedCategories.has(norm(record.category)) ||
            selectedCompetitions.has(norm(record.competition)));
        }
      }
      return sorted(records.map(record => record.competition));
    }
    return catalog[key];
  }
  function optionId(option) {
    return typeof option === 'string' ? option : option.id;
  }
  function optionLabel(option) {
    return typeof option === 'string' ? option : option.label;
  }
  function optionMatchesSearch(key, option, label, query, matchingClubs) {
    if (!query || norm(label).includes(query)) return true;
    if (!matchingClubs.size) return false;
    const clubMatches = record => matchingClubs.has(norm(record.club));
    if (key === 'teams') return matchingClubs.has(norm(option.club));
    if (key === 'categories') return catalog.teamRecords.some(record =>
      norm(record.category) === norm(option) && clubMatches(record));
    if (key === 'competitions') return catalog.teamRecords.some(record =>
      norm(record.competition) === norm(option) && clubMatches(record));
    return false;
  }
  function renderCount() {
    const count = GROUPS.reduce((total, [key]) => total + selected[key].length, 0);
    nodes.count.textContent = `${count} ${count === 1 ? 'seleccionat' : 'seleccionats'}`;
  }
  function render() {
    const query = norm(nodes.search.value);
    const matchingClubs = new Set(query ? catalog.clubs.filter(club => norm(club).includes(query)).map(norm) : []);
    const hasClubScope = selected.clubs.length > 0;
    nodes.scope.hidden = !hasClubScope;
    nodes.scope.textContent = showAllOptions ? 'Limita a clubs marcats' : 'Mostra totes les opcions';
    nodes.scopeNote.textContent = hasClubScope && !showAllOptions
      ? 'Equips, categories i competicions filtrats pels clubs marcats. Les seleccions desades es conserven.'
      : hasClubScope ? 'Mostrant totes les opcions; les seleccions desades es conserven.'
      : 'Marca un club per limitar els equips, les categories i les competicions disponibles.';
    nodes.groups.replaceChildren();
    for (const [key, title] of GROUPS) {
      const section = document.createElement('section');
      section.className = 'zok-favorite-group';
      const heading = document.createElement('h2');
      heading.textContent = title;
      const amount = document.createElement('small');
      amount.textContent = `${selected[key].length} / ${catalog[key].length}`;
      heading.append(amount);
      section.append(heading);
      const list = document.createElement('div');
      list.className = 'zok-favorite-list';
      const chosen = new Set(selected[key]);
      const options = scopedOptions(key, matchingClubs).sort((a, b) => {
        const selectedFirst = Number(chosen.has(optionId(b))) - Number(chosen.has(optionId(a)));
        if (selectedFirst) return selectedFirst;
        if (key === 'teams') {
          const clubA = typeof a === 'string' ? '' : a.club || '';
          const clubB = typeof b === 'string' ? '' : b.club || '';
          const byClub = clubA.localeCompare(clubB, 'ca', {sensitivity: 'base'});
          if (byClub) return byClub;
        }
        return optionLabel(a).localeCompare(optionLabel(b), 'ca', {sensitivity: 'base'});
      });
      const availableIds = new Set(options.map(optionId));
      amount.textContent = `${selected[key].filter(id => availableIds.has(id)).length} / ${options.length}`;
      for (const option of options) {
        const id = optionId(option);
        const label = optionLabel(option);
        const row = document.createElement('label');
        row.className = 'zok-favorite-option';
        row.hidden = Boolean(query && !optionMatchesSearch(key, option, label, query, matchingClubs));
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = selected[key].includes(id);
        checkbox.addEventListener('change', () => {
          selected[key] = checkbox.checked
            ? [...selected[key], id]
            : selected[key].filter(value => value !== id);
          save();
          render();
          if (key === 'clubs') void discoverClubLogos();
        });
        const logoUrl = key === 'clubs' ? selected.clubLogoUrls[id] : '';
        if (logoUrl && /^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(logoUrl)) {
          const crest = document.createElement('img'); crest.className='zok-favorite-option-crest';
          crest.src=logoUrl; crest.alt=''; crest.loading='lazy'; crest.decoding='async';
          crest.onerror=()=>crest.remove(); row.append(crest);
        }
        const text = document.createElement('span');
        text.className='zok-favorite-option-label';
        text.textContent = label;
        row.append(checkbox, text);
        if (checkbox.checked && (key === 'clubs' || key === 'teams')) {
          const colors = key === 'clubs' ? selected.clubColors : selected.teamColors;
          const picker = document.createElement('input');
          picker.type='color'; picker.className='zok-favorite-color';
          picker.value=/^#[0-9a-f]{6}$/i.test(colors[id]||'')?colors[id]:'#dce8f1';
          picker.setAttribute('aria-label','Color de '+label);
          picker.title='Color de '+label;
          picker.addEventListener('input',()=>{colors[id]=picker.value;save();window.dispatchEvent(new CustomEvent('zonaok:favorites-updated'))});
          row.append(picker);
        }
        if (key === 'teams' && checkbox.checked) {
          const name = document.createElement('input');
          name.type = 'text'; name.className = 'zok-favorite-child-name';
          name.maxLength = 32; name.autocomplete = 'given-name';
          name.placeholder = 'Nom del fill o la filla';
          name.setAttribute('aria-label', `Nom personalitzat per a ${label}`);
          name.value = clean(selected.teamNames[id] || '');
          name.addEventListener('input', () => { selected.teamNames[id] = name.value.slice(0, 32); save(); });
          row.append(name);
        }
        list.append(row);
      }
      if (!catalog[key].length) {
        const empty = document.createElement('p');
        empty.className = 'zok-favorite-empty';
        empty.textContent = 'No hi ha dades disponibles en els JSON publicats.';
        list.append(empty);
      }
      section.append(list);
      nodes.groups.append(section);
    }
    renderCount();
  }
  async function discoverClubLogos() {
    const safeLogo = value => /^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(String(value||''));
    const clubKey = value => {
      const key = norm(clubBaseName(value));
      if (/\bSANT CELONI\b/.test(key)) return 'CP SANT CELONI';
      if (/\b(BARCA|FC BARCELONA|FCBETERANS|FCBETRANS)\b/.test(key)) return 'BARÇA';
      return key;
    };
    const missing = new Map(selected.clubs
      .filter(club => !selected.clubLogoUrls[club])
      .map(club => [clubKey(club), club]));
    if (!missing.size) return;
    let changed = false;
    // Només desem els escuts dels clubs que l'usuari ha triat.
    for (const [rawName, logo] of Object.entries(catalog.clubLogos || {})) {
      const club = missing.get(clubKey(rawName));
      if (!club || !safeLogo(logo)) continue;
      selected.clubLogoUrls[club] = logo;
      missing.delete(clubKey(rawName));
      changed = true;
      if (!missing.size) break;
    }
    // Fallback de l'agenda per als clubs que no surtin al catàleg de logos.
    if (missing.size) {
      for (const row of catalog.agendaRows || []) {
        for (const side of ['home', 'away']) {
          const club = missing.get(clubKey(row?.[side] || ''));
          const logo = row?.[side + 'Logo'] || '';
          if (!club || !safeLogo(logo)) continue;
          selected.clubLogoUrls[club] = logo;
          missing.delete(clubKey(row[side]));
          changed = true;
        }
        if (!missing.size) break;
      }
    }
    if (changed) { save(); render(); window.dispatchEvent(new CustomEvent('zonaok:favorites-updated')); }
  }
  async function load() {
    try {
      const [agendaResponse, standingsResponse] = await Promise.all([
        fetch(`zonaok-tots-agenda.json?favorits=${Date.now()}`, {cache: 'no-store'}),
        fetch(`zonaok-classificacions.json?favorits=${Date.now()}`, {cache: 'no-store'})
      ]);
      if (!agendaResponse.ok) throw new Error(`Agenda total: ${agendaResponse.status}`);
      const packet = await agendaResponse.json();
      if (packet?.schema !== 'zonaok-all-v1' || packet?.kind !== 'agenda' || !Array.isArray(packet.rows) || !packet.rows.length)
        throw new Error('L’agenda total està buida o té un format incorrecte.');
      let standings = {};
      if (standingsResponse.ok) standings = await standingsResponse.json();
      buildCatalog(packet.rows, standings, packet.clubLogos || {});
      nodes.status.textContent = location.protocol === 'file:'
        ? 'Previsualització local: Safari pot separar les seleccions de Favorits i Inici.'
        : 'Clubs, equips i escuts carregats de l’agenda total FECAPA.';
      discoverClubLogos();
    } catch (_) {
      nodes.status.textContent = 'No s’ha pogut carregar l’agenda total. Revisa zonaok-tots-agenda.json i torna-ho a provar.';
      nodes.groups.replaceChildren();
      const message = document.createElement('p');
      message.className = 'empty';
      message.textContent = 'Els clubs, equips, partits i escuts es carreguen de zonaok-tots-agenda.json.';
      nodes.groups.append(message);
    }
  }
  nodes.search.addEventListener('input', render);
  nodes.scope.addEventListener('click', () => {
    showAllOptions = !showAllOptions;
    render();
  });
  nodes.clear.addEventListener('click', () => {
    selected = emptySelection();
    save();
    render();
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    selected = readSelection();
    render();
  });
  window.addEventListener('storage', event => {
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    selected = readSelection();
    render();
  });
  load();
})();
