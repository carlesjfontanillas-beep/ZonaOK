/*
 * ZonaOK — Resultats dels darrers 7 dies · V8 · NOMS COMPLETS DELS CLUBS + TARGETES COMPACTES + ACTES TOTAL (24/11/2026)
 * Instal·lació: <script defer src="zonaok-resultats-7dies.js?v=20261124-club-names-r8"></script>
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
  const baseClubName = name => String(name || '').trim().replace(/\s+[A-D]$/i, '').trim();
  // Les sigles de resultats es poden mostrar amb el nom complet d'Agenda quan
  // una altra fila del mateix paquet n'aporta una equivalència inequívoca.
  let teamAliases = new Map();
  let rowTeamAliases = new WeakMap();
  const aliasCandidates = name => {
    const variants = [String(name || '').trim(), baseClubName(name)];
    const candidates = [];
    for (const variant of new Set(variants)) {
      const words = norm(variant).split(' ').filter(Boolean);
      if (words.length < 2) continue;
      const last = words[words.length - 1];
      candidates.push(words.map(word => word[0]).join(''));
      if (last.length >= 2 && last.length <= 5) {
        candidates.push(words.slice(0, -1).map(word => word[0]).join('') + last);
        candidates.push(last);
      }
    }
    return [...new Set(candidates)].filter(value => value.length >= 2 && value.length <= 6);
  };
  const aliasCompatible = (a, b) => {
    if (norm(a) === norm(b)) return true;
    const aa = norm(a).replace(/ /g, ''), bb = norm(b).replace(/ /g, '');
    if (aa.length <= 6 && bb.length > 6) return aliasCandidates(b).includes(aa);
    if (bb.length <= 6 && aa.length > 6) return aliasCandidates(a).includes(bb);
    return false;
  };
  const setTeamAliases = (rows, references = []) => {
    const candidates = new Map();
    const sources = [...rows, ...references], bySlot = new Map();
    const slot = r => r.iso+'|'+String(r.time||'').padStart(5,'0');
    for(const r of sources){if(!r?.iso||!r?.time)continue;const k=slot(r);if(!bySlot.has(k))bySlot.set(k,[]);bySlot.get(k).push(r)}
    rowTeamAliases = new WeakMap();
    for (const row of rows) {
      if (!row?.iso || !row?.time) continue;
      const perRow = {};
      for (const other of (bySlot.get(slot(row))||[])) {
        if (other === row || other.iso !== row.iso || String(other.time || '').padStart(5, '0') !== String(row.time || '').padStart(5, '0') ||
            !aliasCompatible(row.home, other.home) || !aliasCompatible(row.away, other.away)) continue;
        for (const side of ['home', 'away']) {
          const short = String(row[side] || '');
          const full = String(other[side] || '').trim();
          const shortKey = norm(short).replace(/ /g, '');
          if (shortKey.length > 6 || norm(full).replace(/ /g, '').length <= 6) continue;
          if (!perRow[side]) perRow[side] = new Set();
          perRow[side].add(full);
          if (!candidates.has(shortKey)) candidates.set(shortKey, new Set());
          candidates.get(shortKey).add(full);
        }
      }
      rowTeamAliases.set(row, perRow);
    }
    teamAliases = new Map([...candidates].filter(([, values]) => values.size === 1)
      .map(([alias, values]) => [alias, [...values][0]]));
  };
  // El nom del partit conserva el sufix oficial; només els filtres el treuen.
  const displayTeamName = (name, row, side) => {
    const full = String(name || '').trim();
    const stateName = window.ZonaOKStateTeamName?.(full, row, side);
    if (stateName !== undefined && stateName !== null) return stateName;
    const key = norm(full).replace(/ /g, '');
    const contextual = row && rowTeamAliases.get(row)?.[side];
    if (contextual?.size === 1) return [...contextual][0];
    return teamAliases.get(key) || full;
  };
  const teamKey = (name, logo, row, side) => {
    const known = clubOf(name);
    if (known) return known;
    const base = norm(baseClubName(displayTeamName(name, row, side)));
    if (base) return 'team:' + base;
    const match = String(logo || '').match(/^https:\/\/sidgad\.cloud\/fecapa\/images\/logos_clubes\/(\d+)\.png$/);
    return match ? 'logo:' + match[1] : 'team:' + norm(name);
  };
  const teamLabel = (name, key, row, side) => {
    if (key === 'barca') return 'Barça';
    if (key === 'celoni') return 'CP Sant Celoni';
    return baseClubName(displayTeamName(name, row, side));
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
  const competitionGroup = text => String(text || 'Categoria no informada').trim().replace(/\s+/g, ' ')
    .replace(/\b(OR|PLATA|BRONZE)\s+\d+\b/gi, '$1')
    .replace(/\s+(?:GRUP|GRUPO)\s+[A-Z0-9]+\b/gi, '').trim();
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

  let matches = [], periodRows = {past:[],upcoming:[]}, activePeriod = 'past', periodLoaded = false;
  let publishedAt = '', pendingLoad = null, periodTitle, periodNote, pastButton, upcomingButton;
  let panel, navButton, clubFilter, categoryFilter, competitionFilter, content, counter, status;

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
      return dt >= lower && dt <= upper &&
        !/EN JOC|EN DIRECTE|PLAYING|LIVE|IN PROGRESS/i.test(String(r.status || ''));
    }).sort((a, b) => rowDateKey(b).localeCompare(rowDateKey(a)) ||
      norm(a.competition).localeCompare(norm(b.competition), 'ca'));
  }

  // Dues finestres mòbils de set dies, amb el rellotge de Madrid.
  function rowsInPeriod(rows, period, now = new Date()) {
    const current = madridTimeKey(now);
    const localShift = days => {
      // Desplaçament de dates civils: manté l'hora local també en canvi CET/CEST.
      const d = new Date(current + ':00Z');
      d.setUTCDate(d.getUTCDate() + days);
      return d.toISOString().slice(0,16);
    };
    const upcoming = period === 'upcoming', edge = localShift(upcoming ? 7 : -7);
    return rows.filter(r => r && /^20\d\d-\d\d-\d\d$/.test(String(r.iso)) &&
      /^\d{2}:\d{2}$/.test(String(r.time)) && r.home && r.away &&
      (upcoming ? rowDateKey(r) > current && rowDateKey(r) <= edge &&
        !/AJORNAT|APLAZADO|CANCEL|SUSPES|SUSPÈS|SUSPENDIDO/i.test(String(r.status || '')) :
        rowDateKey(r) >= edge && rowDateKey(r) <= current &&
        !/EN JOC|EN DIRECTE|LIVE|IN PROGRESS|PLAYING|DESCANS|PRIMERA PART|SEGONA PART/i.test(String(r.status || ''))))
      .sort((a,b) => (upcoming ? rowDateKey(a).localeCompare(rowDateKey(b)) : rowDateKey(b).localeCompare(rowDateKey(a))) ||
        norm(a.competition).localeCompare(norm(b.competition),'ca'));
  }

  function selectPeriod(period) {
    activePeriod = period === 'upcoming' ? 'upcoming' : 'past';
    const future = activePeriod === 'upcoming';
    pastButton.setAttribute('aria-pressed',String(!future));
    upcomingButton.setAttribute('aria-pressed',String(future));
    periodTitle.textContent = future ? 'Pròxims partits' : 'Partits recents';
    periodNote.textContent = future ? 'Pròxims 7 dies · Més propers primer' : 'Darrers 7 dies · Més recents primer';
    if(!periodLoaded)return;
    matches = periodRows[activePeriod];
    updateClubOptions();
    updateCategoryOptions();
    updateCompetitionOptions();
    renderCards();
  }

  async function loadData() {
    const response = await fetch('zonaok-tots-agenda.json', {cache:'no-cache'});
    if (!response.ok) throw new Error('No s’ha pogut carregar l’agenda total.');
    const packet = await response.json();
    if (packet?.schema !== 'zonaok-all-v1' || packet?.kind !== 'agenda' || !Array.isArray(packet.rows) || !packet.rows.length)
      throw new Error('L’agenda total és buida o no té el format esperat.');
    publishedAt = packet.capturedAt || packet.publishedAt || '';
    return {__all:true, rows:packet.rows, agendaRows:packet.rows};
  }

  // Enllaços d'acta independents de l'Agenda. No modifiquen marcadors ni filtres.
  async function enrichActes(rows) {
    let data;
    try {
      const response = await fetch('zonaok-tots-actes.json', {cache:'no-cache'});
      if (!response.ok) return rows;
      data = await response.json();
    } catch (_) { return rows; }
    if (data?.schema !== 'zonaok-actes-total-v1' || data?.kind !== 'actes-total' || !Array.isArray(data.rows)) return rows;
    const linked = new Map();
    const ambiguous = new Set();
    for (const f of data.rows) {
      if (!f || typeof f.key !== 'string' || !/^\d{3,10}$/.test(String(f.leagueId || '')) ||
          !/^\d{4,10}$/.test(String(f.matchId || ''))) continue;
      try {
        const u = new URL(String(f.actaUrl || ''));
        if (u.protocol !== 'https:' || !['www.hoqueipatins.fecapa.cat','hoqueipatins.fecapa.cat'].includes(u.hostname) ||
            u.searchParams.get('liga') !== String(f.leagueId) || u.searchParams.get('partido') !== String(f.matchId)) continue;
      } catch (_) { continue; }
      if (linked.has(f.key) && linked.get(f.key).matchId !== String(f.matchId)) ambiguous.add(f.key);
      else linked.set(f.key, f);
    }
    return rows.map(row => {
      const k = key(row), f = linked.get(k);
      if (!f || ambiguous.has(k) || (row.matchId && String(row.matchId) !== String(f.matchId)) ||
          (row.leagueId && String(row.leagueId) !== String(f.leagueId)) ||
          (row.actaUrl && row.actaUrl !== f.actaUrl)) return row;
      return {...row, matchId: String(f.matchId), id: row.id || String(f.matchId),
        leagueId: row.leagueId || String(f.leagueId), actaUrl: f.actaUrl};
    });
  }

  function buildTeam(name, importedLogo, row, side) {
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
    team.append(crest, make('strong', '', displayTeamName(name, row, side)));
    return team;
  }

  function buildCard(row) {
    const card = make('article', 'match gray');
    card.classList.add('zok-recent-card');
    window.ZonaOKApplyFavoriteCardColor?.(card,row);

    // Disseny compacte de la versió facilitada: només dues línies per partit.
    // Capçalera: categoria, hora, data i Acta (sense pista ni «Marcador Agenda»).
    const top = make('div', 'match-top');
    const category = make('span', 'pill', row.competition || 'Categoria no informada');
    category.title = row.competition || 'Categoria no informada';
    const time = make('strong', 'zok-recent-time', row.time);
    const date = make('small', 'zok-recent-day', prettyDate(row.iso));
    top.append(category, time, date);
    const actaUrl=window.ZonaOKActaLinks.savedUrl(row)||window.ZonaOKActes?.url(row,row.leagueId||'live')||'';
    if(actaUrl){
      const acta=make('button','zok-recent-acta','Acta');
      acta.type='button';
      acta.setAttribute('aria-label','Veure la fitxa i l’acta del partit');
      acta.onclick=()=>window.ZonaOKActaFitxa.open(row,actaUrl);
      top.append(acta);
    }

    // Segona línia: escuts (inclosos els clubs nous), equips i marcador.
    const teams = make('div', 'teams');
    const center = make('div', 'middle');
    const score = activePeriod !== 'upcoming' && validResult(row) ? `${Number(row.homeScore)} : ${Number(row.awayScore)}` : '– : –';
    center.append(make('strong', 'score', score));
    teams.append(buildTeam(row.home, row.homeLogo, row, 'home'), center, buildTeam(row.away, row.awayLogo, row, 'away'));
    card.append(top, teams);
    return card;
  }

  function updateClubOptions() {
    const clubs = new Map();
    for (const r of matches) for (const [name, logo] of [[r.home,r.homeLogo],[r.away,r.awayLogo]]) {
      const k=teamKey(name,logo,r,name===r.home?'home':'away');
      const label = teamLabel(name,k,r,name===r.home?'home':'away');
      const isUnresolvedCode = /^[A-Z0-9]{2,6}$/.test(norm(label)) && !clubOf(label);
      if (!isUnresolvedCode && !clubs.has(k)) clubs.set(k,label);
    }
    const options = [...clubs.entries()].sort((a,b)=>a[1].localeCompare(b[1],'ca',{sensitivity:'base'})).map(([,label])=>label);
    setSuggestions(clubFilter, options);
  }

  function mountSuggestions(input) {
    const wrap=make('div','zok-suggest-wrap'),menu=make('div','zok-suggestions');
    menu.setAttribute('role','listbox'); input.removeAttribute('list'); input.parentNode.insertBefore(wrap,input); wrap.append(input,menu); input._zokOptions=[];
    const draw=()=>{const q=input.value,values=input._zokOptions.filter(v=>!q||norm(v).includes(norm(q))).slice(0,40);menu.replaceChildren(...values.map(value=>{const b=make('button','',value);b.type='button';b.setAttribute('role','option');b.addEventListener('mousedown',e=>e.preventDefault());b.addEventListener('click',()=>{input.value=value;menu.classList.remove('open');input.dispatchEvent(new Event('input',{bubbles:true}));input.focus()});return b}));menu.classList.toggle('open',document.activeElement===input&&values.length>0)};
    input.addEventListener('focus',draw);input.addEventListener('input',draw);input.addEventListener('keydown',e=>{if(e.key==='Escape')menu.classList.remove('open')});input.addEventListener('blur',()=>setTimeout(()=>menu.classList.remove('open'),130));input._zokDraw=draw;
  }
  function setSuggestions(input, values) { input._zokOptions=[...new Set(values)]; input._zokDraw?.(); }
  const queryMatches = (value, query) => !query || norm(value).includes(norm(query));

  function updateCategoryOptions() {
    const chosen = categoryFilter.value;
    const selectedClub = clubFilter.value;
    const selectedCompetition = competitionFilter.value;
    const categories = [...new Set(matches.filter(r => (!selectedClub ||
      queryMatches(teamLabel(r.home,teamKey(r.home,r.homeLogo,r,'home'),r,'home'),selectedClub) ||
      queryMatches(teamLabel(r.away,teamKey(r.away,r.awayLogo,r,'away'),r,'away'),selectedClub)) &&
      queryMatches(competitionGroup(r.competition),selectedCompetition))
      .map(r => String(r.competition || 'Categoria no informada')))]
      .sort((a, b) => a.localeCompare(b, 'ca', {sensitivity: 'base'}));
    setSuggestions(categoryFilter, categories);
    categoryFilter.value = chosen;
  }

  function updateCompetitionOptions() {
    const selectedClub = clubFilter.value;
    const competitions = [...new Map(matches.filter(r => (!selectedClub ||
      queryMatches(teamLabel(r.home,teamKey(r.home,r.homeLogo),r,'home'),selectedClub) ||
      queryMatches(teamLabel(r.away,teamKey(r.away,r.awayLogo),r,'away'),selectedClub)) &&
      (queryMatches(r.competition,categoryFilter.value)))
      .map(r => {const label=competitionGroup(r.competition);return [norm(label),label];})).values()]
      .sort((a,b)=>a.localeCompare(b,'ca',{sensitivity:'base'}));
    setSuggestions(competitionFilter, competitions);
  }

  function renderCards() {
    const club = clubFilter.value, category = categoryFilter.value, competition=competitionFilter.value;
    const selected = matches.filter(r =>
      (!club || queryMatches(teamLabel(r.home,teamKey(r.home,r.homeLogo),r,'home'),club) || queryMatches(teamLabel(r.away,teamKey(r.away,r.awayLogo),r,'away'),club)) &&
      queryMatches(r.competition, category) &&
      queryMatches(competitionGroup(r.competition),competition));
    counter.textContent = `${selected.length} ${selected.length === 1 ? 'partit' : 'partits'}`;
    content.replaceChildren();
    if (!selected.length) {
      const period = activePeriod === 'upcoming' ? 'els pròxims 7 dies' : 'els darrers 7 dies';
      content.append(make('div', 'empty', matches.length ?
        'No hi ha partits amb aquests filtres durant '+period+'.' :
        'No hi ha partits a l’Agenda durant '+period+'.'));
    } else for (const row of selected) content.append(buildCard(row));
    if (publishedAt) {
      try {
        const stamp = new Intl.DateTimeFormat('ca-ES', {
          timeZone: 'Europe/Madrid', dateStyle: 'short', timeStyle: 'short'
        }).format(new Date(publishedAt));
        status.textContent = `Actualització: ${stamp}`;
      } catch (_) { status.textContent = 'Actualització no disponible'; }
    }
  }

  async function openResults(preserve=false) {
    document.body.classList.add('zok-recent-mode');
    panel.hidden = false;
    if(!preserve)selectPeriod('past'); // Sempre obrir els darrers set dies en entrar al menú.
    document.querySelectorAll('.bottom .navbtn').forEach(button =>
      button.classList.toggle('active', button === navButton));
    if(!preserve)panel.scrollIntoView({block: 'start', behavior: 'auto'});
    if(pendingLoad)return pendingLoad;
    status.textContent = 'Carregant dades de GitHub…';
    pendingLoad=(async()=>{
      try {
        const data = await loadData();
        const now=new Date(),past=rowsInPeriod(data.rows,'past',now),upcoming=rowsInPeriod(data.rows,'upcoming',now);
        const combined=await enrichActes([...past,...upcoming]);
        periodRows={past:combined.slice(0,past.length),upcoming:combined.slice(past.length)};
        setTeamAliases(combined, data.agendaRows || []);
        periodLoaded=true;
        selectPeriod(activePeriod);
        return true;
      } catch (error) {
        if(!periodLoaded){matches=[];content.replaceChildren(make('div','empty',error.message||'No s’han pogut carregar els partits.'));counter.textContent='0 partits'}
        status.textContent = periodLoaded?'No s’han pogut actualitzar els JSON · Dades anteriors conservades':'No s’han pogut llegir els JSON publicats';
        return false;
      } finally {pendingLoad=null}
    })();
    return pendingLoad;
  }

  function install() {
    const grid = document.querySelector('.zok-nav-fixed') || document.querySelector('.bottom .navgrid');
    const bottomNav = document.querySelector('.zok-bottom-nav') || grid;
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
      #${ID} .zok-recent-filters input{width:100%;min-width:0;padding:12px 8px;border:1px solid #7597b0;border-radius:11px;background:#183d5b;color:#fff;font:inherit;font-size:12px}
      #${ID} .zok-suggest-wrap{position:relative;min-width:0}
      #${ID} .zok-suggestions{display:none;position:absolute;z-index:30;top:calc(100% + 4px);left:0;right:0;max-height:220px;overflow:auto;padding:4px;border:1px solid #7597b0;border-radius:10px;background:#183d5b;box-shadow:0 8px 24px #001522aa}
      #${ID} .zok-suggestions.open{display:grid}
      #${ID} .zok-suggestions button{padding:9px 10px;border:0;border-radius:7px;background:transparent;color:#fff;text-align:left;font:inherit;font-size:12px;cursor:pointer}
      #${ID} .zok-suggestions button:hover,#${ID} .zok-suggestions button:focus{background:#2869c7;outline:0}
      #${ID} .zok-recent-period{font-size:12px;color:#b3cee1;margin:7px 0 14px}
      #${ID} .zok-period-tabs{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:8px 0 10px}
      #${ID} .zok-period-tabs button{min-width:0;min-height:37px;padding:8px 4px;border:1px solid #719cba88;border-radius:11px;background:#173b55;color:#edf6ff;font:inherit;font-size:13px;font-weight:750;cursor:pointer}
      #${ID} .zok-period-tabs button[aria-pressed=true]{background:#fbc252;border-color:#fbc252;color:#10283c}
      #${ID} .zok-period-tabs button:focus-visible{outline:2px solid #fff;outline-offset:2px}
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
      #${ID} .zok-recent-stamp{font-size:11px;color:#b6d2e5;margin:0 0 10px;line-height:1.35}
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
    const toolbarStyle=make('style');toolbarStyle.textContent="\n.bottom.zok-bottom-nav{display:flex!important;align-items:stretch!important;gap:7px!important}\n.zok-nav-scroll{flex:1 1 auto!important;min-width:0!important;overflow-x:auto!important;overflow-y:hidden!important;-webkit-overflow-scrolling:touch!important;scrollbar-width:none!important}\n.zok-nav-scroll .navgrid{display:flex!important;grid-template-columns:none!important;gap:6px!important;width:max-content!important;min-width:100%!important}\n.zok-nav-scroll .navbtn{flex:0 0 62px!important;width:62px!important;min-width:62px!important}\n.zok-nav-fixed{flex:0 0 auto!important;display:flex!important;gap:5px!important}\n.zok-nav-fixed .navbtn{flex:0 0 62px!important;width:62px!important;min-width:62px!important}\n.zok-nav-divider{width:1px!important;flex:0 0 1px!important;align-self:stretch!important;background:#9dbbd044!important;margin:0 1px!important}\n.bottom.zok-bottom-nav .navbtn strong{font-size:9px!important;line-height:1.08!important;white-space:normal!important;overflow-wrap:anywhere!important}\n.bottom.zok-bottom-nav .navbtn small{display:none!important}\n@media(max-width:430px){.bottom.zok-bottom-nav{gap:5px!important}.zok-nav-scroll .navgrid{gap:4px!important}.zok-nav-scroll .navbtn,.zok-nav-fixed .navbtn{flex-basis:54px!important;width:54px!important;min-width:54px!important}.bottom.zok-bottom-nav .navbtn strong{font-size:8px!important}}\n";document.head.append(toolbarStyle);

    navButton = make('button', 'navbtn');
    navButton.type = 'button';
    navButton.id = NAV_ID;
    navButton.setAttribute('aria-label', 'Resultats dels darrers set dies');
    navButton.append(make('span', '', '🏁'), make('strong', '', 'Resultats'), make('small', '', 'Últims 7 dies'));
    grid.append(navButton);

    panel = make('section', 'section');
    panel.id = ID;
    panel.hidden = true;
    const header = make('div', 'section-head');
    const left = make('div');
    periodTitle=make('h2','','Partits recents');
    left.append(make('span', 'overline', 'AGENDA · MARCADORS'), periodTitle);
    counter = make('span', 'section-tag', '0 partits');
    header.append(left, counter);
    const filterRow = make('div', 'zok-recent-filters');
    const clubLabel = make('label', '', 'Club');
    clubFilter = make('input');
    clubFilter.type = 'search'; clubFilter.placeholder = 'Tots els clubs'; clubFilter.setAttribute('list','zok-results-clubs');
    clubFilter.setAttribute('aria-label', 'Filtra els resultats per club');
    clubLabel.append(clubFilter); mountSuggestions(clubFilter);
    const categoryLabel = make('label', '', 'Categoria');
    categoryFilter = make('input');
    categoryFilter.type='search'; categoryFilter.placeholder='Totes les categories'; categoryFilter.setAttribute('list','zok-results-categories');
    categoryFilter.setAttribute('aria-label', 'Filtra els resultats per categoria');
    categoryLabel.append(categoryFilter); mountSuggestions(categoryFilter);
    const competitionLabel = make('label', '', 'Competició');
    competitionFilter = make('input');
    competitionFilter.type='search'; competitionFilter.placeholder='Totes les competicions'; competitionFilter.setAttribute('list','zok-results-competitions');
    competitionFilter.setAttribute('aria-label', 'Filtra els resultats per competició');
    competitionLabel.append(competitionFilter); mountSuggestions(competitionFilter);
    filterRow.append(clubLabel, categoryLabel, competitionLabel);
    content = make('div', 'cards');
    status = make('p', 'zok-recent-stamp', '');
    const tabs=make('div','zok-period-tabs zok-scope-switch');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Període dels partits');
    pastButton=make('button','','Darrers 7 dies');upcomingButton=make('button','','Pròximament');
    for(const button of [pastButton,upcomingButton])button.type='button';
    pastButton.onclick=()=>selectPeriod('past');upcomingButton.onclick=()=>selectPeriod('upcoming');
    tabs.append(pastButton,upcomingButton);
    periodNote=make('p','zok-recent-period');
    panel.append(header,tabs,filterRow,periodNote,status,content);
    selectPeriod('past');
    const footer = main.querySelector('.footer');
    main.insertBefore(panel, footer || null);

    // El botó nou no té data-tab: no interfereix amb el selectSection d'app.js.
    window.ZonaOKRefreshRecent=()=>openResults(true);
    navButton.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      void openResults();
    });
    bottomNav.addEventListener('click', event => {
      const other = event.target.closest('.navbtn');
      if (other && other !== navButton) {
        document.body.classList.remove('zok-recent-mode');
        panel.hidden = true;
      }
    }, true);
    clubFilter.addEventListener('input', () => { updateCompetitionOptions(); updateCategoryOptions(); renderCards(); });
    categoryFilter.addEventListener('input', () => { updateCompetitionOptions(); renderCards(); });
    competitionFilter.addEventListener('input', () => { updateCategoryOptions(); renderCards(); });
  }

  if(typeof module!=='undefined'&&module.exports){module.exports={rowsInPeriod};return}
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once: true});
  else install();
})();
