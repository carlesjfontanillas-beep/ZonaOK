// ZONAOK · Acció «Executar JavaScript en la pàgina web» de Dreceres
// IMPORTANT: pàgina web = «Entrada de la funció ràpida».
// Prova la pàgina FECAPA de la lliga 4789; per a altres lligues canvia el número.
const LEAGUE = '4789';
const BASE = 'https://carlesjfontanillas-beep.github.io/ZonaOK/';
const rows = Array.from(document.querySelectorAll('tr'))
  .map(tr => {
    const text = (tr.innerText || '').replace(/\s+/g, ' ').trim();
    const match = text.match(/\b(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}:\d{2})\b/);
    return {text, date: match ? match[0] : ''};
  })
  .filter(row => /^\d{2}\/\d{2}\/\d{4}\s+\d{2}:\d{2}/.test(row.text));
const selected = rows.filter(row => /BARÇA|BARCA|FC BARCELONA/i.test(row.text));
// Primera prova només Barça, màxim 15 files per evitar URL excessiva.
const payload = {
  source: 'FECAPA-SAFARI', league: LEAGUE,
  capturedAt: new Date().toISOString(), rows: selected.slice(0,15)
};
if (!selected.length) {
  completion('ERROR: No he trobat partits del Barça a les files visibles de FECAPA.');
} else {
  completion(BASE + '#fecapa=' + encodeURIComponent(JSON.stringify(payload)));
}
