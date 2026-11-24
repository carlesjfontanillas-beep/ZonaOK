# JUGADORS TOTAL AUTO — esborrany
Font única: FECAPA, vista plantillas de cada competició. Les classificacions i agenda només aporten l'inventari de lligues. Exemple real d'entrada: liga=4789, filtro=11173, temporada=41.
 
La clau del jugador és l'ID FECAPA (estabilitat entre clubs pendent de prova real). La vinculació és temporada|lliga|filtre|jugador. El filtre no és necessàriament l'ID del club. Els camps clubId/teamId es mantenen nuls fins a tenir una font oficial verificada. No es fusionen noms coincidents ni s'eliminen vinculacions per una lectura parcial. No s'extreuen dates de naixement; només es verifica la presència d'una etiqueta de camp. Cap dada inventada.

## Prova local
Instal·lar playwright i Chromium. Des de l'arrel:
```
python -m pip install playwright
python -m playwright install chromium
python -m unittest discover -s tests -p test_jugadors_auto.py
python scripts/zonaok_jugadors_auto.py --only-seed --seed 4789:11173
python scripts/zonaok_jugadors_auto.py --inventory zonaok-classificacions.json --inventory zonaok-tots-agenda.json --season 41 --previous private/jugadors-master.json
```
Les dades candidates van a private/jugadors-master.json (no afegir al Git). Si no hi ha registres verificats, no es sobreescriu el master. El fitxer jugadors-master.json a l'arrel és una plantilla buida, no un cens real. El diagnòstic conté només recomptes, mai noms ni IDs de jugadors.

## GitHub Actions
En aquesta branca, push al workflow dispara una prova amb la plantilla de referència. Workflow manual i cron diari preparats; GitHub només executa schedule des de la branca per defecte i workflow_dispatch requereix que el workflow existeixi allà. No fusionar fins a validació. El repositori és públic incloses les branques. La captura real no s'ha de publicar en clar. Si es configura la variable de repositori ZONAOK_JUGADORS_AGE_RECIPIENT amb una clau pública age, el workflow genera un artefacte xifrat; la clau privada queda fora de GitHub. Sense aquesta variable només es conserva diagnòstic agregat. Per a un master automàtic persistent entre execucions cal configurar un destí privat, o una cadena de recuperació i xifrat dels candidats. La programació diària és encara una proposta no activa.
 
Pendent: verificar selectors reals, cobertura completa, identificadors i nom de clubs i equips, i possible diversitat d'identificadors per jugador. No modificar app, menú inferior, favorits, ni workflows existents. 
