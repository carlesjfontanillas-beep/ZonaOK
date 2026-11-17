# ZonaOK — prova del pont Safari → GitHub Pages

## Què valida aquesta prova?
La drecera de Safari llegeix les files de la taula visible a FECAPA i envia les dades a ZonaOK mitjançant un fragment de l’URL (`#fecapa=`). ZonaOK guarda les files en `localStorage` de l’iPhone. **No hi ha cap petició de ZonaOK a FECAPA, ni actualització automàtica.** Les dades del fragment no s’envien a GitHub com una petició HTTP ordinària, però poden quedar exposades en l’activitat del dispositiu o en captures.

## Publicació
Puja tots els fitxers d’aquesta carpeta a l’arrel del repositori `ZonaOK` a GitHub, substituint els existents i afegint `safari-bridge.js` i `DRECERA_SAFARI_PROVA.js`. GitHub Pages ha d'estar configurat `main / (root)`.

## Drecera d’iPhone
1. Obre l’acció «Executar JavaScript en la pàgina web» de «Prova FECAPA». Conserva la variable `Entrada de la funció ràpida` com a pàgina.
2. Substitueix el seu codi per **tot** el contingut de `DRECERA_SAFARI_PROVA.js`.
3. **Elimina l'acció «Mostrar resultat»**, o deixa-la al final si vols inspeccionar l’URL.
4. Afegeix l’acció **«Obrir URL»** immediatament després del JavaScript. Com a URL selecciona la variable **«Resultat de JavaScript»**.
5. Obre la pàgina FECAPA de lliga 4789 a Safari, espera que es carregui la taula i prem Compartir → Prova FECAPA.
6. La drecera hauria d’obrir ZonaOK i mostrar les files del Barça importades. Si l’enllaç és molt llarg, redueix `.slice(0,15)` a `.slice(0,5)`.

## Limitacions
- Aquest pont només importa files; **no determina les pistes, els escuts ni distingeix correctament els grups Or 1/2/3 sense una prova del DOM**.
- No s’hi infereix que l’absència d’un marcador signifiqui que el partit està pendent.
- Les dades no es renoven en tornar a obrir ZonaOK; cal repetir la drecera quan vulguis actualitzar.
- El calendari HTML de FECAPA pot canviar: el selector `tr` s’ha validat en les captures de prova, no contra cada pàgina ni a cada dispositiu.
- La resta dels sis botons encara obren ChatGPT com abans, sense canvis.
