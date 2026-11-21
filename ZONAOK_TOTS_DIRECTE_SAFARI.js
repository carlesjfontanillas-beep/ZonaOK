/*
 * ZonaOK TOTS · En directe · V1
 * Drecera Safari: "Executar JavaScript a la pàgina web" => retorna TEXT JSON.
 * Desar el resultat com imports/tots-directe-import.json.
 * Importa TOTS els partits del llistat d'En directe carregat, sense filtre de clubs.
 */
completion((() => {
  try {
    if (!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(location.hostname))
      throw Error('Obre FECAPA a Safari abans de la drecera.');
    const clean = s => String(s??'').replace(/\s+/g,' ').trim();
    const root=document.querySelector('#sidgad-seccion-partidos');
    if (!root || !clean(root.innerText)) throw Error('Obre En directe i espera que es mostrin els partits.');
    const seasonText=document.querySelector('#sidgad-season-selector')?.selectedOptions?.[0]?.textContent || '';
    const match=seasonText.match(/(20\d{2})\s*[\/-]\s*(20\d{2})/);
    if (!match || +match[2]!==+match[1]+1) throw Error('No puc verificar la temporada seleccionada a En directe.');
    const season=`${match[1]}/${match[2]}`;
    const norm=s=>clean(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9]+/g,' ').trim().toUpperCase();
    const text=e=>clean(e?.innerText);
    const logo=side=>{
      const src=side?.querySelector('img')?.getAttribute('src')||'';
      try {
        const u=new URL(src,location.href);
        return u.protocol==='https:' && u.hostname==='sidgad.cloud' &&
          /^\/fecapa\/images\/logos_clubes\/\d+\.png$/i.test(u.pathname) ? u.href : '';
      }catch(_){return '';}
    };
    const idFrom=el=>{
      for (const k of ['idp','partidoId','partitId']) if (/^\d{4,10}$/.test(el.dataset?.[k]||'')) return el.dataset[k];
      for (const a of el.querySelectorAll('a[href]')) {
        const m=(a.getAttribute('href')||'').match(/fecapa_gr_(\d{4,10})_|(?:idp|partido|partit|match)(?:=|\/|_)(\d{4,10})/i);
        if (m) return m[1] || m[2];
      }
      return '';
    };
    const linkMeta=el=>{
      let leagueId='',actaUrl='';
      for(const a of el.querySelectorAll('a[href]')){
        try{
          const u=new URL(a.getAttribute('href'),location.href);
          if(u.protocol!=='https:'||!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname))continue;
          const league=u.searchParams.get('liga');
          if(/^\d{3,10}$/.test(league||''))leagueId=league;
          if(u.searchParams.get('partido')||/acta|fecapa_gr_/i.test(u.pathname))actaUrl=u.href;
        }catch(_){}
      }
      return {leagueId,actaUrl};
    };
    const rows=[], seen=new Set();let examined=0,invalid=0;
    for (const el of root.querySelectorAll('.sidgad-partido-fila')) {
      examined++;
      const h=el.querySelector('.sidgad-local'),a=el.querySelector('.sidgad-visitante');
      const home=text(h?.querySelector('.sidgad-equipo-nombre'));
      const away=text(a?.querySelector('.sidgad-equipo-nombre'));
      const d=text(h?.querySelector('.sidgad-equipo-sub')).match(/^(\d{1,2})\/(\d{1,2})\s+(\d{1,2}):([0-5]\d)$/);
      if (!home||!away||norm(home)===norm(away)||!d||+d[1]>31||+d[2]>12||+d[3]>23) {invalid++;continue;}
      const year=+d[2]>=7?match[1]:match[2];
      const iso=`${year}-${d[2].padStart(2,'0')}-${d[1].padStart(2,'0')}`;
      const parsed=new Date(iso+'T12:00:00Z');
      if (Number.isNaN(+parsed)||parsed.toISOString().slice(0,10)!==iso) {invalid++;continue;}
      const time=`${d[3].padStart(2,'0')}:${d[4]}`;
      const header=el.closest('.sidgad-liga-grupo')?.querySelector('.sidgad-liga-header-separador');
      const competition=clean([...header?.childNodes||[]].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ')) || text(header);
      const rawScore=text(el.querySelector('.sidgad-resultado-texto'));
      const score=rawScore.match(/^(\d{1,3})\s*[-–:]\s*(\d{1,3})$/);
      const row={iso,time,competition,home,away,
        homeScore:score?+score[1]:null,awayScore:score?+score[2]:null,
        homeLogo:logo(h),awayLogo:logo(a),matchId:idFrom(el),...linkMeta(el),venue:'',
        round:text(a?.querySelector('.sidgad-equipo-sub')),
        status:text(el.querySelector('.sidgad-status-tag'))};
      const k=[iso,time,norm(competition),norm(home),norm(away)].join('|');
      if(!seen.has(k)){seen.add(k);rows.push(row);}
    }
    if(!rows.length) throw Error('No hi ha partits vàlids carregats a En directe.');
    rows.sort((a,b)=>(a.iso+a.time).localeCompare(b.iso+b.time));
    return JSON.stringify({schema:'zonaok-all-v1',kind:'directe',season,source:'FECAPA-SAFARI',
      capturedAt:new Date().toISOString(),sourceUrl:location.href,
      counts:{examined,invalid,exported:rows.length},rows});
  }catch(error){return 'ERROR ZONAOK DIRECTE TOTS: '+(error?.message||String(error));}
})());
