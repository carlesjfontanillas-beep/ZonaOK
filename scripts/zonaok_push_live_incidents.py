#!/usr/bin/env python3
"""Capture FECAPA live incidents only for subscription-selected NC M/F fixtures."""
import argparse, asyncio, hashlib, json, re, unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

BASE = "https://www.hoqueipatins.fecapa.cat/"
MADRID = ZoneInfo("Europe/Madrid")
LIVE = {"EN JOC", "EN DIRECTE", "EN DIRECTO", "LIVE", "PLAYING", "IN PROGRESS", "PRIMERA PART", "SEGONA PART", "DESCANS", "PRIMERA PARTE", "SEGUNDA PARTE", "DESCANSO"}
COMPETITIONS = {"NACIONAL CATALANA MASCULINA", "NACIONAL CATALANA FEMENINA"}
TIME = re.compile(r"^P([12])\s+(\d{1,2}:\d{2})$", re.I)

def norm(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", str(value or "")) if unicodedata.category(c) != "Mn").upper().split())

def incident_id(season, fixture, item):
    values = [season, fixture["leagueId"], fixture["matchId"], item["event"], item["period"], item["matchClock"], item["team"], item["player"], item["score"], str(item["ordinal"])]
    material = "|".join(norm(v).replace("|", "/") for v in values)
    return hashlib.sha256(material.encode()).hexdigest()

def parse_incidents(text, fixture, *, season="2026/2027", observed_at=None):
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines()]
    start = next((i for i, line in enumerate(lines) if norm(line) == "INCIDENCIES"), None)
    if start is None: return []
    blocks, current = [], None
    for line in lines[start + 1:]:
        stamp = TIME.match(norm(line))
        if stamp:
            if current: blocks.append(current)
            current = {"period": "P" + stamp.group(1), "matchClock": stamp.group(2), "lines": []}
        elif current: current["lines"].append(line)
    if current: blocks.append(current)
    output, counts = [], Counter()
    for block in blocks:
        desc = next((line for line in block["lines"] if re.match(r"^(GOL|TARGETA|TARJETA|FALTA DIRECTA)\b", norm(line))), "")
        label = norm(desc)
        if label.startswith("FALTA DIRECTA"): event = "directFoul"
        elif label.startswith(("TARGETA", "TARJETA")): event = "card"
        elif label.startswith("GOL") and not any(x in label for x in ("ANUL", "ANUL·LAT", "NO VALID")): event = "goal"
        else: continue
        team = re.sub(r"^(?:FALTA DIRECTA(?: PER A| PARA)?|TARGETA(?: GROGA| BLAVA| VERMELLA)?|TARJETA(?: AMARILLA| AZUL| ROJA)?|GOL)\s*", "", desc, flags=re.I).strip()
        player = next((line.strip() for line in block["lines"] if re.match(r"^#\s*\d+\b", line)), "")
        score = next((re.sub(r"\s+", "", line) for line in block["lines"] if re.fullmatch(r"\s*\d{1,2}\s*[-–:]\s*\d{1,2}\s*", line)), "")
        signature = (event, block["period"], block["matchClock"], norm(team), norm(player), score)
        counts[signature] += 1
        item = {"event": event, "period": block["period"], "matchClock": block["matchClock"], "team": team[:100], "player": player[:100], "score": score[:10], "ordinal": counts[signature]}
        item["eventId"] = incident_id(season, fixture, item)
        item["observedAt"] = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        output.append(item)
    return output

