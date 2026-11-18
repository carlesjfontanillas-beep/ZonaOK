# ZonaOK — iPhone + GitHub Pages

Projecte INDEPENDENT de qualsevol altra aplicació. Cost d'allotjament: 0 € en repositori públic dins dels límits gratuïts de GitHub Pages. No utilitza API OpenAI, Apps Script ni backend.

## Què fa
- Pantalla principal ZonaOK adaptada a iPhone i amb sis accessos ràpids.
- Cada botó obre `https://chatgpt.com/?q=...` amb una pregunta completa, feta per consultar exclusivament FECAPA, les lligues 4789/4786/4784 i `/ag/`.
- En cas que ChatGPT no empleni o no enviï la consulta, hi ha un botó per **copiar la pregunta** i enganxar-la manualment.
- No inventa ni publica partits a la portada. La consulta i les seves limitacions es mostren dins de ChatGPT.

## Publicació (sense escriure codi)
1. A GitHub, crea un repositori públic **ZonaOK** (buit o amb README).
2. Prem **Add file → Upload files** i arrossega **els fitxers descomprimits** d'aquesta carpeta (no només el ZIP).
3. Prem **Commit changes**.
4. Ves a **Settings → Pages → Build and deployment → Deploy from a branch**; selecciona **main** i carpeta **/(root)** i desa.
5. La URL, si l'usuari GitHub és `ELTEUUSUARI`, serà `https://ELTEUUSUARI.github.io/ZonaOK/` (GitHub mostra l'URL real a Pages).
6. Des de **Safari** a iPhone, obre aquesta URL → Compartir → **Afegir a la pantalla d'inici**.

## Limitacions importants
- `?q=` no és una API pública documentada i estable per a consultes de ChatGPT. Segons el dispositiu i la versió, pot emplenar la pregunta sense enviar-la o pot no interpretar-la. Hi ha una alternativa de còpia manual.
- ChatGPT s'obre **fora** de ZonaOK. Les respostes no apareixen dins de ZonaOK.
- ChatGPT pot no poder llegir les dades dinàmiques de FECAPA. En aquest cas ha de declarar que no són verificables i no presentar dades inventades.
- Pot caldre iniciar sessió a ChatGPT i prémer «Enviar».
- La web no necessita permisos ni claus API. No promet accés a dades ni respostes verificades.


## Pont experimental Safari → ZonaOK
Vegeu `GUIA_PROVA_SAFARI.md`. És una prova manual, no una consulta directa des de GitHub Pages.

## Temporada sencera de Magí i Ton
- A ZonaOK, els botons **Magí · Aleví OR 3** i **Ton · Infantil OR 10** mostren els partits de tota la temporada que s'hagi importat, ordenats del més recent al més antic.
- Les dreceres `ZonaOK-Magi-Temporada.shortcut` i `ZonaOK-Ton-Temporada.shortcut` llegeixen les taules oficials de FECAPA (lligues 4789 i 4786) des de Safari, incloent fixtures futurs, resultats disponibles i identificador de la fitxa del partit. Les classificacions existents continuen separades.
- Cal obrir la pàgina de la lliga corresponent a FECAPA, esperar que aparegui el calendari complet i executar la drecera des de Safari. L'importació queda desada en aquell dispositiu; `Descarregar JSON` la prepara per publicar-la i compartir-la.
- El botó `⌕ Acta` obre la fitxa oficial del partit. FECAPA obre la fitxa a la pestanya Resum i cal triar-hi «Acta del partit»: el lloc no admet un enllaç públic que obri directament aquesta pestanya.
- La drecera mostra les files examinades, el nombre de partits, quants tenen marcador i quants disposen d'identificador d'acta. Si FECAPA canvia l'estructura de la taula, cal revisar aquests recomptes abans de confiar en la importació.


## Agenda de temporada sencera
- A la pàgina oficial FECAPA `/ag/`, selecciona tots els clubs i el rang complet de la temporada actual. Executa `ZonaOK Agenda` des de Safari per importar tots els partits de Barça i CP Sant Celoni; no es limita a dilluns–diumenge.
- La importació mostra el recompte de files, els partits de cada club i les pistes detectades. Les dades es comprimeixen abans d'obrir ZonaOK i es desen en la memòria local; publica `zonaok-data.json` per compartir-les entre dispositius.
- Els botons Barça i CP Sant Celoni mostren la temporada completa després d'aquesta importació; la portada conserva el resum de la setmana.
