/* ZonaOK · Classificacions TOTALS FECAPA.
   Executa des d'una pàgina de classificacions FECAPA. Descobreix les lligues
   enllaçades al catàleg i llegeix tots els grups amb el nom oficial visible. */
(async()=>{
  try{
    const ROOT='https://www.hoqueipatins.fecapa.cat/';
    const clean=x=>String(x??'').replace(/\s+/g,' ').trim();
    const norm=x=>clean(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();
    const slug=x=>norm(x).toLowerCase().replace(/\s+/g,'-').replace(/^-|-$/g,'');
    if(!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(location.hostname))throw Error('Obre el web de FECAPA a Safari.');
    const urls=new Set();
    const addUrl=value=>{try{const u=new URL(value,ROOT);if(!/hoqueipatins\.fecapa\.cat$/i.test(u.hostname))return;const id=u.searchParams.get('liga');if(id&&/^\d{3,8}$/.test(id))urls.add(id)}catch(_){}};
    const discover=doc=>{
      const html=doc.documentElement?.outerHTML||'';for(const match of html.matchAll(/[?&]liga(?:%3D|=)(\d{3,8})/gi))urls.add(match[1]);
      doc.querySelectorAll('a[href], [data-liga], [data-id-liga], [data-league-id], option[value]').forEach(el=>{
        addUrl(el.href||el.getAttribute('href')||'');
        for(const attr of ['data-liga','data-id-liga','data-league-id','value']){const value=el.getAttribute(attr);if(value&&/^\d{3,8}$/.test(value)&&!['2026','2027','2028'].includes(value))urls.add(value)}
        for(const attr of [...el.attributes])if(/liga|league/i.test(attr.name)){if(/^\d{3,8}$/.test(attr.value))urls.add(attr.value);else addUrl(attr.value)}
        for(const attr of [...el.attributes||[]])if(/liga|league/i.test(attr.name))addUrl(attr.value);
      });
      for(const a of doc.querySelectorAll('a[href*="liga="]'))addUrl(a.href);
    };
    addUrl(location.href);
    discover(document);
    // El catàleg principal conté les lligues; mantenim cookies de la sessió FECAPA.
    for(const path of ['?vista=clasificaciones','?vista=classificacions']){
      try{const response=await fetch(ROOT+path,{credentials:'include',cache:'no-store'});if(response.ok)discover(new DOMParser().parseFromString(await response.text(),'text/html'))}catch(_){}
    }
    // Compatibilitat si el catàleg no exposa enllaços a la càrrega actual.
    for(const id of ['4789','4786','4784','4782','4774'])urls.add(id);
    if(!urls.size)throw Error('No he trobat cap ID de lliga al catàleg FECAPA.');
    const extract=doc=>{
      const out=[];
      for(const heading of doc.querySelectorAll('h1,h2,h3,h4')){
        const name=clean(heading.innerText||heading.textContent);if(!name||name.length>100||name.includes('|')||/\b20\d{2}(?:\/20\d{2})?\b/.test(name))continue;
        let table=null,node=heading;
        for(let i=0;i<5&&node&&!table;i++,node=node.nextElementSibling)table=node.matches?.('table')?node:node.querySelector?.('table.sidgad-clasif-tabla,table');
        if(!table)table=heading.parentElement?.querySelector('table.sidgad-clasif-tabla');
        if(!table)continue;
        const headers=[...table.querySelectorAll('thead th')].map(cell=>norm(cell.innerText||cell.textContent));
        if(!headers.length)continue;
        const idx=(...keys)=>headers.findIndex(h=>keys.includes(h));
        const pts=idx('PTS','PUNTS'),pj=idx('PJ','PARTITS JUGATS'),pg=idx('PG'),pe=idx('PE'),pp=idx('PP'),gf=idx('GF','GOLS A FAVOR'),gc=idx('GC','GOLS EN CONTRA'),dif=idx('DIF','DIFERENCIA','DIFERENCIA DE GOLS','AVG');
        if(pts<0||pj<0)continue;
        const rows=[...table.querySelectorAll('tbody tr')].map(tr=>{
          const cells=[...tr.cells],cell=i=>clean(cells[i]?.innerText||cells[i]?.textContent||'');
          const team=clean(tr.querySelector('.sidgad-clasif-nombre')?.textContent)||cell(1);
          if(!/^\d{1,2}$/.test(cell(0))||!team)return null;
          const stats={};headers.forEach((h,i)=>{if(h&&cell(i))stats[h]=cell(i)});
          return {pos:cell(0),team,played:cell(pj),points:cell(pts),gf:gf<0?'':cell(gf),ga:gc<0?'':cell(gc),difference:dif<0?'':cell(dif),stats};
        }).filter(Boolean);
        if(rows.length>=2&&rows.length<=50)out.push({name,rows});
      }
      return out;
    };
    const competitions={};let leagueCount=0;
    for(const id of urls){
      let doc;
      if(new URLSearchParams(location.search).get('liga')===id&&/clasificaciones|classificacions/i.test(location.search))doc=document;
      else{
        const response=await fetch(ROOT+'?liga='+encodeURIComponent(id)+'&vista=clasificaciones',{credentials:'include',cache:'no-store'});
        if(!response.ok)continue;
        doc=new DOMParser().parseFromString(await response.text(),'text/html');
      }
      const groups=extract(doc);if(!groups.length)continue;leagueCount++;
      for(const group of groups){
        const key=id+':'+slug(group.name);
        competitions[key]={name:group.name,category:group.name.replace(/\s+(?:OR|PLATA|BRONZE)\s+\d+\b/i,'').replace(/\s+GRUP\s+[A-Z0-9]+\b/i,'').trim(),competition:group.name.replace(/\s+(OR|PLATA|BRONZE)\s+\d+\b/i,' $1').replace(/\s+GRUP\s+[A-Z0-9]+\b/i,'').trim(),leagueId:id,url:ROOT+'?liga='+id+'&vista=clasificaciones',rows:group.rows};
      }
    }
    const count=Object.keys(competitions).length;if(!count)throw Error('No he pogut llegir taules de classificació. Obre la pestanya «Classificacions» i espera que carregui.');
    const packet={source:'FECAPA-SAFARI',version:3,kind:'classificacions-total',capturedAt:new Date().toISOString(),competitions};
    const bytes=new TextEncoder().encode(JSON.stringify(packet));let packed=bytes;
    if(typeof CompressionStream==='function')packed=new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
    let binary='';for(let i=0;i<packed.length;i+=8192)binary+=String.fromCharCode(...packed.subarray(i,i+8192));
    const encoded=btoa(binary);if(encoded.length>62000)throw Error('El fitxer de totes les classificacions supera el límit; he recollit '+count+' grups, però no s’ha enviat.');
    completion(encoded);
  }catch(error){completion('ERROR: '+String(error?.message||error))}
})();
