# ZonaOK — contracte JSON de jugadors (esborrany V1)

Font única FECAPA, plantilles. L'esquema és a `schemas/jugadors-master.schema.json`. Una fitxa per ID de jugador; vinculacions indexades per temporada|lliga|filtre|jugador. El filtre no equival necessàriament a l'ID de club ni a l'ID federatiu de l'equip. Els camps no verificats són nuls o absents, mai inventats. Les estadístiques opcionals pertanyen a una vinculació esportiva, no es sumen automàticament; validar capçaleres i significat.

Camps amb cobertura real V5: playerId/name 252/252; leagueId/teamFilterId/seasonId/teamName/profileUrl 297/297; clubId per escut 132/297 (pendent de confirmar significat complet); sports.played 181/297. Els camps opcionals sports.number/goals/yellowCards/redCards/blueCards i teamId/clubName no estan confirmats. La prova V6 investiga més camps. No es recullen dates de naixement ni altres dades delicades.

La prova V7 escriu un master real temporal en un directori privat efímer del runner, el rellegeix i valida esquema, claus, vinculacions, URL i reimportació sense duplicats. El directori s'elimina. Només es conserva el diagnòstic agregat, amb resultat i mida del fitxer; no es publiquen registres identificables ni es guarden com a artefacte. El master de l'arrel continua buit. Persistència real entre execucions requereix destí privat autoritzat i queda pendent.

No fusionar encara. No modifica la UI ni els altres imports.
