# Notificacions push sense IDP oficial — 28/11/2026

## Canvis del Worker

Versió activa al panell de Cloudflare: `24ca50a7` (anterior: `4fe6527e`).

- `/sports-events` accepta fixtures sense `leagueId` ni `matchId`; si manquen, treballa amb una identitat interna estable i les dades de competició, equips i horari.
- `/sports-incidents` calcula una identitat interna deduplicable a partir del partit i de la incidència. Ja no depèn d'un IDP oficial.
- `/sports-candidates` no exigeix IDP a la validació del Worker. La cerca automatitzada d'actes encara el necessita per construir l'URL oficial de FECAPA; aquest requisit queda limitat a recuperar l'acta i no bloqueja l'enviament d'avisos.
- Es conserven OIDC, filtres de preferències, deduplicació i autenticació. No s'han canviat subscripcions ni secrets, ni s'han aturat importacions.
- El format dels avisos d'incidència ara mostra `GOL!` en majúscules, el nom del jugador i el marcador en una línia pròpia amb l'etiqueta `Resultat:`. Les targetes i les faltes directes també mostren el jugador i el resultat quan són disponibles. Quan l'acta no identifica jugador, no se n'inventa cap.

## Verificació

- El flux normal d'avisos va respondre HTTP 200: 9 acceptats, 6 duplicats, 0 rebutjats.
- El primer run semi real, `46136633909`, va enviar 7 notificacions amb incidències simulades; no corresponien a l'acta real.
- Després de rebre l'acta que va facilitar l'usuari, el run `46137488973` va preparar i enviar exactament 6 notificacions amb les incidències reals: HTTP 200, `accepted: 6`, `duplicates: 0`, `baselineMatches: 1`, `pending: 0`. El lot conté:
  - P1 15:54 — gol del Barça, Nicolás Sama Gilabert (#28), 1–0.
  - P1 15:20 — gol del Barça, Oriol Castro Castillejo (#44), 2–0.
  - P1 07:09 — gol del CP Voltregà–Masies, Alex Vila Colell (#6), 2–1.
  - P1 02:09 — gol del Barça, Albert Molera i Moncau (#8), assistència de Marc Orus Cabanillas (#78), 3–1.
  - P2 10:34 — gol del Barça, Albert Molera i Moncau (#8), assistència d'Oriol Castro Castillejo (#44), 4–1.
  - P2 05:17 — targeta blava al CP Voltregà–Masies, Marc Jurado Lira (#4).
- Els rellotges i l'hora del partit s'han traslladat al moment de la prova per fer l'enviament semi real; els detalls de la incidència i el marcador corresponen a l'acta facilitada. No s'hi ha afegit cap etiqueta visible de prova.
- El desplegament del format nou és la versió activa `24ca50a7`. No s'han reenviat les sis incidències després del canvi de format per evitar duplicar avisos al telèfon.

## Recuperació d'actes quan el catàleg no porta IDP

El capturador ara conserva els partits de Nacional Catalana encara que no tinguin `leagueId`/`matchId`. Calcula un `internalId` estable amb temporada, data, hora, competició i equips per seleccionar el partit i deduplicar-ne les incidències. Quan l'acta ho requereix, consulta el calendari oficial de la competició (masculina `4774`, femenina `4775`) i només segueix l'enllaç de partit si troba una única coincidència exacta per data i equips. Si no n'hi ha cap o n'hi ha més d'una, no associa cap acta ni envia incidències d'aquell partit.

## Etiqueta «from ZonaOK»

«from» és una atribució que mostra iOS, no un camp del payload push ni del Worker. No es pot canviar a «de» des del codi de ZonaOK; iOS decideix l'idioma de la interfície segons la configuració del dispositiu.
