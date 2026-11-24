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
  const emptySelection = () => ({...Object.fromEntries(GROUPS.map(([key]) => [key, []])), teamNames: {}, clubLogoUrls: {}});
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
      return {...Object.fromEntries(GROUPS.map(([key]) => [key,
        Array.isArray(value[key]) ? value[key].map(clean).filter(Boolean) : []])),
        teamNames: value.teamNames && typeof value.teamNames === 'object' ? value.teamNames : {},
        clubLogoUrls: value.clubLogoUrls && typeof value.clubLogoUrls === 'object' ? value.clubLogoUrls : {}};
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
    const santCeloni = name.match(/^(?:CP )?SANT CELONI(?: ([A-D]))?$/) ||
      name.match(/^CPSC(?: ([A-D]))?$/);
    return santCeloni ? `CPSC${santCeloni[1] || ''}` : clean(value);
  }
  function clubLabel(record) {
    const code = norm(record.clubCode);
    const team = norm(record.team);
    // Reutilitza les equivalències que l'app aplica als noms FECAPA.
    if (code === 'CELONI' || /^CPSC(?:[AB]| [AB])?$/.test(team) || /\bSANT CELONI\b/.test(team))
      return 'CP SANT CELONI';
    if (code === 'BARCA' || /^(?:BAR|BARCA|FC BARCELONA|F C BARCELONA|FCBETERANS|FCBETRANS)(?: [A-Z0-9]+)?$/.test(team))
      return 'BARÇA';
    const name = clean(record.team);
    // La lletra final A/B/C/D identifica un equip dins del club.
    return name.replace(/\s+[A-D]$/i, '');
  }
  function buildCatalog(agenda, classifications) {
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
      teamRecords: enrichedRecords
    };
    selected = {...Object.fromEntries(GROUPS.map(([key]) => {
      const allowed = new Set(catalog[key].map(option => typeof option === 'string' ? option : option.id));
      return [key, selected[key].filter(value => allowed.has(value))];
    })), teamNames: selected.teamNames || {}, clubLogoUrls: selected.clubLogoUrls || {}};
    render();
  }
  function scopedOptions(key) {
    if (key === 'clubs') return catalog.clubs;
    if (showAllOptions) return catalog[key];

    let records = catalog.teamRecords;
    if (selected.clubs.length) {
      const clubs = new Set(selected.clubs);
      records = records.filter(record => clubs.has(record.club));
    }

    const selectedTeams = new Set(selected.teams);
    const selectedCategories = new Set(selected.categories.map(norm));
    const selectedCompetitions = new Set(selected.competitions.map(norm));
    if (key === 'teams') {
      if (selectedCategories.size) records = records.filter(record => selectedCategories.has(norm(record.category)));
      if (selectedCompetitions.size) records = records.filter(record => selectedCompetitions.has(norm(record.competition)));
      const available = new Set(records.map(record => record.key));
      return catalog.teams.filter(option => available.has(option.id));
    }
    if (key === 'categories') {
      if (selectedTeams.size) records = records.filter(record => selectedTeams.has(record.key));
      if (selectedCompetitions.size) records = records.filter(record => selectedCompetitions.has(norm(record.competition)));
      return sorted(records.map(record => record.category));
    }
    if (key === 'competitions') {
      if (selectedTeams.size) records = records.filter(record => selectedTeams.has(record.key));
      if (selectedCategories.size) records = records.filter(record => selectedCategories.has(norm(record.category)));
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
      const chosen = new Set(selected[key]);
      const options = scopedOptions(key).sort((a, b) => {
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
    for (const club of selected.clubs.slice(0, 2)) {
      if (selected.clubLogoUrls[club]) continue;
      const records = catalog.teamRecords.filter(record => record.club === club && /^\d+$/.test(record.leagueId));
      const league = records[0]?.leagueId;
      if (!league) continue;
      try {
        const response = await fetch(`https://www.hoqueipatins.fecapa.cat/?liga=${encodeURIComponent(league)}&vista=plantillas`, {mode: 'cors', cache: 'no-store'});
        if (!response.ok) continue;
        const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
        const aliases = records.map(record => norm(record.team)).filter(Boolean);
        const match = [...doc.querySelectorAll('img[src*="logos_clubes/"]')].find(image => aliases.some(alias => {
          const alt = norm(image.alt || image.title || '');
          return alt && (alt === alias || alt.startsWith(alias + ' ') || alias.startsWith(alt + ' '));
        }));
        if (match) {
          const url = new URL(match.getAttribute('src'), 'https://www.hoqueipatins.fecapa.cat/').href;
          const parsed = new URL(url);
          if (parsed.hostname === 'sidgad.cloud' && /\/logos_clubes\/\d+\.png$/.test(parsed.pathname)) {
            selected.clubLogoUrls[club] = url;
            save();
            window.dispatchEvent(new CustomEvent('zonaok:favorites-updated'));
          }
        }
      } catch (_) {
        // Si FECAPA no permet la lectura entre dominis, l'app conserva els escuts coneguts.
      }
    }
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
      nodes.status.textContent = location.protocol === 'file:'
        ? 'Previsualització local: Safari pot separar les seleccions de Favorits i Inici.'
        : 'Dades carregades dels JSON publicats a ZonaOK.';
      discoverClubLogos();
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
