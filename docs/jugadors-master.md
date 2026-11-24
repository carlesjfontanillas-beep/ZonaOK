# ZonaOK — contracte mestre de jugadors
Font única FECAPA. Contracte ampliat compatible amb els documents v1 anteriors. Un master per temporada; el fitxer públic és una plantilla buida. No fusionar ni desplegar fins a validar la importació i un destí privat autoritzat.

## Col·leccions
- players: ID federatiu, nom, variants, any de naixement opcional (mai data completa), marques de verificació.
- memberships: clau temporada|lliga|filtre|jugador. Noms de club, equip, lliga i grup, escut, URL de fitxa. Un jugador pot tenir diverses vinculacions. El filtre no equival necessàriament a l'ID federatiu de l'equip ni al club.
- matchAppearances: clau temporada|lliga|partit|home/away|jugador. Dorsal, P (porter), C (capità), participació, estadístiques opcionals, URL canònica i font. El filtre d'equip només es conserva si correspon a una vinculació verificada, no es copia del filtre de navegació. No es deduplica per nom ni dorsal.
- sports (plantilles), profileStats (resum) i matches (historial anterior): fonts independents. No sumar totals entre fonts o comptar dues vegades la mateixa aparició. L'índex canònic per partit és matchAppearances.

## Semàntica
P explícita = goalkeeper; buit només implica field si la columna i la convenció s'han verificat. C explícita = captain true; buit només implica false si es verifica. Num = dorsal en aquell partit. Una alineació significa listed; played exigeix evidència de participació. Absència no equival a zero. No inferir gols, targetes, assistències, penals o altres estadístiques sense verificar columnes i valors. Els camps de gols, assistències, targetes, penals, faltes directes, aturades i minuts són opcionals; no tots estan confirmats.
 
## Validació i persistència
V12 confirma lectura de Resum i Partits, filtre Totes les competicions en 10/12 fitxes; no ha incorporat historial. Actes V2: sis URL, quatre partits, 69 files de jugadors amb ID i dorsal. V3 valida P/C. La lectura i fusió real d'aparicions queda pendent de validar. Les proves escriuen i rellegeixen el JSON temporal i comproven claus i referències, sense publicar dades identificables. Els diagnòstics públics són agregats. No es modifiquen la UI ni altres imports.

## Importació total candidata
El workflow JUGADORS MASTER TOTAL llegeix els catàlegs de main i uneix tots els IDs d'actes disponibles i totes les lligues identificades. No hi ha límit de mostra. Dos consultors simultanis com a màxim, pausa per consulta i aturada de les actes si apareix un bloqueig HTTP 403/429/503. El runner té un pressupost finit: es declaren les actes no intentades i les incidències; no es considera cobertura completa si falten dades. L'enriquiment de fitxes individuals és una fase separada. El JSON mestre només existeix temporalment dins el runner i es verifica i rellegeix. No es conserva entre execucions ni es puja com a artefacte públic. El destí privat permanent i la represa entre execucions encara s'han de configurar.
