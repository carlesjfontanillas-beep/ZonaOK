# ZonaOK · Resultats tots els clubs · Targetes compactes V5

Es mantenen **exactament** els camps i les mides compactes del `zonaok-resultats-7dies(3).js` aportat per l’usuari:

- **Línia 1:** categoria, hora, data i botó Acta (24 px d’alçada).
- **Línia 2:** equips, escuts petits i marcador.
- **Eliminats:** pista / ubicació i «Marcador Agenda / En directe» de la targeta.
- **Mida de targeta:** farcit 5px 8px, separació entre targetes 5px, escut 26px (24px en pantalles estretes), marcador 19px (17px en pantalles estretes).

**Sense canvis** a les noves dreceres d’Agenda, En directe, Python, GitHub Actions o JSON.
Es conserva la lectura de `zonaok-tots-resultats-7dies.json`, els filtres dinàmics de **tots els clubs** i Categoria, els escuts nous i l’ID del partit a les actes.

## Instal·lació ràpida si la V2 de tots els clubs ja és a GitHub

1. Puja **només** `zonaok-resultats-7dies.js` a l’arrel de `main`, substituint l’existent.
2. A `index.html`, utilitza `<script defer src="zonaok-resultats-7dies.js?v=20261121-tots-r5"></script>` abans de `</body>`.
3. Fes Commit i obre `https://carlesjfontanillas-beep.github.io/ZonaOK/?v=20261121-tots-r5`.

Si encara no has pujat la V2 completa, penja totes les carpetes i fitxers del ZIP respectant la ubicació indicada a `INSTRUCCIONS_INSTAL_LACIO.md`.