def candidates(catalog, *, now=None):
    now = now or datetime.now(timezone.utc)
    if catalog.get("schema") != "zonaok-partits-total-v1" or not isinstance(catalog.get("matches"), list): raise ValueError("catalog_invalid")
    output, seen = [], Counter()
    rows = [r for r in catalog["matches"] if isinstance(r, dict)]
    for row in rows: seen[(str(row.get("leagueId") or ""), str(row.get("matchId") or ""))] += 1
    for row in rows:
        key = (str(row.get("leagueId") or ""), str(row.get("matchId") or ""))
        if not all(key) or seen[key] != 1 or norm(row.get("competition")) not in COMPETITIONS or norm(row.get("status")) not in LIVE: continue
        try: kickoff = datetime.strptime(row["iso"] + " " + row["time"], "%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
        except (KeyError, ValueError, TypeError): continue
        if not timedelta(0) <= now.astimezone(MADRID) - kickoff <= timedelta(minutes=165): continue
        fixture = {k: row.get(k, "") for k in ("iso", "time", "competition", "home", "away", "leagueId", "matchId", "homeLogo", "awayLogo", "round")}
        if any(not fixture[k] for k in ("iso", "time", "competition", "home", "away", "leagueId", "matchId")): continue
        output.append({"fixture": fixture, "status": row["status"]})
    return output

async def capture_one(browser, match, *, season, started_ids):
    fixture = match["fixture"]
    page = await browser.new_page()
    try:
        response = await page.goto(BASE + "?" + urlencode({"liga": fixture["leagueId"], "vista": "calendar", "partido": fixture["matchId"]}), wait_until="domcontentloaded", timeout=30000)
        if response and response.status in (403, 429, 503): raise RuntimeError("fecapa_http_" + str(response.status))
        await page.wait_for_selector(".sidgad-match-modal .sidgad-roster-table", timeout=18000)
        modal = page.locator(".sidgad-match-modal:visible")
        labels = await modal.locator(".sidgad-modal-status:visible").all_inner_texts()
        if not any(norm(label) in LIVE for label in labels): return None
        tabs = modal.locator(".sidgad-modal-tab-btn:visible")
        names = await tabs.all_inner_texts()
        indices = [i for i, name in enumerate(names) if norm(name) == "INCIDENCIES"]
        if len(indices) != 1: raise RuntimeError("fecapa_incidents_tab_unavailable")
        await tabs.nth(indices[0]).click(timeout=10000)
        previous, stable, text = None, 0, ""
        for _ in range(12):
            text = await modal.inner_text()
            signature = text if "INCIDENCIES" in norm(text) else None
            stable = stable + 1 if signature and signature == previous else 1 if signature else 0
            previous = signature
            if stable >= 3: break
            await page.wait_for_timeout(650)
        if stable < 3: raise RuntimeError("fecapa_incidents_not_stable")
        captured = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        key = str(fixture["leagueId"]) + "|" + str(fixture["matchId"])
        return {"fixture": fixture, "observedAt": captured, "startedNow": key in started_ids, "incidents": parse_incidents(text, fixture, season=season, observed_at=captured)}
    finally: await page.close()

async def capture_selected(selected, *, season, started_ids):
    if not selected: return []
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            results = []
            for match in selected:
                result = await capture_one(browser, match, season=season, started_ids=started_ids)
                if result: results.append(result)
            return results
        finally: await browser.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("candidates", "capture")); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--started", type=Path); parser.add_argument("--season", default="2026/2027")
    args = parser.parse_args(); data = json.loads(args.input.read_text(encoding="utf-8"))
    if args.mode == "candidates": result = {"schema": "zonaok-push-live-candidates-v1", "season": args.season, "matches": candidates(data)}
    else:
        detection = json.loads(args.started.read_text(encoding="utf-8")) if args.started and args.started.exists() else {"events": []}
        started = {str(e.get("fixture", {}).get("leagueId")) + "|" + str(e.get("fixture", {}).get("matchId")) for e in detection.get("events", []) if e.get("event") == "start"}
        matches = asyncio.run(capture_selected(data.get("matches", []), season=args.season, started_ids=started))
        result = {"schema": "zonaok-push-live-incidents-v1", "season": args.season, "matches": matches}
    args.output.write_text(json.dumps(result, ensure_ascii=False) + "\n", encoding="utf-8")

if __name__ == "__main__": main()
