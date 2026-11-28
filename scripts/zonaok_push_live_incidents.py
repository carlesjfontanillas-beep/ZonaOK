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
    values = [season, fixture.get("internalId") or (fixture.get("leagueId") and fixture.get("matchId") and (str(fixture["leagueId"]) + "|" + str(fixture["matchId"]))) or internal_match_id(season, fixture), item["event"], item["period"], item["matchClock"], item["team"], item["player"], item["score"], str(item["ordinal"])]
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

def internal_match_id(season, fixture):
    identity = [season] + [norm(fixture.get(k)) for k in ("iso", "time", "competition", "home", "away")]
    if not all(identity[1:]): return ""
    digest = hashlib.sha256("|".join(identity).encode()).hexdigest()
    return "zonaok:" + digest

def candidates(catalog, *, now=None):
    now = now or datetime.now(timezone.utc)
    if catalog.get("schema") != "zonaok-partits-total-v1" or not isinstance(catalog.get("matches"), list): raise ValueError("catalog_invalid")
    output, seen_internal, official = [], Counter(), Counter()
    rows = [r for r in catalog["matches"] if isinstance(r, dict)]
    for row in rows:
        fixture = {k: row.get(k, "") for k in ("iso", "time", "competition", "home", "away", "leagueId", "matchId", "homeLogo", "awayLogo", "round")}
        ident = internal_match_id(catalog.get("season", ""), fixture)
        pair = (str(row.get("leagueId") or ""), str(row.get("matchId") or ""))
        if all(pair): official[pair] += 1
        elif ident: seen_internal[ident] += 1
    for row in rows:
        if norm(row.get("competition")) not in COMPETITIONS or norm(row.get("status")) not in LIVE: continue
        fixture = {k: row.get(k, "") for k in ("iso", "time", "competition", "home", "away", "leagueId", "matchId", "homeLogo", "awayLogo", "round")}
        ident = internal_match_id(catalog.get("season", ""), fixture)
        pair = (str(row.get("leagueId") or ""), str(row.get("matchId") or ""))
        if not ident or (all(pair) and official[pair] != 1) or (not all(pair) and seen_internal[ident] != 1): continue
        try: kickoff = datetime.strptime(row["iso"] + " " + row["time"], "%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
        except (KeyError, ValueError, TypeError): continue
        if not timedelta(0) <= now.astimezone(MADRID) - kickoff <= timedelta(minutes=165): continue
        fixture["internalId"] = ident
        output.append({"fixture": fixture, "status": row["status"]})
    return output

def official_league_id(fixture):
    if fixture.get("leagueId"): return str(fixture["leagueId"])
    return {"NACIONAL CATALANA MASCULINA": "4774", "NACIONAL CATALANA FEMENINA": "4775"}.get(norm(fixture.get("competition")), "")

async def resolve_match_url(browser, fixture):
    league = official_league_id(fixture)
    if not league: raise RuntimeError("fecapa_league_unresolved")
    if fixture.get("matchId"):
        return BASE + "?" + urlencode({"liga": league, "vista": "calendar", "partido": fixture["matchId"]})
    page = await browser.new_page()
    try:
        await page.goto(BASE + "?" + urlencode({"liga": league, "vista": "calendar"}), wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1800)
        home, away = norm(fixture.get("home")), norm(fixture.get("away"))
        date = datetime.strptime(fixture["iso"], "%Y-%m-%d")
        matches = await page.locator("a[href*='partido=']").evaluate_all("""(anchors, wanted) => {
          const norm = s => (s || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toUpperCase().replace(/\\s+/g,' ').trim();
          const dates = [wanted.dateLong, wanted.dateShort].map(norm);\n          const out = new Set();
          for (const a of anchors) {
            let n=a;
            for (let i=0; i<8 && n; i++, n=n.parentElement) {
              const t=norm(n.innerText);
              if (dates.some(d => t.includes(d)) && t.includes(norm(wanted.home)) && t.includes(norm(wanted.away))) {
                const u=new URL(a.href, location.href), id=u.searchParams.get('partido'), lg=u.searchParams.get('liga');
                if (id && lg===wanted.league) out.add(lg+'|'+id);
                break;
              }
            }
          }
          return [...out];
        }""", {"dateLong":date.strftime("%d/%m/%Y"),"dateShort":date.strftime("%d/%m"),"home":home,"away":away,"league":league})
        if len(matches) != 1: raise RuntimeError("fecapa_fixture_lookup_" + ("missing" if not matches else "ambiguous"))
        lg, mid = matches[0].split("|", 1)
        fixture["leagueId"], fixture["matchId"] = lg, mid
        return BASE + "?" + urlencode({"liga": lg, "vista": "calendar", "partido": mid})
    finally: await page.close()

async def capture_one(browser, match, *, season, started_ids):
    fixture = match["fixture"]
    page = await browser.new_page()
    try:
        match_url = await resolve_match_url(browser, fixture)
        response = await page.goto(match_url, wait_until="domcontentloaded", timeout=30000)
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
        key = fixture.get("internalId") or (str(fixture.get("leagueId") or "") + "|" + str(fixture.get("matchId") or ""))
        return {"fixture": fixture, "observedAt": captured, "startedNow": key in started_ids, "incidents": parse_incidents(text, fixture, season=season, observed_at=captured)}
    finally: await page.close()

async def capture_selected(selected, *, season, started_ids):
    if not selected: return []
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            sem=asyncio.Semaphore(3)
            async def one(match):
                async with sem:
                    try:return await capture_one(browser,match,season=season,started_ids=started_ids)
                    except Exception as exc:
                        print("::warning::Incidències "+str(match.get('fixture',{}).get('matchId'))+": "+str(exc)[:160])
                        return None
            results=await asyncio.gather(*(one(match) for match in selected))
            return [r for r in results if r]
        finally: await browser.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("candidates", "capture")); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--started", type=Path); parser.add_argument("--season", default="2026/2027")
    args = parser.parse_args(); data = json.loads(args.input.read_text(encoding="utf-8"))
    if args.mode == "candidates": result = {"schema": "zonaok-push-live-candidates-v1", "season": args.season, "matches": candidates(data)}
    else:
        detection = json.loads(args.started.read_text(encoding="utf-8")) if args.started and args.started.exists() else {"events": []}
        started = {internal_match_id(args.season, e.get("fixture", {})) or (str(e.get("fixture", {}).get("leagueId") or "") + "|" + str(e.get("fixture", {}).get("matchId") or "")) for e in detection.get("events", []) if e.get("event") == "start"}
        matches = asyncio.run(capture_selected(data.get("matches", []), season=args.season, started_ids=started))
        result = {"schema": "zonaok-push-live-incidents-v1", "season": args.season, "matches": matches}
    args.output.write_text(json.dumps(result, ensure_ascii=False) + "\n", encoding="utf-8")

if __name__ == "__main__": main()
