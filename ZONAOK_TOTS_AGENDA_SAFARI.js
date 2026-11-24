/*
 * ZonaOK TOTS · Agenda · V2 (escuts PNG i GIF)
 * Drecera Safari: "Executar JavaScript a la pàgina web" => retorna TEXT JSON.
 * La drecera ha de DESAR el resultat com imports/tots-agenda-import.json.
 * Llegeix només el DOM carregat de https://www.hoqueipatins.fecapa.cat/ag/
 * IMPORTANT: seleccionar TOTS els clubs i el període desitjat abans d'executar.
 */
completion((() => {
  try {
    if (!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(location.hostname) ||
        !/^\/ag(?:\/|$)/.test(location.pathname)) {
      throw Error('Obre FECAPA /ag/ i selecciona TOTS els clubs i el període abans de la drecera.');
    }
    const clean = v => String(v ?? '').replace(/\s+/g, ' ').trim();
    const norm = v => clean(v).normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^A-Za-z0-9]+/g, ' ').trim().toUpperCase();
    const nowParts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
      timeZone:'Europe/Madrid', year:'numeric', month:'2-digit', day:'2-digit'
    }).formatToParts(new Date()).filter(p => p.type !== 'literal').map(p => [p.type,p.value]));
    const seasonYear = +nowParts.month >= 7 ? +nowParts.year : +nowParts.year - 1;
    const season = `${seasonYear}/${seasonYear+1}`;
    const firstDay = `${seasonYear}-07-01`, lastDay = `${seasonYear+1}-06-30`;
    const validISO = s => {
      if (!/^20\d{2}-\d{2}-\d{2}$/.test(s)) return '';
      const d = new Date(s + 'T12:00:00Z');
      return !Number.isNaN(+d) && d.toISOString().slice(0,10) === s ? s : '';
    };
    const dateValue = input => {
      const s = clean(input); let m;
      if ((m = s.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/))) return validISO(m[0]);
      if ((m = s.match(/\b(\d{1,2})[\/. -](\d{1,2})[\/. -](20\d{2})\b/)))
        return validISO(`${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`);
      if ((m = s.match(/\b(\d{1,2})[\/. -](\d{1,2})\b/))) {
        const opts = [seasonYear,seasonYear+1].map(y => validISO(`${y}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`));
        return opts.find(x => x && x>=firstDay && x<=lastDay) || '';
      }
      return '';
    };
    const timeValue = s => {
      const m = clean(s).match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);
      return m ? `${m[1].padStart(2,'0')}:${m[2]}` : '';
    };
    const scoreValue = s => {
      const m = clean(s).match(/(?:^|\s)(\d{1,3})\s*[-–:]\s*(\d{1,3})(?:\s|$)/);
      return m ? [+m[1],+m[2]] : [null,null];
    };
    const matchId = tr => {
      const attrs = [tr.dataset.idp,tr.dataset.partidoId,tr.dataset.partitId].filter(Boolean);
      for (const x of attrs) if (/^\d{4,10}$/.test(String(x))) return String(x);
      for (const a of tr.querySelectorAll('a[href]')) {
        const u = a.getAttribute('href') || '';
        const m = u.match(/fecapa_gr_(\d{4,10})_|(?:idp|partido|partit|match)(?:=|\/|_)(\d{4,10})/i);
        if (m) return m[1] || m[2];
      }
      return '';
    };
    const linkMeta = tr => {
      let leagueId='', actaUrl='';
      for (const a of tr.querySelectorAll('a[href]')) {
        try {
          const u=new URL(a.getAttribute('href'),location.href);
          if (!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname) || u.protocol!=='https:') continue;
          const league=u.searchParams.get('liga');
          if (/^\d{3,10}$/.test(league||'')) leagueId=league;
          if (u.searchParams.get('partido') || /acta|fecapa_gr_/i.test(u.pathname)) actaUrl=u.href;
        }catch(_){}
      }
      return {leagueId,actaUrl};
    };
    const logo = cell => {
      const src = cell?.querySelector('img[src]')?.getAttribute('src') || '';
      try {
        const u = new URL(src,location.href);
        return u.protocol==='https:' && u.hostname==='sidgad.cloud' &&
          /^\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(u.pathname) ? u.href : '';
      } catch (_) {return '';}
    };
    const clubLogos = Object.create(null);
    const addClubLogo = (name, src) => {
      const label = clean(name);
      if (!label || !src) return;
      try {
        const u = new URL(src, location.href);
        if (u.protocol !== 'https:' || u.hostname !== 'sidgad.cloud' ||
            !/^\/fecapa\/images\/logos_clubes\/\d+(?:_\d+)?\.(?:png|gif)$/i.test(u.pathname)) return;
        clubLogos[label] = u.href;
      } catch (_) {}
    };
    // FECAPA associa explícitament l'escut amb el club a través de l'alt/title
    // de les imatges logos_clubes. Conservem aquesta relació al mateix export.
    for (const img of document.querySelectorAll('img[src]')) {
      addClubLogo(img.getAttribute('alt') || img.getAttribute('title'), img.getAttribute('src'));
    }
    const all = new Map(); let inspected=0,invalid=0,recognizedTables=0;
    const tables = [...document.querySelectorAll('table')];
    for (const table of tables) {
      const trs = [...table.querySelectorAll('tr')];
      const headerRow = table.querySelector('thead tr') || trs.find(tr => tr.querySelector('th'));
      if (!headerRow) continue;
      const headers = [...headerRow.querySelectorAll('th,td')].map(c=>norm(c.innerText));
      const find = re => headers.findIndex(v=>re.test(v));
      const dateIdx=find(/^(DATA|DIA|DATE|FECHA)/), timeIdx=find(/^(HORA|HOUR)/);
      const homeIdx=find(/(^| )(EQUIP LOCAL|EQUIPO LOCAL|LOCAL|CASA|HOME)( |$)/);
      const awayIdx=find(/VISITANT|VISITANTE|VISITOR|AWAY/);
      const scoreIdx=find(/RESULT|MARCADOR|SCORE/);
      const venueIdx=find(/PISTA|PAVELL|INSTAL|LLOC|SEU|PABELL/);
      const compIdx=find(/COMPET|CATEG|LLIGA|LIGA/);
      if (homeIdx<0 || awayIdx<0) continue; // Mai inventar equips des de columnes arbitràries.
      recognizedTables++;
      const heading=clean(table.closest('.sidgad-liga-grupo, section')?.querySelector('h2,h3,.sidgad-liga-header-separador')?.textContent || table.caption?.textContent || '');
      const start=trs.indexOf(headerRow)+1;
      for (const tr of trs.slice(start)) {
        const cells=[...tr.querySelectorAll(':scope > th, :scope > td')];
        if (!cells.length) continue;
        inspected++;
        const vals=cells.map(c=>clean(c.innerText));
        const home=vals[homeIdx]||'', away=vals[awayIdx]||'';
        if (!home || !away || norm(home)===norm(away)) {invalid++; continue;}
        const iso=dateValue(dateIdx>=0 ? vals[dateIdx] : vals.join(' ')) || dateValue(vals.join(' '));
        const time=timeValue(timeIdx>=0 ? vals[timeIdx] : vals.join(' ')) || timeValue(vals.join(' '));
        if (!iso || !time || iso<firstDay || iso>lastDay) {invalid++;continue;}
        const score=scoreIdx>=0 ? scoreValue(vals[scoreIdx]) : scoreValue(tr.querySelector('.sidgad-resultado-texto')?.textContent||'');
        const row={iso,time,competition:compIdx>=0 ? vals[compIdx] : heading,
          home,away,homeScore:score[0],awayScore:score[1],
          venue:venueIdx>=0 ? vals[venueIdx] : '',
          homeLogo:logo(cells[homeIdx]),awayLogo:logo(cells[awayIdx]),
          matchId:matchId(tr),...linkMeta(tr),status:''};
        addClubLogo(home, row.homeLogo);
        addClubLogo(away, row.awayLogo);
        const key=[iso,time,norm(row.competition),norm(home),norm(away)].join('|');
        const old=all.get(key);
        if (!old || (row.matchId&&!old.matchId) || (row.homeScore!==null&&old.homeScore===null)) all.set(key,row);
      }
    }
    if (!tables.length) throw Error('Cap taula a /ag/. Espera que acabin de carregar les dades.');
    if (!recognizedTables) throw Error('No s’han reconegut les columnes Local/Visitant. No s’ha generat un JSON incomplet.');
    if (!all.size) throw Error('Cap partit vàlid carregat. Revisa dates, filtres i taules de FECAPA.');
    const rows=[...all.values()].sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time));
    return JSON.stringify({schema:'zonaok-all-v1',kind:'agenda',season,source:'FECAPA-SAFARI',
      capturedAt:new Date().toISOString(),sourceUrl:location.href,
      counts:{tables:tables.length,recognizedTables,inspected,invalid,exported:rows.length},clubLogos,rows});
  } catch (error) {
    // Prefix inequívoc: una drecera no ha de desar un error com si fos JSON.
    return 'ERROR ZONAOK AGENDA TOTS: ' + (error?.message || String(error));
  }
})());
