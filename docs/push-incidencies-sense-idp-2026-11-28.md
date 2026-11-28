# Notificacions push sense IDP oficial — 28/11/2026

## Canvis del Worker

Versió activa al panell de Cloudflare: `4fe6527e`.

- `/sports-events` accepta fixtures sense `leagueId` ni `matchId`; si manquen, treballa amb una identitat interna estable i les dades de competició, equips i horari.
- `/sports-incidents` calcula una identitat interna deduplicable a partir del partit i de la incidència. Ja no depèn d'un IDP oficial.
- `/sports-candidates` no exigeix IDP a la validació del Worker. La cerca automatitzada d'actes encara el necessita per construir l'URL oficial de FECAPA; aquest requisit queda limitat a recuperar l'acta i no bloqueja l'enviament d'avisos.
- Es conserven OIDC, filtres de preferències, deduplicació i autenticació. No s'han canviat subscripcions ni secrets, ni s'han aturat importacions.

## Verificació

- El flux normal d'avisos va respondre HTTP 200: 9 acceptats, 6 duplicats, 0 rebutjats.
- El run manual de GitHub Actions `46136633909` va enviar 7 incidències al Worker `/sports-incidents`, que va respondre HTTP 200: `accepted: 7`, `duplicates: 0`, `baselineMatches: 1`, `pending: 0`.
- El lot semi real parteix del resultat final Barça–Club Patí Voltregà - Masies (4–1) del 27/11/2026. Per a l'enviament, el dia i l'hora s'han traslladat al moment de la prova; els rellotges i els detalls de gols, targeta i falta s'han simulat. No s'hi ha afegit cap etiqueta visible de prova.
- Només s'ha executat el canal habitual amb OIDC. El Worker ha aplicat les preferències de la subscripció existent.

## Etiqueta «from ZonaOK»

«from» és una atribució que mostra iOS, no un camp del payload push ni del Worker. No es pot canviar a «de» des del codi de ZonaOK; iOS decideix l'idioma de la interfície segons la configuració del dispositiu.
