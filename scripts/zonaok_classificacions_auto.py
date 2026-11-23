#!/usr/bin/env python3
"""ZonaOK · Classificacions totals des de FECAPA amb Playwright.

Aquest script NO altera l'Agenda, En directe ni les actes.

Fases separades:
  collect --limit N : captura i diagnòstic (cap fitxer publicat)
  merge --input X --output Y : fusió conservadora i validació; només Y canvia

Per defecte, el workflow GitHub fa només DRY RUN i adjunta els resultats.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = "https://www.hoqueipatins.fecapa.cat/"
ALLOWED_HOSTS = {"hoqueipatins.fecapa.cat", "www.hoqueipatins.fecapa.cat"}
# Referències oficials de competicions conegudes; NO equival a un catàleg exhaustiu.
SEEDS = ("4789", "4786", "4784", "4822", "4823", "4824", "4825", "5082")
MAX_DISCOVERED = 250
LEAGUE_RX = re.compile(r"(?i)(?:[?&]|%3[fF]|%26)liga(?:=|%3[dD])(\d{4,6})(?!\d)")
ID_RX = re.compile(r"\d{4,6}")


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()


def norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", "".join(c for c in unicodedata.normalize("NFD", clean(value)) if unicodedata.category(c) != "Mn").upper()).strip()


def slug(value: object) -> str:
    return norm(value).lower().replace(" ", "-")


def category_name(name: str) -> str:
    return re.sub(r"\s+GRUP\s+[A-Z0-9]+\b", "", re.sub(r"\s+(?:OR|PLATA|BRONZE)\s+\d+\b", "", name, flags=re.I), flags=re.I).strip()


def competition_name(name: str) -> str:
    return re.sub(r"\s+GRUP\s+[A-Z0-9]+\b", "", re.sub(r"\s+(OR|PLATA|BRONZE)\s+\d+\b", r" \1", name, flags=re.I), flags=re.I).strip()


def league_from_url(value: str) -> str | None:
    try:
        u = urlparse(value)
        if u.hostname not in ALLOWED_HOSTS:
            return None
        val = parse_qs(u.query).get("liga", [""])[0]
        return val if ID_RX.fullmatch(val) else None
    except ValueError:
        return None


# La mateixa lògica de lectura i desplaçament de la drecera V5 (ara navegador real).
# Cada grup es rebutja sencer si una fila és inconsistent.
JS_EXTRACT = r"""() => {
  const clean = x => String(x ?? '').replace(/\s+/g, ' ').trim();
  const norm = x => clean(x).normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim();
  const number = x => /^-?\d+$/.test(clean(x));
  const result = {groups: [], errors: []};
  for (const h of document.querySelectorAll('h1,h2,h3,h4')) {
    const name = clean(h.innerText || h.textContent);
    if (!name || name.length > 100 || name.includes('|') ||
        /\b20\d{2}(?:\/20\d{2})?\b/.test(name)) continue;
    let table = null, node = h;
    for (let i=0; i<5 && node && !table; i++, node=node.nextElementSibling) {
      table = node.matches?.('table') ? node :
        node.querySelector?.('table.sidgad-clasif-tabla,table');
    }
    if (!table) table = h.parentElement?.querySelector('table.sidgad-clasif-tabla');
    if (!table) continue;
    const headers = [...table.querySelectorAll('thead th')]
      .map(c => norm(c.innerText || c.textContent));
    const idx = (...keys) => headers.findIndex(v => keys.includes(v));
    const col = {
      pts: idx('PTS','PUNTS'), pj: idx('PJ','PARTITS JUGATS'),
      pg: idx('PG'), pe: idx('PE'), pp: idx('PP'),
      gf: idx('GF','GOLS A FAVOR'), gc: idx('GC','GOLS EN CONTRA'),
      dif: idx('DIF','DIFERENCIA','DIFERENCIA DE GOLS','AVG'), san:idx('SAN')
    };
    if (['pts','pj','pg','pe','pp','gf','gc','dif'].some(k=>col[k]<0)) continue;
    const rows=[]; let invalid=false;
    for (const tr of table.querySelectorAll('tbody tr')) {
      const cells = [...tr.cells];
      const cell=i=>i<0?'':clean(cells[i]?.innerText||cells[i]?.textContent||'');
      const pos=cell(0);
      const team=clean(tr.querySelector('.sidgad-clasif-nombre')?.textContent)||cell(1);
      if (!/^\d{1,2}$/.test(pos)||!team) continue;
      const shifts=[...new Set([cells.length-headers.length,1,0,2,3])]
        .filter(n=>n>=0&&n<=3);
      let shift=null;
      for (const n of shifts) {
        const val=k=>cell(col[k]+n);
        if (!['pts','pj','pg','pe','pp','gf','gc','dif'].every(k=>number(val(k)))) continue;
        if (+val('pg') + +val('pe') + +val('pp') !== +val('pj')) continue;
        if (+val('gf') - +val('gc') !== +val('dif')) continue;
        shift=n;break;
      }
      if (shift===null) {
        invalid=true;result.errors.push(`${name}: ${team} té columnes incoherents`);break;
      }
      const val=k=>col[k]<0?'':cell(col[k]+shift);
      const stats={};
      headers.forEach((k,i)=>{const v=cell(i+shift);if(k&&v)stats[k]=v;});
      rows.push({pos,team,played:val('pj'),points:val('pts'),
        gf:val('gf'),ga:val('gc'),difference:val('dif'),stats});
    }
    if (!invalid&&rows.length>=2&&rows.length<=50&&
        new Set(rows.map(r=>norm(r.team))).size===rows.length) {
      result.groups.push({name,rows});
    }
  }
  return result;
}"""

JS_DISCOVER = r"""() => {
  const ids=new Set(),sources=[];
  const add=(v,source)=>{
    if(/^\d{4,6}$/.test(String(v||'')) && !['2026','2027','2028'].includes(String(v))) {
      ids.add(String(v));sources.push([String(v),source]);
    }
  };
  const fromUrl=(s,source)=>{
    try {const u=new URL(s,location.href);
      if(!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname))return;
      add(u.searchParams.get('liga'),source);
    }catch(_){}
  };
  fromUrl(location.href,'pagina');
  const html=document.documentElement.outerHTML;
  for (const m of html.matchAll(/[?&]liga(?:%3D|=)(\d{4,6})/gi))add(m[1],'HTML');
  document.querySelectorAll('a[href], [data-liga], [data-id-liga], [data-league-id], [data-id-competicion]').forEach(el=>{
    fromUrl(el.getAttribute('href')||'', 'enllac');
    for(const attr of ['data-liga','data-id-liga','data-league-id','data-id-competicion'])
      add(el.getAttribute(attr),attr);
  });
  document.querySelectorAll('select').forEach(select=>{
    const label=((select.id||'')+' '+(select.name||'')+' '+
       (select.getAttribute('aria-label')||'')).toLowerCase();
    for(const opt of select.querySelectorAll('option')){
      fromUrl(opt.value,'option-url');
      if(/liga|league|competi/.test(label))add(opt.value,'selector-competicio');
    }
  });
  return {ids:[...ids],sources:sources.slice(0,1000)};
}"""


class Discovery:
    def __init__(self) -> None:
        self.ids: dict[str, set[str]] = {}
        self.responses = []
        self.network_tasks = []

    def add(self, value: object, source: str) -> None:
        val = clean(value)
        if ID_RX.fullmatch(val) and val not in {"2026", "2027", "2028"}:
            self.ids.setdefault(val, set()).add(source)

    def urls_from_text(self, text: str, source: str) -> None:
        for match in LEAGUE_RX.finditer(text):
            self.add(match.group(1), source)

    def from_json(self, value: object, source: str, depth: int = 0) -> None:
        if depth > 7:
            return
        if isinstance(value, dict):
            for k, v in value.items():
                key = norm(k).replace(" ", "_")
                if key in {"LIGA", "ID_LIGA", "LEAGUE", "LEAGUE_ID", "ID_COMPETICION", "ID_COMPETICIO", "COMPETITION_ID", "ID_COMPETITION"}:
                    self.add(v, source + ":" + key)
                if isinstance(v, str) and len(v) < 25000:
                    self.urls_from_text(v, source)
                elif isinstance(v, (dict, list)):
                    self.from_json(v, source, depth+1)
        elif isinstance(value, list):
            for v in value[:2000]:
                self.from_json(v, source, depth+1)

    async def inspect_response(self, response) -> None:
        try:
            url = response.url
            if not any(x in urlparse(url).hostname or "" for x in ["fecapa.cat", "sidgad"]):
                return
            self.urls_from_text(url, "URL-XHR")
            typ = response.headers.get("content-type", "").lower()
            if "json" not in typ and "html" not in typ and "javascript" not in typ:
                return
            raw = await response.body()
            if len(raw) > 1_200_000:
                return
            body = raw.decode("utf-8", errors="replace")
            self.urls_from_text(body, "XHR-HTML")
            if "json" in typ:
                try: self.from_json(json.loads(body), "XHR-JSON")
                except json.JSONDecodeError: pass
        except Exception:
            return

    def attach(self, page) -> None:
        page.on("response", lambda resp: self.network_tasks.append(asyncio.create_task(self.inspect_response(resp))))

    async def gather_network(self) -> None:
        if self.network_tasks:
            await asyncio.gather(*self.network_tasks, return_exceptions=True)
            self.network_tasks.clear()

    async def gather_page(self, page, source: str) -> None:
        try:
            info = await page.evaluate(JS_DISCOVER)
            for league in info.get("ids", []): self.add(league, source)
            for league, place in info.get("sources", []): self.add(league, source+":"+place)
        except Exception:
            pass


async def collect(args) -> dict:
    from playwright.async_api import async_playwright

    diag = {"source": "FECAPA-PLAYWRIGHT", "checkedAt": datetime.now(timezone.utc).isoformat(),
            "discovery": [], "found": [], "failed": [], "warnings": [], "mode": "navegador-grafic-headful"}
    data = {}
    discover = Discovery()
    for league in SEEDS: discover.add(league, "referencia-coneguda")
    existing = Path(args.existing)
    if existing.exists():
        try:
            doc = json.loads(existing.read_text(encoding="utf-8"))
            for obj in doc.get("competitions", {}).values():
                if isinstance(obj, dict): discover.add(obj.get("leagueId"), "json-existent")
        except (ValueError, OSError, AttributeError):
            diag["warnings"].append("No es pot llegir el JSON existent per ampliar les llavors")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        context = await browser.new_context(locale="ca-ES", timezone_id="Europe/Madrid",
                                            viewport={"width":1360,"height":980},
                                            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        context.set_default_timeout(12000)
        page = await context.new_page()
        discover.attach(page)
        for url in [ROOT, ROOT+"?vista=clasificaciones", ROOT+"?vista=classificacions"]:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(1800)
                await discover.gather_page(page,"cataleg")
                # A FECAPA el botó LEAGUES pot mostrar el selector de les lligues.
                for label in ["LEAGUES", "LLIGUES", "COMPETICIONES", "COMPETICIONS"]:
                    btn = page.get_by_role("button", name=re.compile("^"+label+"$", re.I))
                    if await btn.count():
                        try:
                            await btn.first.click(timeout=2500)
                            await page.wait_for_timeout(1000)
                            await discover.gather_page(page,"cataleg-boto")
                        except Exception:
                            pass
                        break
            except Exception as exc:
                diag["warnings"].append("Catàleg inaccessible " + url + ": " + str(exc)[:160])
        await discover.gather_network()
        ids = sorted(discover.ids, key=lambda x:int(x))
        if len(ids) > MAX_DISCOVERED:
            diag["warnings"].append(f"Descoberts {len(ids)} possibles IDs; s'aplica límit {MAX_DISCOVERED}")
            ids = ids[:MAX_DISCOVERED]
        diag["discovery"] = [{"leagueId":i,"sources":sorted(discover.ids[i])} for i in ids]
        if args.limit:
            # Posar les conegudes primer facilita una comprovació ràpida de la 4789.
            priority = [x for x in SEEDS if x in ids]
            ids = (priority+[x for x in ids if x not in priority])[:args.limit]
        for ix, league in enumerate(ids, 1):
            url = ROOT + "?" + urlencode({"liga":league,"vista":"clasificaciones"})
            success = False
            groups = []
            last_error = "cap taula de classificació llegible"
            for attempt in range(2):
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    try:
                        await page.wait_for_function(
                            "document.querySelector('table.sidgad-clasif-tabla, table') !== null",
                            timeout=10000)
                    except Exception: pass
                    await page.wait_for_timeout(700)
                    result = await page.evaluate(JS_EXTRACT)
                    groups = result.get("groups",[])
                    if not groups:
                        last_error = "; ".join(result.get("errors",[])[:2]) or last_error
                        continue
                    for group in groups:
                        name = clean(group["name"])
                        key = league+":"+slug(name)
                        item = {"name":name, "category":category_name(name),
                                "competition":competition_name(name),"leagueId":league,
                                "url":url,"rows":group["rows"]}
                        if key in data and data[key] != item:
                            raise ValueError("Clau duplicada amb dades diferents: "+key)
                        data[key] = item
                    diag["found"].append({"leagueId":league,"groups":len(groups),
                                          "teams":sum(len(g["rows"]) for g in groups),
                                          "warnings":result.get("errors",[])[:10]})
                    success = True
                    break
                except Exception as exc:
                    last_error = str(exc)[:180]
                if attempt == 0:
                    await page.wait_for_timeout(1000)
            if not success:
                diag["failed"].append({"leagueId":league,"error":last_error})
            print(f"[{ix}/{len(ids)}] Lliga {league}: "+
                  (f"{len(groups)} grups" if success else f"sense dades ({last_error})"),flush=True)
        await browser.close()

    diag["stats"] = {"discoveredLeagues":len(diag["discovery"]),
                     "checkedLeagues":len(ids),"validLeagues":len(diag["found"]),
                     "failedLeagues":len(diag["failed"]),"groups":len(data),
                     "teams":sum(len(g["rows"]) for g in data.values())}
    now = datetime.now(timezone.utc).isoformat()
    return {"packet":{"source":"FECAPA-SAFARI", "version":3,
                       "kind":"classificacions-total", "capturedAt":now,
                       "competitions":data},"diagnostic":diag}


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str): return None
    try:
        date = datetime.fromisoformat(value.replace("Z","+00:00"))
        return date.astimezone(timezone.utc) if date.tzinfo else None
    except ValueError: return None


def check_row(row: dict) -> None:
    if not isinstance(row,dict) or not clean(row.get("team")):
        raise ValueError("Fila sense equip")
    stats=row.get("stats") or {}
    def num(key, alias):
        value=clean(row.get(key) if key else stats.get(alias))
        if not re.fullmatch(r"-?\d+",value):
            raise ValueError("Camp numèric absent: "+(key or alias))
        return int(value)
    played=num("played", "PJ")
    gf=num("gf", "GF")
    ga=num("ga", "GC")
    diff=num("difference", "DIF")
    num("points", "PTS")
    wins = num(None,"PG");ties=num(None,"PE");loss=num(None,"PP")
    if played != wins+ties+loss or gf-ga != diff:
        raise ValueError("Estadístiques incoherents per a "+clean(row.get("team")))


def merge_packet(capture: dict, existing: dict) -> tuple[dict,dict]:
    packet = capture.get("packet", capture)
    if packet.get("source") != "FECAPA-SAFARI" or packet.get("kind") != "classificacions-total":
        raise ValueError("Format de captura incompatible")
    when=parse_time(packet.get("capturedAt"))
    if not when: raise ValueError("Data de captura invàlida")
    incoming=packet.get("competitions")
    if not isinstance(incoming,dict) or not incoming:
        raise ValueError("Captura sense classificacions: no es publica res")
    if existing and existing.get("schema") not in ("zonaok-classificacions-v1", "zonaok-classificacions-v2"):
        raise ValueError("Esquema antic desconegut: no es modifica res")
    old=existing.get("competitions",existing.get("leagues",{}))
    if not isinstance(old,dict):raise ValueError("Classificacions existents mal formades")
    output=dict(old)
    updated=preserved=0
    for key,item in incoming.items():
        if not re.fullmatch(r"\d{4,6}:[a-z0-9_-]{2,140}",key):
            raise ValueError("Clau de grup invàlida: "+str(key))
        if not isinstance(item,dict) or str(item.get("leagueId")) != key.split(":")[0]:
            raise ValueError("Grup incompatible amb ID: "+key)
        rows=item.get("rows")
        if not isinstance(rows,list) or not 2<=len(rows)<=50:
            raise ValueError("Grup incomplet: "+key)
        teams=set()
        for row in rows:
            check_row(row)
            identity=norm(row["team"])
            if identity in teams: raise ValueError("Equip repetit al grup: "+key)
            teams.add(identity)
        prior=old.get(key)
        previous_time=parse_time(prior.get("standingsAt") or prior.get("capturedAt")) if isinstance(prior,dict) else None
        if previous_time and previous_time>=when:
            preserved += 1
            continue
        output[key]={"name":clean(item.get("name"))[:100],
                     "category":clean(item.get("category"))[:100],
                     "competition":clean(item.get("competition"))[:100],
                     "leagueId":str(item["leagueId"]),
                     "capturedAt":packet["capturedAt"],"standingsAt":packet["capturedAt"],
                     "url":clean(item.get("url"))[:500],
                     "standings":rows}
        updated += 1
    # REGLE: mai eliminar claus que no hagin vingut al lot, encara que
    # una altra lliga contingui un grup amb el mateix nom.
    result={"schema":"zonaok-classificacions-v2",
            "capturedAt": packet["capturedAt"] if updated else existing.get("capturedAt",packet["capturedAt"]),
            "competitions":dict(sorted(output.items()))}
    stats={"updatedGroups":updated,"preservedNewer":preserved,
           "preservedByKey":len(old.keys()-incoming.keys()),"totalGroups":len(output),
           "totalTeams":sum(len(v.get("standings",[])) for v in output.values() if isinstance(v,dict))}
    return result,stats


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("collect",help="Captura DOM de classificacions amb Playwright, sense publicar")
    a.add_argument("--existing",default="zonaok-classificacions.json")
    a.add_argument("--limit",type=int,default=3,help="0 per comprovar totes les lligues descobertes")
    a.add_argument("--capture",default="captura-classificacions.json")
    a.add_argument("--report",default="diagnostic-classificacions.json")
    b=sub.add_parser("merge",help="Fusió conservadora de captura i classificacions existents")
    b.add_argument("--capture",default="captura-classificacions.json")
    b.add_argument("--existing",default="zonaok-classificacions.json")
    b.add_argument("--output",required=True)
    b.add_argument("--report",default="diagnostic-fusio.json")
    args=parser.parse_args()
    if args.cmd=="collect":
        if args.limit<0:parser.error("--limit ha de ser >=0")
        result=asyncio.run(collect(args))
        Path(args.capture).write_text(json.dumps(result["packet"],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        Path(args.report).write_text(json.dumps(result["diagnostic"],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("RESUM",json.dumps(result["diagnostic"]["stats"],ensure_ascii=False))
        # Un catàleg inaccessible s'ha de veure com a error, no com a execució satisfactòria.
        return 0 if result["packet"]["competitions"] else 2
    capture=json.loads(Path(args.capture).read_text(encoding="utf-8"))
    existing_path=Path(args.existing)
    existing=json.loads(existing_path.read_text(encoding="utf-8")) if existing_path.exists() else {}
    result,diag=merge_packet(capture,existing)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(args.report).write_text(json.dumps(diag,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FUSIÓ",json.dumps(diag,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:sys.exit("ERROR: no s'ha escrit cap JSON publicat: "+str(exc))
