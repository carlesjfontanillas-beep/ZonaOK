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
  const emptySelection = () => Object.fromEntries(GROUPS.map(([key]) => [key, []]));
  const nodes = {
    status: document.getElementById('favorites-status'),
    count: document.getElementById('favorites-count'),
    groups: document.getElementById('favorites-groups'),
    search: document.getElementById('favorites-search'),
    clear: document.getElementById('favorites-clear'),
    scope: document.getElementById('favorites-scope-toggle'),
    scopeNote: document.getElementById('favorites-scope-note')
  };
  let catalog = {clubs: [], teams: [], categories: [], competitions: []};
  let selected = readSelection();
  let showAllOptions = false;

  function readSelection() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return Object.fromEntries(GROUPS.map(([key]) => [key,
        Array.isArray(value[key]) ? value[key].map(clean).filter(Boolean) : []]));
    } catch (_) {
      return emptySelection();
    }
  }
  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selected));
      nodes.status.textContent = 'Seleccions desades en aquest navegador.';
    } catch (_) {
      nodes.status.textContent = 'No s’han pogut desar les seleccions en aquest navegador.';
    }
    renderCount();
  }
  function categoryName(value) {
    return clean(value)
      .replace(/\s+(?:OR|PLATA|BRONZE)\s+\d+\b/gi, '')
      .replace(/\s+(?:GRUP|GRUPO)\s+[A-Z0-9]+\b/gi, '').trim();
  }
  function teamKey(team, competition, leagueId) {
    return ['team', team, competition, leagueId].map(norm).join('|');
  }
  function clubLabel(record) {
    const code = norm(record.clubCode);
    if (code === 'CELONI') return 'CP SANT CELONI';
    if (code === 'BARCA') return 'BARÇA';
    const name = clean(record.team);
    // Segueix el patró de noms de clubs de ZonaOK: A/B/C/D final identifica equip.
    return name.replace(/\s+[A-D]$/i, '');
  }
  function buildCatalog(agenda, classifications) {
    const teamRecords = new Map();
    const categories = [];
    const competitions = [];
    const addTeam = (team, competition, category, leagueId, clubCode) => {
      team = clean(team);
      if (!team) return;
      competition = clean(competition);
      category = clean(category) || categoryName(competition);
      const key = teamKey(team, competition, leagueId);
      const record = {key, team, competition, category, leagueId: clean(leagueId), clubCode: clean(clubCode)};
      const previous = teamRecords.get(key);
      teamRecords.set(key, previous ? {...previous, ...record, clubCode: record.clubCode || previous.clubCode} : record);
      categories.push(category);
      competitions.push(competition);
    };

    for (const row of agenda) {
      if (!row || typeof row !== 'object') continue;
      const competition = row.competition || row.category || row.categoria;
      const category = row.category || row.categoria || categoryName(competition);
      const leagueId = row.leagueId || row.league || '';
      addTeam(row.home, competition, category, leagueId, row.homeClub);
      addTeam(row.away, competition, category, leagueId, row.awayClub);
    }

    const entries = classifications && typeof classifications === 'object'
      ? Object.values(classifications.competitions || classifications.leagues || {}) : [];
    for (const item of entries) {
      if (!item || typeof item !== 'object') continue;
      const competition = item.competition || item.name;
      const category = item.category || categoryName(competition);
      for (const row of Array.isArray(item.standings) ? item.standings : []) {
        addTeam(row && row.team, competition, category, item.leagueId || '', '');
      }
      categories.push(category);
      competitions.push(competition);
    }

    const records = [...teamRecords.values()];
    const enrichedRecords = records.map(record => ({...record, club: clubLabel(record)}));
    catalog = {
      clubs: sorted(enrichedRecords.map(record => record.club)),
      teams: enrichedRecords.sort((a, b) => a.team.localeCompare(b.team, 'ca', {sensitivity: 'base'}) ||
        a.competition.localeCompare(b.competition, 'ca', {sensitivity: 'base'})).map(record => ({
          id: record.key,
          label: record.competition ? `${record.team} · ${record.competition}` : record.team,
          club: record.club
        })),
      categories: sorted(categories),
      competitions: sorted(competitions),
      teamRecords: enrichedRecords
    };
    selected = Object.fromEntries(GROUPS.map(([key]) => {
      const allowed = new Set(catalog[key].map(option => typeof option === 'string' ? option : option.id));
      return [key, selected[key].filter(value => allowed.has(value))];
    }));
    render();
  }
  function scopedOptions(key) {
    if (key === 'clubs' || showAllOptions || !selected.clubs.length) return catalog[key];
    const clubs = new Set(selected.clubs);
    const records = catalog.teamRecords.filter(record => clubs.has(record.club));
    if (key === 'teams') return catalog.teams.filter(option => clubs.has(option.club));
    if (key === 'categories') return sorted(records.map(record => record.category));
    if (key === 'competitions') return sorted(records.map(record => record.competition));
    return catalog[key];
  }
  function optionId(option) {
    return typeof option === 'string' ? option : option.id;
  }
  function optionLabel(option) {
    return typeof option === 'string' ? option : option.label;
  }
  function renderCount() {
    const count = GROUPS.reduce((total, [key]) => total + selected[key].length, 0);
    nodes.count.textContent = `${count} ${count === 1 ? 'seleccionat' : 'seleccionats'}`;
  }
  function render() {
    const query = norm(nodes.search.value);
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
      const options = scopedOptions(key);
      const availableIds = new Set(options.map(optionId));
      amount.textContent = `${selected[key].filter(id => availableIds.has(id)).length} / ${options.length}`;
      for (const option of options) {
        const id = optionId(option);
        const label = optionLabel(option);
        const row = document.createElement('label');
        row.className = 'zok-favorite-option';
        row.hidden = Boolean(query && !norm(label).includes(query));
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = selected[key].includes(id);
        checkbox.addEventListener('change', () => {
          selected[key] = checkbox.checked
            ? [...selected[key], id]
            : selected[key].filter(value => value !== id);
          save();
          render();
        });
        const text = document.createElement('span');
        text.textContent = label;
        row.append(checkbox, text);
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
  async function load() {
    try {
      const [dataResponse, standingsResponse] = await Promise.all([
        fetch(`zonaok-data.json?favorits=${Date.now()}`, {cache: 'no-store'}),
        fetch(`zonaok-classificacions.json?favorits=${Date.now()}`, {cache: 'no-store'})
      ]);
      if (!dataResponse.ok) throw new Error(`Agenda: ${dataResponse.status}`);
      const packet = await dataResponse.json();
      if (packet.version !== 3 || !Array.isArray(packet.data?.agenda?.rows))
        throw new Error('format d’agenda no reconegut');
      let standings = {};
      if (standingsResponse.ok) standings = await standingsResponse.json();
      buildCatalog(packet.data.agenda.rows, standings);
      nodes.status.textContent = 'Dades carregades dels JSON publicats a ZonaOK.';
    } catch (_) {
      nodes.status.textContent = 'No s’han pogut carregar els catàlegs. Comprova la connexió i torna-ho a provar.';
      nodes.groups.replaceChildren();
      const message = document.createElement('p');
      message.className = 'empty';
      message.textContent = 'Els favorits utilitzen zonaok-data.json i zonaok-classificacions.json.';
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
  load();
})();
