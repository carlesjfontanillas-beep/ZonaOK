#!/usr/bin/env python3
"""Importar els IDs/actes de FECAPA i fusionar-los amb zonaok-actes.json.

Només pot escriure zonaok-actes.json. Mai esborra coincidències existents.
Per GitHub Actions workflow_dispatch; variables secret via ambient.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "zonaok-actes.json"
LEAGUES = {"4789", "4786", "4784"}
BASE = "https://www.hoqueipatins.fecapa.cat/"


def die(message: str) -> None:
    raise ValueError(message)


def normal(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(s).upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", s).split())


def preferred(league: str, home: str, away: str) -> bool:
    names = (normal(home), normal(away))
    if league == "4789":
        return any(re.fullmatch(r"(?:BARCA|FC BARCELONA|F C BARCELONA|FCBETRANS|FCBETERANS)(?: [A-Z0-9]+)?", n) for n in names)
    return any(re.fullmatch(r"(?:CP |C P |CLUB PATI )?SANT CELONI B", n) for n in names)


def iso(s: str) -> str:
    if not re.fullmatch(r"20\d\d-\d\d-\d\d", s):
        die("Data ISO incorrecta")
    dt.date.fromisoformat(s)
    return s


def hora(s: str) -> str:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", s):
        die("Hora incorrecta")
    return s


def text(v: object, n: int = 140) -> str:
    s = str(v or "").strip()
    if not s or len(s) > n:
        die("Nom o valor de partit buit/massa llarg")
    return s


def entry_from_row(league: str, r: list, stamp: str) -> dict:
    if not isinstance(r, list) or len(r) not in (5, 7):
        die("La fila d'acta ha de tenir 5 o 7 camps")
    date, time, home, away, fid = r[:5]
    date = iso(str(date))
    time = hora(str(time))
    home = text(home)
    away = text(away)
    fid = str(fid)
    if not re.fullmatch(r"\d{4,10}", fid):
        die("L'identificador no es numeric")
    if not preferred(league, home, away):
        die(f"L'acta {fid} no pertany a l'equip favorit de {league}")
    row = {
        "league": league, "id": fid, "iso": date, "time": time,
        "home": home, "away": away,
        "competition": {"4789": "ALEVÍ OR 3", "4786": "INFANTIL OR 10", "4784": "JUVENIL OR 6"}[league],
        "actaUrl": f"{BASE}?liga={league}&vista=calendar&partido={fid}",
        "capturedAt": stamp,
    }
    if len(r) == 7 and r[5] is not None and r[6] is not None:
        if any(type(v) is not int or v < 0 or v >= 200 for v in r[5:7]):
            die("Marcador no vàlid")
        row["homeScore"], row["awayScore"] = r[5], r[6]
    return row


def safe_existing(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    league = str(row.get("league", ""))
    fid = str(row.get("id", ""))
    if league not in LEAGUES or not re.fullmatch(r"\d{4,10}", fid):
        return None
    return dict(row)


def migrate_old(content: dict) -> dict:
    """Preservar format V18/V20 i si cal migrar el legacy actaIndex."""
    previous = content if isinstance(content, dict) else {}
    entries = list(previous.get("fixtures", [])) if isinstance(previous.get("fixtures"), list) else []
    legacy = previous.get("actaIndex") or (previous.get("data") or {}).get("actaIndex", {})
    if isinstance(legacy, dict):
        for league, obj in legacy.items():
            if league not in LEAGUES or not isinstance(obj, dict):
                continue
            for row in obj.get("rows", []):
                if not isinstance(row, dict):
                    continue
                r = dict(row, league=league)
                entries.append(r)
    return {"version": 1, "fixtures": entries}


def main() -> None:
    raw = os.environ.get("ZONAOK_PAYLOAD_B64", "")
    if not raw or len(raw) > 65535 or not re.fullmatch(r"[A-Za-z0-9+/=]+", raw):
        die("Payload absent o format base64 invalid")
    payload = json.loads(base64.b64decode(raw, validate=True).decode("utf-8"))
    if payload.get("source") != "FECAPA-SAFARI" or payload.get("kind") != "match-ids-v1":
        die("Font/kind invalida")
    league = str(payload.get("league", ""))
    if league not in LEAGUES:
        die("Lliga no acceptada")
    stamp = text(payload.get("capturedAt", ""), 48)
    dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list) or not (1 <= len(rows) <= 250):
        die("Han d'arribar entre 1 i 250 actes verificades")
    fetched = [entry_from_row(league, r, stamp) for r in rows]
    if len({(r["league"], r["id"]) for r in fetched}) != len(fetched):
        die("Actes duplicades dins del lot; no publicar")

    if DEST.exists():
        existing = json.loads(DEST.read_text("utf-8"))
    else:
        existing = {}
    if existing and not isinstance(existing, dict):
        die("El fitxer existent no es un objecte JSON; conservar-lo")
    # Si té una estructura desconeguda, refusar en comptes d'esborrar.
    if existing and not any(k in existing for k in ("fixtures", "actaIndex", "data")):
        die("Format desconegut de zonaok-actes.json: no se sobreescriu")
    old = migrate_old(existing)
    map_by_id = {}
    for old_row in old["fixtures"]:
        e = safe_existing(old_row)
        if e is not None:
            map_by_id[(e["league"], e["id"])] = e
    before = len(map_by_id)
    added = 0
    updated = 0
    for row in fetched:
        k = (row["league"], row["id"])
        prev = map_by_id.get(k)
        if prev is None:
            map_by_id[k] = row
            added += 1
            continue
        # Un ID conegut mai no pot passar silenciosament a altres equips o data.
        if prev.get("iso") and prev["iso"] != row["iso"]:
            die(f"Conflicte de data per acta {row['id']} ({prev['iso']} vs {row['iso']}); no publicat")
        for side in ("home", "away"):
            if prev.get(side) and normal(prev[side]) != normal(row[side]):
                die(f"Conflicte d'equips per acta {row['id']}; no publicat")
        merged = {**prev, **row}
        if prev != merged:
            updated += 1
        map_by_id[k] = merged
    fixtures = sorted(map_by_id.values(), key=lambda r: (str(r.get("iso", "")), str(r.get("time", "")), r["league"], r["id"]))
    output = {"version": 1, "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"), "fixtures": fixtures}
    # No canviar l'arxiu si el contingut dels partits no ha variat.
    if existing.get("version") == 1 and existing.get("fixtures") == fixtures:
        print(f"Sense canvis: {len(fixtures)} actes ja registrades")
        return
    DEST.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Actes: abans={before}; rebudes={len(fetched)}; noves={added}; actualitzades={updated}; total={len(fixtures)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR IMPORTANT: {exc}", file=sys.stderr)
        sys.exit(1)
