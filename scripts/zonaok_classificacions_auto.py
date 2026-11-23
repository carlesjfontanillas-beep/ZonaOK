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
# Competicions amb URL oficial FECAPA coneguda. No és un inventari complet.
# Les dues primeres són importants per provar les fallades de V2.
SEEDS = ("4789", "4786", "4784", "4822", "4823", "4824", "4825", "5082",
         "4774", "4775", "4776", "4782", "4808", "4856")
MAX_DISCOVERED = 300
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
  const ids=new Set(), sources=[];
  const add=(value,source)=>{
    const v=String(value??'').trim();
    if(/^\d{4,6}$/.test(v) && !['2026','2027','2028'].includes(v)) {
      ids.add(v);sources.push([v,source]);
    }
  };
  const fromUrl=(value,source)=>{
    try {
      const u=new URL(value,location.href);
      if(!/^(?:www\.)?hoqueipatins\.fecapa\.cat$/i.test(u.hostname))return;
      add(u.searchParams.get('liga'),source);
    }catch(_){}
  };
  fromUrl(location.href,'pagina');
  const html=document.documentElement.outerHTML;
  for (const m of html.matchAll(/[?&]liga(?:%3[Dd]|=)(\d{4,6})/gi)) add(m[1],'HTML');
  document.querySelectorAll('a[href], [data-liga], [data-id-liga], [data-league-id], [data-id-competicion], [onclick]').forEach(el=>{
    fromUrl(el.getAttribute('href')||'', 'enllac');
    for(const attr of [...el.attributes]) {
      if(/liga|league|competici/i.test(attr.name)){
        add(attr.value, 'atribut:'+attr.name);
        fromUrl(attr.value,'atribut-url:'+attr.name);
        for(const m of attr.value.matchAll(/(?:liga|league)(?:_id|Id)?\D{0,8}(\d{4,6})/gi))add(m[1],'atribut:'+attr.name);
      }
    }
  });
  document.querySelectorAll('select').forEach(select=>{
    const label=((select.id||'')+' '+(select.name||'')+' '+(select.getAttribute('aria-label')||'')).toLowerCase();
    for(const opt of select.querySelectorAll('option')){
      fromUrl(opt.value,'option-url');
      if(/liga|league|competi/.test(label))add(opt.value,'selector-competicio');
    }
  });
  // Competitions can appear inside inline JS / JSON script nodes.
  for(const el of document.querySelectorAll('script:not([src])')){
    const body=el.textContent||'';
    if(body.length>300000)continue;
    for(const m of body.matchAll(/(?:[?&]liga=|["'](?:id_liga|league_id|liga)["']\s*:\s*["']?)(\d{4,6})/gi)) add(m[1],'script');
  }
  return {ids:[...ids],sources:sources.slice(0,2000)};
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

    def from_json(self, value: object, source: str, depth: int = 0, parent: str = "") -> None:
        if depth > 9:
            return
        if isinstance(value, dict):
            for key, val in value.items():
                field = norm(key).replace(" ", "_")
                if field in {"LIGA", "ID_LIGA", "LEAGUE", "LEAGUE_ID", "ID_COMPETICION", "ID_COMPETICIO", "COMPETITION_ID", "ID_COMPETITION"}:
                    self.add(val, source+":"+field)
                # Generic ID is safe only inside an explicitly named league collection.
                if field in {"ID", "IDENTIFICADOR"} and re.search(r"LIGA|LEAGUE|COMPETI", parent):
                    self.add(val, source+":ID-DINS-LLIGUES")
                if isinstance(val, str) and len(val) < 350000:
                    self.urls_from_text(val,source)
                elif isinstance(val, (dict, list)):
                    self.from_json(val, source, depth+1, field)
        elif isinstance(value, list):
            for item in value[:5000]:
                self.from_json(item,source,depth+1,parent)

    async def inspect_response(self, response) -> None:
        try:
            url = response.url
            host = (urlparse(url).hostname or "").lower()
            if not (host.endswith("fecapa.cat") or host.endswith("sidgad.es") or host.endswith("sidgad.cloud")):
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


async def inspect_catalogue(page, discover: Discovery, diagnostic: dict, location: str) -> None:
    """Discover from the *rendered* catalogue; no raw HTTP scraping required."""
    try:
        await page.goto(location, wait_until="domcontentloaded", timeout=28000)
        await page.wait_for_timeout(1700)
        await discover.gather_page(page,"cataleg:"+location)
        # A visible league/category menu is often a link rather than a button.
        for pattern in (r"^(?:LEAGUES|LLIGUES)$", r"^(?:COMPETITIONS|COMPETICIONS|COMPETICIONES)$"):
            for role in ("button", "link"):
                choices=page.get_by_role(role,name=re.compile(pattern,re.I))
                if await choices.count():
                    try:
                        await choices.first.click(timeout=2000)
                        await page.wait_for_timeout(850)
                        await discover.gather_page(page,"cataleg-menu:"+location)
                    except Exception:
                        pass
        # Read any selectors that are dynamically populated after opening the catalogue.
        await discover.gather_page(page,"cataleg-final:"+location)
    except Exception as exc:
        diagnostic["warnings"].append("Catàleg no llegible "+location+": "+str(exc)[:150])


