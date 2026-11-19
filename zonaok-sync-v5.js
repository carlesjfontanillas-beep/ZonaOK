/* ZonaOK V6 \u2014 Agenda com a font de partits, En directe nomes com a font de marcadors.
/* ZonaOK V10.5 \u2014 Agenda com a font de partits, En directe nomes com a font de marcadors.
  Carregar ABANS d'app.js. Conserva V2 (classificacions) i les dades existents.
  No consulta FECAPA des del web: les dues dreceres Safari llegeixen el DOM.
*/
@@ -278,52 +278,113 @@
root.replaceChildren(frag);if($('#home-count'))$('#home-count').textContent=count+' partits';
}
function activeTab(){const button=$('.navbtn.active');return button?.dataset.tab||($('#results-section')?.classList.contains('hide')?'home':'');}
  function drawList(tab,rows){
    const root=$('#results-list');if(!root||$('#results-section')?.classList.contains('hide'))return;
  // V10.5: les consultes de club i de Magi/Ton sempre son de TEMPORADA.
  // La pantalla Inici es l'unic lloc on apliquem el filtre setmanal.
  function drawList(tab,rows,store){
    const root=$('#results-list');
    if(!root||$('#results-section')?.classList.contains('hide'))return;
if(tab==='classificacions'||!['barca','celoni','grupalevi','grupinfantil'].includes(tab))return;

const seasonId=tab==='grupalevi'?'4789':tab==='grupinfantil'?'4786':'';
    const seasonRows=seasonId?(read().seasons?.[seasonId]?.rows||[]):[];
    let selected=seasonRows.length?seasonRows.map(r=>resolved(r,read())):tab==='barca'?rows.filter(r=>isBarca(r.home)||isBarca(r.away)):
      tab==='celoni'?rows.filter(r=>isCeloni(r.home)||isCeloni(r.away)):
      tab==='grupalevi'?rows.filter(r=>norm(r.competition)==='ALEVI OR 3'&&(isBarca(r.home)||isBarca(r.away))):
      rows.filter(r=>norm(r.competition)==='INFANTIL OR 10'&&(isCeloni(r.home)||isCeloni(r.away)));
    if(tab.startsWith('grup'))selected=[...selected].reverse();
    const sig=tab+'|'+JSON.stringify(selected.map(r=>[rowKey(r),r.homeScore,r.awayScore]));
    const seasons=store.seasons||{};
    const seasonItem=seasonId?(seasons[seasonId]||{}):{};
    const wanted=String(store.agenda?.season||seasonItem.season||'');
    const dates=wanted.match(/(20\d{2})\D+(20\d{2})/);
    const current=Number(monday().slice(0,4))-(Number(monday().slice(5,7))<7?1:0);
    const y=dates?Number(dates[1]):current;
    const seasonName=dates?wanted:(y+'/'+(y+1));
    const seasonStart=y+'-07-01',seasonEnd=(y+1)+'-06-30';

    const isTon=s=>/^(?:(?:CP|C P|CLUB PATI)\s+)?SANT CELONI\s+B$/.test(norm(s));
    const alevi=s=>/^ALEVI\s+OR\s+0?3(?:\s|$)/.test(norm(s));
    const infantil=s=>/^INFANTIL\s+OR\s+0?10(?:\s|$)/.test(norm(s));
    const sameClub=(r,check)=>check(r.home)||check(r.away);
    const leagueMatch=(r,knownId)=>knownId==='4789'
      ?sameClub(r,isBarca)&&(!r.competition||alevi(r.competition))
      :sameClub(r,isTon)&&(!r.competition||infantil(r.competition));

    // La base es l'agenda general. Els calendaris individuals son complementaris,
    // mai no han de substituir els partits que ja s'han importat a l'agenda.
    const sources=rows.map(r=>({...r}));
    if(seasonId){
      const official=[...(store[seasonId]?.rows||[]),...(seasonItem.rows||[])];
      for(const r of official){
        if(!r||!leagueMatch(r,seasonId))continue;
        sources.push(resolved({...r,
          competition:r.competition|| (seasonId==='4789'?'Alevi OR 3':'Infantil OR 10'),
          capturedAt:r.capturedAt||seasonItem.capturedAt||store[seasonId]?.capturedAt||''},store));
      }
    }

    const eligible=r=>r&&validDate(r.iso)&&validTime(r.time)&&
      r.iso>=seasonStart&&r.iso<=seasonEnd;
    const keep=r=>{
      if(tab==='barca')return sameClub(r,isBarca);
      if(tab==='celoni')return sameClub(r,isCeloni);
      if(tab==='grupalevi')return alevi(r.competition)&&sameClub(r,isBarca);
      return infantil(r.competition)&&sameClub(r,isTon);
    };
    const byFixture=new Map();
    for(const r of sources){
      if(!eligible(r)||!keep(r))continue;
      // No utilitzem l'hora a la clau: un partit mogut d'horari no es duplica.
      const key=r.id?'id:'+r.id:[r.iso,norm(r.competition),norm(r.home),norm(r.away)].join('|');
      const prev=byFixture.get(key);
      if(!prev){byFixture.set(key,r);continue;}
      const newer=String(r.capturedAt||'')>=String(prev.capturedAt||'')?r:prev;
      const older=newer===r?prev:r;
      byFixture.set(key,{...older,...newer,
        venue:newer.venue||older.venue||'',
        actaUrl:newer.actaUrl||older.actaUrl||'',
        homeScore:validScore(newer.homeScore)?newer.homeScore:older.homeScore,
        awayScore:validScore(newer.awayScore)?newer.awayScore:older.awayScore});
    }
    const selected=[...byFixture.values()].sort((a,b)=>
      (b.iso+' '+b.time).localeCompare(a.iso+' '+a.time));

    const labels={
      barca:'Bar\u00e7a \u00b7 Temporada',
      celoni:'CP Sant Celoni \u00b7 Temporada',
      grupalevi:'Mag\u00ed \u00b7 Bar\u00e7a Alev\u00ed OR 3 \u00b7 Temporada',
      grupinfantil:'Ton \u00b7 CP Sant Celoni B Infantil OR 10 \u00b7 Temporada'
    };
    // Actualitzar sempre els titols, fins si les targetes ja estan pintades.
    if($('#results-title'))$('#results-title').textContent=labels[tab];
    if($('#results-note'))$('#results-note').textContent=
      selected.length+' partits \u00b7 Temporada '+seasonName+
      ' \u00b7 Agenda FECAPA. M\u00e9s recents primer.';
    if($('#open-fecapa'))$('#open-fecapa').onclick=()=>window.open(
      seasonId?ROOT+'?liga='+seasonId+'&vista=calendar':AGENDA,'_blank','noopener');

    const sig=tab+'|'+JSON.stringify(selected.map(r=>
      [rowKey(r),r.homeScore,r.awayScore,r.venue,r.actaUrl]));
if(root.dataset.zokV5Sig===sig&&root.querySelector('[data-zok-v5]'))return;
root.dataset.zokV5Sig=sig;
const frag=document.createDocumentFragment();
    if(!selected.length){const empty=el('div','empty',tab.startsWith('grup')&&!seasonRows.length?'Importa la temporada completa amb la drecera de '+(tab==='grupalevi'?'Mag\u00ED':'Ton')+' per veure aqu\u00ED tots els partits.':'No hi ha partits verificats en aquesta importaci\u00F3.');empty.dataset.zokV5='1';frag.append(empty);}
    if(!selected.length){
      const empty=el('div','empty',
        'No hi ha partits d\u2019aquest equip i competici\u00f3 dins de l\u2019agenda de la temporada '+seasonName+'.');
      empty.dataset.zokV5='1';frag.append(empty);
    }
for(const r of selected)frag.append(card(r,true));
root.replaceChildren(frag);
    const labels={barca:'Bar\u00E7a \u00B7 Setmana',celoni:'CP Sant Celoni \u00B7 Setmana',grupalevi:'Bar\u00E7a Alev\u00ED OR 3 \u00B7 Setmana',grupinfantil:'Sant Celoni Infantil OR 10 \u00B7 Setmana'};
    if($('#results-title'))$('#results-title').textContent=labels[tab];
    if($('#results-note'))$('#results-note').textContent=seasonRows.length?`${selected.length} partits de la temporada ${read().seasons?.[seasonId]?.season||''} \u00B7 FECAPA. Els partits acabats conserven el marcador oficial; \u2315 obre la fitxa i l\u2019acta.`:`${selected.length} partits \u00B7 Agenda FECAPA (setmana actual). Els marcadors s\u2019actualitzen des d\u2019En directe quan coincideix el partit.`;
    if($('#open-fecapa'))$('#open-fecapa').onclick=()=>window.open(AGENDA,'_blank','noopener');
}
let scheduled=false;
function draw(){
    scheduled=false;const store=read();const list=store.agenda?.rows||[];
    if(!list.length)return; // No suprimir les pantalles antigues fins tenir Agenda.
    scheduled=false;
    const store=read(),list=store.agenda?.rows||[];
    if(!list.length)return; // Sense agenda, app.js segueix funcionant.
const week=byWeek(list).map(r=>resolved(r,store));
    drawHome(week);
    const tab = activeTab();

const temporada = [
  'barca',
  'celoni',
  'grupalevi',
  'grupinfantil'
].includes(tab);

const files = temporada
  ? list.map(r => resolved(r, store))
  : week;

drawList(tab, files);
    const last=[store.agenda?.capturedAt,store.scoreUpdates?.capturedAt,store.live?.capturedAt].filter(Boolean).sort().pop();
    if($('#data-label'))$('#data-label').textContent='Agenda + En directe \u00B7 Safari';
    if($('#data-age')&&last)$('#data-age').textContent='\u00DAltima lectura: '+timestamp(last);
    if($('#total-count'))$('#total-count').textContent=week.length+' partits setmana';
    drawHome(week); // Inici = setmana; no modificar aquest comportament.
    const tab=activeTab();
    // MAI passar la llista setmanal a Magi/Ton: la font son totes les files.
    const all=list.map(r=>resolved(r,store));
    drawList(tab,all,store);
    const last=[store.agenda?.capturedAt,store.scoreUpdates?.capturedAt,
      store.live?.capturedAt].filter(Boolean).sort().pop();
    if($('#data-label'))$('#data-label').textContent='Agenda + En directe \u00b7 Safari';
    if($('#data-age')&&last)$('#data-age').textContent='\u00daltima lectura: '+timestamp(last);
    if($('#total-count'))$('#total-count').textContent=list.length+' partits temporada';
}
function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(draw)}
function saveJson(event){
@@ -340,9 +401,20 @@ drawList(tab, files);
for(const kind of ['agenda','scoreUpdates']){
const entry=p.data[kind];if(!entry||!Array.isArray(entry.rows)||entry.rows.length>2000)continue;
const curr=store[kind]||{};
        store[kind]={rows:mergeRows(curr.rows||[],entry.rows),capturedAt:[curr.capturedAt,entry.capturedAt].filter(Boolean).sort().pop()};
        store[kind]={...entry,...curr,
          rows:mergeRows(curr.rows||[],entry.rows),
          capturedAt:[curr.capturedAt,entry.capturedAt].filter(Boolean).sort().pop(),
          season:curr.season||entry.season||'',
          counts:curr.counts||entry.counts||{}};
      }
      for(const id of ['4789','4786']){
        const entry=p.data.seasons?.[id];
        if(entry&&Array.isArray(entry.rows)&&entry.rows.length<=100&&
           String(entry.capturedAt||'')>String(store.seasons?.[id]?.capturedAt||'')){
          store.seasons={...(store.seasons||{}),[id]:{
            ...entry,rows:entry.rows.map(r=>cleanSeasonRow(r,id)).filter(Boolean)}};
        }
}
      for(const id of ['4789','4786']){const entry=p.data.seasons?.[id];if(entry&&Array.isArray(entry.rows)&&entry.rows.length<=100&&String(entry.capturedAt||'')>String(read().seasons?.[id]?.capturedAt||'')){const store=read();store.seasons={...(store.seasons||{}),[id]:{...entry,rows:entry.rows.map(r=>cleanSeasonRow(r,id)).filter(Boolean)}};write(store)}}
write(store);schedule();
}catch(_){/* Desconnectat: es conserva la c\u00F2pia local */}
}
