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
  let catalog = {clubs: [], teams: [], categories: [], competitions: [], teamRecords: [], agendaRows: [], clubLogos: {}, clubNameLookup: new Map()};
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
    // Preserva els nivells i grups que formen part del nom FECAPA.
    return clean(value);
  }
  function teamKey(team, category) {
    return ['team', team, category].map(norm).join('|');
  }
  function shortTeamName(value) {
    const name = norm(value);
    return clean(value);
  }
  // FECAPA crest identifiers, with display names verified against the published crest catalog.
  const CLUB_NAMES_BY_CREST = {"231":"CLUB HOQUEI ARENYS DE MAR","233":"UNIÓ ESPORTIVA HOQUEI BARBERÀ","234":"BARÇA","235":"CLUB TENNIS BARCINO","236":"CHP BIGUES I RIELLS","237":"CH CALDES RECAM LÀSER","239":"CAPELLADES HC","240":"ASSOCIACIÓ ESPORTIVA CASP","242":"CLUB HOQUEI CASTELLET","243":"CLUB PATÍ CENTELLES","244":"CERDANYOLA CLUB D´HOQUEI","248":"CE CORNELLÀ","250":"CLUB PATÍ FOLGUEROLES","253":"JESUS MARIA I JOSEP","255":"CE LA SALLE BONANOVA","259":"MARTINELIA CLUB PATÍ MANLLEU","260":"CLUB PATÍ MANRESA","263":"CLUB HOQUEI MATARÓ","269":"CE NOIA","270":"CLUB ESPORTIU OLESA PATÍ","275":"CLUB HOQUEI PRAT","278":"CLUB HOQUEI RIPOLLET","279":"CLUB PATÍ RIUDEBITLLES","280":"CLUB PATÍ RODA","281":"CP SANT CELONI","282":"PHC SANT CUGAT","283":"CLUB HOQUEI PATINS SANT FELIU","287":"HF SANT JOSEP SANT SADURNÍ","289":"CLUB PATÍ SANT RAMON","295":"CLUB PATÍ TARADELL","296":"HOQUEI PATINS TONA","300":"CLUB PATÍ VIC","301":"CLUB PATÍ VILAFRANCA","302":"CLUB PATÍ VILANOVA","304":"CLUB PATÍ VOLTREGÀ","307":"CLUB PATÍ BREDA","308":"CP CALDES DE MALAVELLA","309":"FOMENT DEPORTIU CASSANENC","311":"GEIEG","315":"CLUB HOQUEI OLOT","316":"CLUB HOQUEI PALAFRUGELL","317":"CLUB PATÍ RIBES DE FRESER","321":"CLUB HOQUEI PATINS AMPOSTA","322":"CLUB PATÍ CALAFELL","323":"CAMBRILS CLUB HOQUEI","324":"HOQUEI CASAL L´ESPLUGA","326":"CLUB PATI FLIX","332":"CLUB D´ESPORTS VENDRELL","333":"HOQUEI CLUB ALPICAT","334":"CLUB HOQUEI VILA-SECA","335":"CLUB PATÍ BELL-LLOC","338":"CLUB HOQUEI JUNEDA","339":"LLEIDA LLISTA BLAVA","393":"TRANSLOP ALCAÑIZ CLUB PATÍN","398":"CPI LA SAGRERA","425":"TÀRREGA HOQUEI PATINS CLUB","443":"CLUB HOQUEI CLARET","464":"HOQUEI BANYOLES","474":"IGUALADA FEMENÍ HCP","475":"CEH SABADELL","477":"CLUB HOQUEI LES FRANQUESES","493":"HOQUEI CLUB VALLS","520":"CLUB HOQUEI PATINS MARTORELL","521":"CP SUBUR SITGES","551":"SFERIC","572":"SD ESPANYOL","657":"CLUB HOQUEI MOLINS DE REI","665":"CP FRAGA","724":"CE SAGRERENC","727":"SE LA SALLE BONANOVA","232_1":"CE ARENYS DE MUNT","337_2":"CLUB HOQUEI CADÍ","312_1":"GIRONA CLUB HOQUEI","241_2":"HOQUEI CLUB CASTELLAR","319_4":"HOQUEI CLUB RIPOLL","252_1":"IGUALADA HC","392_1":"CLUB PATÍ TORRELLES","341_1":"CLUB PATÍ VILA-SANA","318_1":"HOQUEI CLUB SALT","271_1":"HC PALAU PLEGAMANS","692_2":"PATÍ VIC","428_1":"ANDORRA HOQUEI CLUB","298_1":"CE TORRELAVIT","303_1":"CLUB HOQUEI VILASSAR","310_5":"CLUB HOQUEI FARNERS","360_1":"CLUB PATÍ CUBELLES","246_1":"CP CONGRÉS","267_3":"CLUB PATÍ MONJOS","330_4":"CP RIUDOMS","297_1":"CLUB PATI TORDERA","292_1":"HOQUEI CLUB SENTMENAT","313_1":"CLUB HOQUEI LLORET","251_1":"UNIÓ ESPORTIVA D’HORTA","517_1":"CLUB PATÍ BLANES ATLÈTIC","261_1":"FUTBOL CLUB MARTINENC","288_1":"HC SANT JUST","266_1":"MOLLET HC","328_2":"REUS DEPORTIU","320_1":"SHUM","518_1":"CH FIGUERES","340_1":"CLUB HOQUEI MOLLERUSSA","291_3":"CLUB HOQUEI SANTA PERPÈTUA","314_1":"CLUB PATÍ JONQUERENC","262_2":"CLUB PATÍ MASQUEFA","258_1":"CLUB PATÍ MALGRAT ABADEN","290_1":"HOQUEI CLUB MONTBUI","329_1":"CN REUS PLOMS","638_1":"CEH OLÍMPIC REUS","254_7":"UNIÓ ESPORTIVA LA GARRIGA","268_1":"CLUB HOQUEI NAVARCLES","286_1":"CHP SANT JOSEP DE BADALONA","575_1":"CP CORBERA","277_2":"RIBES CLUB PATI","325_1":"CLUB HOQUEI MONTBLANC","553_3":"CLUB HOQUEI SANT JORDI","285_1":"MARISTES SANT JOAN","612_1":"CP MONTESQUIU","274_1":"HOQUEI CLUB PIERA","238_2":"CLUB HOQUEI CANET","276_1":"CLUB HOQUEI PREMIÀ"};
  const crestId = url => String(url || '').match(/\/(\d+(?:_\d+)?)\.(?:png|gif)$/i)?.[1] || '';
  const isVenue = name => /^(?:PAVELLO|POLIESPORTIU|PISTA\s+\d|MUNICIPAL D ESPORTS)/.test(norm(name));
  // Unidentified short codes remain in team records, never masquerade as separate clubs.
  const isUnknownCode = name => /^[A-Z0-9]{2,5}$/.test(clean(name));
  function makeClubResolver(records, logos) {
    const logoNames = new Map();
    const nameToCrest = new Map();
    const canonicalByCrest = new Map();
    for (const [name, url] of Object.entries(logos || {})) {
      const names = logoNames.get(url) || [];
      names.push(clean(name)); logoNames.set(url, names);
      const id = crestId(url);
      if (id) nameToCrest.set(norm(name), id);
    }
    for (const [url, names] of logoNames) {
      const id = crestId(url);
      if (!id) continue;
      const preferred = CLUB_NAMES_BY_CREST[id];
      const candidates = names.filter(name => !isUnknownCode(name) && !/(?:\\s*-\\s*|\\s+)[A-Z]$/.test(norm(name)));
      const canonical = (preferred && names.find(name => norm(name) === norm(preferred))) || candidates.sort((a,b)=>a.length-b.length || a.localeCompare(b,'ca'))[0] || names[0];
      if (canonical) canonicalByCrest.set(id, preferred && norm(canonical) === norm(preferred) ? preferred : canonical);
    }
    const variants = new Map();
    const labels = [...records.map(r => r.team), ...Object.keys(logos || {})];
    for (const label of labels) {
      const m = clean(label).match(/^(.*?)(?:\s*-\s*|\s+)([A-Z])$/i);
      if (!m) continue;
      const prefix = clean(m[1]), set = variants.get(norm(prefix)) || new Set();
      set.add(m[2].toUpperCase()); variants.set(norm(prefix), set);
    }
    const verifiedBases = new Map();
    for (const label of labels) {
      const m = clean(label).match(/^(.*?)(?:\s*-\s*|\s+)([A-Z])$/i);
      if (!m) continue;
      const prefix = clean(m[1]);
      const url = Object.entries(logos || {}).find(([name]) => norm(name) === norm(label))?.[1];
      const exactBase = url && (logoNames.get(url) || []).find(name => norm(name) === norm(prefix));
      if (exactBase || (variants.get(norm(prefix))?.size || 0) >= 2)
        verifiedBases.set(norm(prefix), exactBase || prefix);
    }
    return record => {
      const team = clean(record.team), code = norm(record.clubCode), key = norm(team);
      if (code === 'CELONI' || /^CPSC(?:[AB]| [AB])?$/.test(key) || /\bSANT CELONI\b/.test(key)) return 'CP SANT CELONI';
      if (code === 'BARCA' || /^(?:BAR|BARCA|FC BARCELONA|F C BARCELONA|FCBETERANS|FCBETRANS)(?: [A-Z0-9]+)?$/.test(key)) return 'BARÇA';
      if (isVenue(team)) return '';
      const exact = canonicalByCrest.get(nameToCrest.get(key));
      if (exact) return exact;
      const m = team.match(/^(.*?)(?:\s*-\s*|\s+)([A-Z])$/i);
      if (m && verifiedBases.has(norm(m[1]))) {
        const base = verifiedBases.get(norm(m[1]));
        return canonicalByCrest.get(nameToCrest.get(norm(base))) || base;
      }
      return isUnknownCode(team) ? '' : team;
    };
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
      const descriptor = {category: exactName, competition: clean(item.competition) || exactName};
      if (exactName) {
        if (league) classificationByKey.set(`${norm(league)}|${norm(exactName)}`, descriptor);
        const nameKey = norm(exactName);
        if (!classificationByName.has(nameKey)) classificationByName.set(nameKey, descriptor);
        else classificationByName.set(nameKey, null);
      }
    }
    const addTeam = (team, category, competition, leagueId, clubCode) => {
      team = clean(team);
      if (!team || isVenue(team)) return;
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
      const competition = descriptor?.competition || exactName;
      addTeam(row.home, category, competition, leagueId, row.homeClub);
      addTeam(row.away, category, competition, leagueId, row.awayClub);
    }

    for (const item of entries) {
      if (!item || typeof item !== 'object') continue;
      const category = clean(item.name || item.category || item.competition);
      const competition = clean(item.competition) || category;
      for (const row of Array.isArray(item.standings) ? item.standings : []) {
        addTeam(row && row.team, category, competition, item.leagueId || '', '');
      }
      categories.push(category);
      competitions.push(competition);
    }

    const records = [...teamRecords.values()];
    const resolveClub = makeClubResolver(records, clubLogos);
    const enrichedRecords = records.map(record => ({...record, club: resolveClub(record)}));
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
    // Use the same verified club grouping for saved favorites and crests.
    catalog.clubNameLookup = new Map(clubsByName);
    for (const record of enrichedRecords) {
      if (record.club && !catalog.clubNameLookup.has(norm(record.team))) catalog.clubNameLookup.set(norm(record.team), record.club);
    }
    for (const name of Object.keys(clubLogos || {})) {
      const canonical = clubsByName.get(norm(resolveClub({team: name})));
      if (canonical && !catalog.clubNameLookup.has(norm(name))) catalog.clubNameLookup.set(norm(name), canonical);
    }
    const clubAliases = new Map(), migratedClubs = [];
    for (const oldClub of selected.clubs || []) {
      const canonical = catalog.clubNameLookup.get(norm(oldClub)) || clubsByName.get(norm(resolveClub({team: oldClub})));
      if (canonical) { clubAliases.set(oldClub, canonical); migratedClubs.push(canonical); }
      else migratedClubs.push(oldClub);
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
    const migratedLogoMap = migrateClubMap(selected.clubLogoUrls);
    for (const [name,url] of Object.entries(clubLogos || {})) {
      const canonical = catalog.clubNameLookup.get(norm(name));
      if (canonical && migratedClubs.includes(canonical) && crestId(url)) migratedLogoMap[canonical] = url;
    }
    const favoriteClubSet = new Set(migratedClubs);
    const favoriteClubLogos = Object.fromEntries(Object.entries(migratedLogoMap).filter(([club]) => favoriteClubSet.has(club)));
    selected = {...Object.fromEntries(GROUPS.map(([key]) => {
      const values = key === 'clubs' ? [...new Set(migratedClubs)] : selected[key];
      return [key, values];
    })), teamNames: selected.teamNames || {}, clubLogoUrls: favoriteClubLogos, teamLogoUrls: {}, clubColors: migrateClubMap(selected.clubColors), teamColors: selected.teamColors || {}, teamLeagueIds: {...(selected.teamLeagueIds||{}), ...Object.fromEntries(selected.teams.map(id=>{const record=catalog.teamRecords.find(item=>item.key===id);return [id,record?.leagueId||'']}))}, playerIds: selected.playerIds || {}};
    save();
    render();
  }
  function scopedOptions(key, matchingClubs = new Set()) {
    if (key === 'clubs') return catalog.clubs;
    if (showAllOptions) return catalog[key];

    let records = catalog.teamRecords;
    const activeClubs = selected.clubs.filter(club => catalog.clubs.includes(club));
    const matches = activeClubs.filter(club => matchingClubs.has(norm(club)));
    let clubSearchScope = matches.length > 0;

    if (activeClubs.length) {
      const allowed = new Set(clubSearchScope ? matches : activeClubs);
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
  // Read-only catalog shared with push settings. Never expose personal aliases as team labels.
  window.ZonaOKPushFavoriteCatalog = () => ({
    teams: catalog.teams.map(option => ({id: option.id, label: option.label})),
    categories: scopedOptions('categories').map(optionId),
    competitions: scopedOptions('competitions').map(optionId)
  });
  function optionMatchesSearch(key, option, label, query, matchingClubs) {
    if (!query || norm(label).includes(query)) return true;
    if (!matchingClubs.size) return false;
    const clubMatches = record => matchingClubs.has(norm(record.club));
    if (key === 'clubs') return matchingClubs.has(norm(option));
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
    if (query) for (const [alias,club] of catalog.clubNameLookup) if (alias.includes(query)) matchingClubs.add(norm(club));
    const hasClubScope = selected.clubs.some(club => catalog.clubs.includes(club));
    nodes.scope.hidden = !hasClubScope;
    nodes.scope.textContent = showAllOptions ? 'Limita a clubs marcats' : 'Mostra totes les opcions';
    nodes.scopeNote.textContent = hasClubScope && !showAllOptions
      ? 'Equips, categories i competicions filtrats pels clubs marcats. Les seleccions desades es conserven.'
      : hasClubScope ? 'Mostrant totes les opcions; les seleccions desades es conserven.'
      : 'Marca un club per limitar els equips, les categories i les competicions disponibles.';
    const playerSection = document.getElementById('jugadors-favorits');
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
        const teamRow = key === 'teams';
        const row = document.createElement(teamRow ? 'div' : 'label');
        row.className = 'zok-favorite-option' + (teamRow ? ' zok-jp-team-row' : '');
        row.hidden = Boolean(query && !optionMatchesSearch(key, option, label, query, matchingClubs));
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = selected[key].includes(id);
        checkbox.addEventListener('change', () => {
          selected[key] = checkbox.checked
            ? [...selected[key], id]
            : selected[key].filter(value => value !== id);
          if (key === 'clubs' && !checkbox.checked) delete selected.clubLogoUrls[id];
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
        const text = document.createElement(teamRow ? 'label' : 'span');
        if(teamRow){checkbox.id='zok-team-'+encodeURIComponent(id);text.htmlFor=checkbox.id;checkbox.setAttribute('aria-label',label)}
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
          if(!window.ZonaOKJugadors?.loaded){
          const name = document.createElement('input');
          name.type = 'text'; name.className = 'zok-favorite-child-name';
          name.maxLength = 32; name.autocomplete = 'given-name';
          name.placeholder = 'Nom del fill o la filla';
          name.setAttribute('aria-label', `Nom personalitzat per a ${label}`);
          name.value = clean(selected.teamNames[id] || '');
          name.addEventListener('input', () => { selected.teamNames[id] = name.value.slice(0, 32); save(); });
          row.append(name);
          }
          const pickerHost=document.createElement('div');pickerHost.className='zok-jp-team-picker';pickerHost.dataset.teamId=id;pickerHost.dataset.teamLabel=label;pickerHost.dataset.originalName=clean(selected.teamNames[id]||'');row.append(pickerHost);
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
      if (key === 'teams' && playerSection) nodes.groups.append(playerSection);
    }
    renderCount();
    window.dispatchEvent(new CustomEvent('zonaok:team-pickers-rendered'));
  }
  async function discoverClubLogos() {
    const safeLogo = value => /^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(String(value||''));
    const clubKey = value => {
      return norm(catalog.clubNameLookup.get(norm(value)) || value);
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
        fetch(`zonaok-classificacions.json?favorits=${Date.now()}`, {cache: 'no-store'}).catch(() => null)
      ]);
      if (!agendaResponse.ok) throw new Error(`Agenda total: ${agendaResponse.status}`);
      const packet = await agendaResponse.json();
      if (packet?.schema !== 'zonaok-all-v1' || packet?.kind !== 'agenda' || !Array.isArray(packet.rows) || !packet.rows.length)
        throw new Error('L’agenda total està buida o té un format incorrecte.');
      let standings = {};
      if (standingsResponse?.ok) {
        try { standings = await standingsResponse.json(); }
        catch (error) { console.warn('Favorits: classificacions no disponibles', error); }
      }
      buildCatalog(packet.rows, standings, packet.clubLogos || {});
      nodes.status.textContent = location.protocol === 'file:'
        ? 'Previsualització local: Safari pot separar les seleccions de Favorits i Inici.'
        : 'Clubs, equips i escuts carregats de l’agenda total FECAPA.';
      discoverClubLogos();
    } catch (error) {
      console.error('Favorits: error carregant catàleg', error);
      nodes.status.textContent = 'No s’ha pogut carregar l’agenda total. Revisa zonaok-tots-agenda.json i torna-ho a provar.';
      const playerSection = document.getElementById('jugadors-favorits');
      nodes.groups.replaceChildren();
      if (playerSection) nodes.groups.append(playerSection);
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
  window.addEventListener('zonaok:jugadors-loaded',render);
  window.addEventListener('zonaok:jugador-equip',e=>{const {teamId,playerId,name}=e.detail||{};if(!selected.teams.includes(teamId))return;if(playerId){selected.playerIds[teamId]=playerId;selected.teamNames[teamId]=String(name).slice(0,80)}else{delete selected.playerIds[teamId];delete selected.teamNames[teamId]}save();render()});
  load();
})();
