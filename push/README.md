# ZonaOK · Preparació Web Push (desactivada)

## Abast
GitHub Pages i importacions FECAPA existents -> JSON verificats -> normalitzador i comparador independent -> Cloudflare Worker/D1 -> Web Push VAPID.
No tocar importadors ni frontend públic. No hi ha comptes; preferències i consentiment per instal·lació. Estrella de favorit i campana són independents.
El manifest existent ja usa display standalone. A iOS/iPadOS cal instal·lar a la pantalla d'inici, versió 16.4 o posterior i un gest explícit per demanar permís.

## Fitxers de preparació
- zonaok-push-sw.js: receptor de push i clic que obre ZonaOK; no intercepta fetch ni implementa memòria cau.
- zonaok-push-client.js: mòdul opt-in, subscripció, actualització preferències, baixa i petició de prova. Encara no es carrega a cap pàgina.
- push/schema.sql: esquema D1 proposat; no desplegat. Les credencials del dispositiu s'han de conservar al backend com a hash i els endpoints només a D1 privat.

## Contracte pendent del Worker
HTTPS, CORS restringit a l'origen real de Pages, preflight i validació estricta de mida/esquema. Sense tokens GitHub al client.
- POST /subscriptions: subscription i preferences; retorna token opac aleatori. Si ja existeix un endpoint, exigir credencial vàlida abans de modificar-lo.
- POST /preferences: preferences, Bearer token; modifica només subscripció pròpia.
- POST /unsubscribe: Bearer token; desactiva o elimina subscripció pròpia.
- POST /test: Bearer token, limitació de freqüència i missatge de prova només al mateix dispositiu.
Validar destinacions push HTTPS amb llista de serveis fiables i evitar redireccions/SSRF. Limitar altes i peticions anònimes. VAPID privada i credencial interna d'ingesta a secrets de Worker, mai al repositori; VAPID pública al client.
Inicialitzar amb enviaments reals deshabilitats per defecte. No usar l'esquema D1 amb dades reals abans de revisar seguretat, retenció i baixa.

## Regles de detecció
Adaptador de JSON pendent de verificar camps reals i frescor de fonts. No inferir l'estat per l'hora prevista o pel marcador sol.
- Identificador estable FECAPA lliga+partit; no basar la deduplicació només en noms.
- Inicialització: guardar una línia base sense enviar notificacions històriques; ignorar observacions antigues i parcials.
- Inici: primera transició confirmada a acta oberta.
- Final: transició confirmada a acta tancada amb marcador definitiu.
- Només Nacional Catalana femenina/masculina: gols i targetes amb incidències verificades de font; no convertir correccions de marcador en gols. Identificador estable d'incidència.
- Altres categories: només inici i final. No notificar incidències ni resultats provisionals.
- Un dispositiu que coincideixi per club, equip, categoria, competició o jugador rep una sola notificació de cada esdeveniment. Jugadors només quan el catàleg i les vinculacions estiguin validats.
- Persistir estat i esdeveniments en transacció; cua amb clau (event_id, subscription_id), reclamació atòmica amb lease, reintents limitats i neteja de subscripcions 404/410. Evitar duplicats amb identificador/tag estable; no prometre exactament una entrega davant errors de xarxa amb resposta perduda.
- Quatre consultes generals al dia segons pla acordat; aprofitar importacions existents i intensificar quan hi ha partits. No duplicar scraping FECAPA.

## Abans d'activar
1. Verificar service worker/scope de la versió pública i adaptar menús de Favorits.
2. Construir i desplegar Worker/D1 de prova i claus VAPID. Revisar seguretat.
3. Integrar client només amb configuració completa; no demanar permís automàtic.
4. Provar alta, baixa i notificació de prova en iPhone instal·lat, amb l'app tancada.
5. Verificar JSON d'Agenda, En directe i Actes, camps d'estat i incidències; implementar comparador amb fixtures.
6. Simular línia base, reexecució, retard de dades, correcció de marcador, final confirmat, múltiples favorits, preferències i errors de lliurament.
7. Activar un únic dispositiu de prova abans de publicar i habilitar enviaments generals.

Estat: esborrany de codi i esquema, no integrat, no provat en execució, no publicat a main.
