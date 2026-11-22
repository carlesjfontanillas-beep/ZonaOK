#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZonaOK V29.8 · coincidència per club favorit + dia + hora.

Conserva el motor V29 i el format de l'Agenda; només personalitza la
selecció de l'índex destí. NO necessita coincidir el rival quan el resultat
FECAPA porta BAR, CPSC, CPSCA o CPSCB. En cas d'ambigüitat no publica.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import sys
import unicodedata


def normalitza(valor):
    s = unicodedata.normalize('NFD', str(valor or '')).upper()
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


ALIASES = {
    'HCSJ': {'INNOAESTHETICS HC SANT JUST'},
    'MHCA': {'MOLLET HC A'},
    'CADI': {'CLUB HOQUEI CADI'},
    'HSCA': {'VICIO PHC SANT CUGAT A'},
    'PAL': {'GENERALI HC PALAU'},
}


def alias_verificat(nom_agenda, nom_directe):
    return normalitza(nom_agenda) in ALIASES.get(normalitza(nom_directe).replace(' ', ''), ())


def club_clau_abreujat(nom):
    value = normalitza(nom).replace(' ', '')
    if value == 'BAR':
        return 'barca'
    if value in {'CPSC', 'CPSCA', 'CPSCB'}:
        return 'celoni'
    return ''


def club_agenda(nom):
    value = normalitza(nom)
    if re.fullmatch(r'(?:BARCA|FC BARCELONA|F C BARCELONA)(?: [ABCD])?', value):
        return 'barca'
    if re.fullmatch(r'(?:(?:CP|C P|CLUB PATI) )?SANT CELONI(?: [ABCD])?', value):
        return 'celoni'
    return ''


def installa_equivalencies(modul):
    """Canvia només la recerca; mai els marcadors, dates o dades de l'Agenda."""
    if getattr(modul, '_zonaok_v298_installed', False):
        return modul
    old_team = modul.team_compatible
    old_select = modul.select_unique

    def compatible(nom_agenda, nom_directe):
        return old_team(nom_agenda, nom_directe) or alias_verificat(nom_agenda, nom_directe)

    def select_unique(output, incoming):
        fav_home = club_clau_abreujat(incoming.get('home'))
        fav_away = club_clau_abreujat(incoming.get('away'))
        if not (fav_home or fav_away):
            return old_select(output, incoming)
        candidates = []
        for i, old in enumerate(output):
            if not isinstance(old, dict):
                continue
            if str(old.get('iso') or '') != incoming['iso'] or str(old.get('time') or '') != incoming['time']:
                continue
            # Mai barrejar costat local/visitant, ni dos ID inequívocament diferents.
            if incoming.get('id') and old.get('id') and str(incoming['id']) != str(old['id']):
                continue
            if fav_home and club_agenda(old.get('home')) != fav_home:
                continue
            if fav_away and club_agenda(old.get('away')) != fav_away:
                continue
            candidates.append(i)
        if len(candidates) == 1:
            return candidates[0], 'favorit_data_hora_sense_rival', 1
        if len(candidates) > 1:
            # Categories de FECAPA (p. ex. INFANTIL OR) poden ometre el grup.
            narrowed = [i for i in candidates if modul.comp_compatible(
                output[i].get('competition'), incoming.get('competition'))]
            if len(narrowed) == 1:
                return narrowed[0], 'favorit_data_hora_categoria', 1
            return None, 'favorit_ambigu_data_hora', len(candidates)
        # No acceptar falses coincidències d'altres clubs si la sigla era coneguda.
        return None, 'favorit_sense_partit_data_hora', 0

    modul.team_compatible = compatible
    modul.select_unique = select_unique
    modul._zonaok_v298_installed = True
    return modul


def main():
    import zonaok_import_directe_v29 as v29
    installa_equivalencies(v29)
    root = Path(os.environ.get('GITHUB_WORKSPACE') or '.').resolve()
    result = v29.run(root)
    print('V29.8: BAR/CPSC/CPSCA/CPSCB associats per dia i hora, sense comparar rival')
    return result


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        sys.exit('ERROR V29.8: ' + str(exc))