async def read_league(context, league: str, expected_groups: int, max_tries: int = 3) -> tuple[list, list, list]:
    """One fresh tab per attempt prevents stale DOM from the previous league.

    We poll for VALID rows, not the existence of a placeholder table. A stable
    group/row signature over consecutive polls avoids prematurely reading XHR.
    """
    url=ROOT+"?"+urlencode({"liga":league,"vista":"clasificaciones"})
    errors=[]
    warnings=[]
    best=[]
    for attempt in range(1,max_tries+1):
        page=await context.new_page()
        page.set_default_timeout(12000)
        try:
            await page.goto(url,wait_until="domcontentloaded",timeout=30000)
            # The page often renders a blank classification component then fills
            # it asynchronously. Poll for fully parsed rows, not table existence.
            stable=0
            signature=None
            latest=[]
            for poll in range(24):
                await page.wait_for_timeout(650)
                result=await page.evaluate(JS_EXTRACT)
                groups=result.get("groups",[])
                if len(groups)>len(best):best=groups
                err=result.get("errors",[])
                if groups:
                    current=tuple(sorted((g["name"],len(g["rows"])) for g in groups))
                    stable=stable+1 if signature==current else 1
                    signature=current
                    latest=groups
                    if len(groups)>=max(1,expected_groups) and stable>=3:
                        return groups, errors, warnings+err[:5]
                if poll==23:
                    errors.append(f"Intent {attempt}: {len(groups)} grups; esperats >= {max(1,expected_groups)}"+
                                  ("; "+"; ".join(err[:2]) if err else ""))
            # On a newly discovered league, a single valid group can be genuine.
            if latest and not expected_groups and stable>=3:
                return latest, errors, warnings
            if best and len(best)>=expected_groups and expected_groups>0:
                # It may have loaded at the deadline; do not discard consistent rows.
                return best, errors, warnings
        except Exception as exc:
            errors.append(f"Intent {attempt}: {str(exc)[:180]}")
        finally:
            await page.close()
        if attempt<max_tries:
            await asyncio.sleep(min(2,attempt))
    return [],errors,warnings


async def collect(args) -> dict:
    from playwright.async_api import async_playwright
    diag={"source":"FECAPA-PLAYWRIGHT","checkedAt":datetime.now(timezone.utc).isoformat(),
          "discovery":[],"found":[],"failed":[],"warnings":[],
          "mode":"navegador-grafic-headful", "version":3}
    data={}
    discover=Discovery()
    existing_groups={}
    existing=Path(args.existing)
    for league in SEEDS: discover.add(league,"referencia-coneguda")
    if existing.exists():
        try:
            doc=json.loads(existing.read_text(encoding="utf-8"))
            if isinstance(doc.get("competitions"),dict):
                existing_groups=doc["competitions"]
                for obj in existing_groups.values():
                    if isinstance(obj,dict):discover.add(obj.get("leagueId"),"json-existent")
        except (ValueError,OSError,AttributeError):
            diag["warnings"].append("El JSON existent no es pot llegir com a font de IDs")

    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=False,args=["--no-sandbox"])
        context=await browser.new_context(locale="ca-ES",timezone_id="Europe/Madrid",
                                          viewport={"width":1360,"height":980})
        discover_page=await context.new_page()
        discover.attach(discover_page)
        for url in [ROOT,ROOT+"?vista=clasificaciones",ROOT+"?vista=classificacions",ROOT+"ag/"]:
            await inspect_catalogue(discover_page, discover, diag, url)
        await discover.gather_network()
        await discover_page.close()

        ids=sorted(discover.ids,key=lambda x:int(x))
        if len(ids)>MAX_DISCOVERED:
            diag["warnings"].append(f"{len(ids)} IDs possibles, límit de seguretat {MAX_DISCOVERED}")
            ids=ids[:MAX_DISCOVERED]
        diag["discovery"]=[{"leagueId":value,"sources":sorted(discover.ids[value])} for value in ids]
        if args.limit:
            priority=[v for v in SEEDS if v in ids]
            ids=(priority+[v for v in ids if v not in priority])[:args.limit]

        for ix,league in enumerate(ids,1):
            expected=sum(1 for value in existing_groups.values()
                         if isinstance(value,dict) and str(value.get("leagueId"))==league)
            groups, errors, warnings=await read_league(context,league,expected)
            if groups:
                url=ROOT+"?"+urlencode({"liga":league,"vista":"clasificaciones"})
                for g in groups:
                    name=clean(g["name"])
                    key=league+":"+slug(name)
                    data[key]={"name":name,"category":category_name(name),
                               "competition":competition_name(name),"leagueId":league,
                               "url":url,"rows":g["rows"]}
                diag["found"].append({"leagueId":league,"groups":len(groups),
                                      "teams":sum(len(g["rows"]) for g in groups),
                                      "expectedFromPrevious":expected,
                                      "warnings":warnings+errors[:3]})
            else:
                diag["failed"].append({"leagueId":league,"expectedFromPrevious":expected,
                                       "error":"; ".join(errors[-3:]) or "Cap grup vàlid"})
            print(f"[{ix}/{len(ids)}] Lliga {league}: "+
                  (f"{len(groups)} grups" if groups else "sense taules completes"),flush=True)
        await context.close()
        await browser.close()
    diag["stats"]={"discoveredLeagues":len(diag["discovery"]),"checkedLeagues":len(ids),
                   "validLeagues":len(diag["found"]),"failedLeagues":len(diag["failed"]),
                   "groups":len(data),"teams":sum(len(v["rows"]) for v in data.values())}
    if len(diag["discovery"])<25:
        diag["warnings"].append("Descobriment encara incomplet: menys de 25 lligues; no afirmar cobertura total")
    now=datetime.now(timezone.utc).isoformat()
    return {"packet":{"source":"FECAPA-SAFARI","version":3,
                      "kind":"classificacions-total","capturedAt":now,"competitions":data},
            "diagnostic":diag}


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
