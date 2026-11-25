#!/usr/bin/env python3
"""Compare public fixture metadata; emit only newly final/available match keys."""
import json,re,subprocess,sys,unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
FINAL=re.compile(r"^(?:final|finalitzat|finalitzada|finalizado|finalizada|acabat|acabado|acabada|finished|full time|completed|acta tancada|acta cerrada)$")
LIVE=re.compile(r"\b(?:en joc|en directe|en juego|en curso|live|playing|in progress|ajornat|aplazado|susp[eè]s|suspendido|cancelado)\b")
def norm(s):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD",str(s or "")) if not unicodedata.combining(c)).lower().split())
def candidates(d,today):
    out={}
    for r in d.get("matches",[]):
        l,m=str(r.get("leagueId") or ""),str(r.get("matchId") or "")
        status=norm(r.get("status"));iso=r.get("iso","")
        if not re.fullmatch(r"[1-9]\d*",l) or not re.fullmatch(r"[1-9]\d*",m) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",iso or "") or iso>today:continue
        if LIVE.search(status) or not all(type(r.get(k)) is int and r[k]>=0 for k in ("homeScore","awayScore")):continue
        if not FINAL.fullmatch(status) and r.get("actaState")!="available":continue
        out[l+"|"+m]=[r["homeScore"],r["awayScore"],bool(FINAL.fullmatch(status)),r.get("actaState")=="available"]
    return out
def read(ref):
    if not re.fullmatch(r"[a-f0-9]{40}",ref):raise ValueError("invalid_ref")
    return json.loads(subprocess.check_output(["git","show",ref+":zonaok-tots-partits.json"],text=True))
if __name__=="__main__":
    today=datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    before=candidates(read(sys.argv[1]),today);after=candidates(read(sys.argv[2]),today)
    changed=sorted(k for k,v in after.items() if before.get(k)!=v)
    print(json.dumps({"event_type":"zonaok-match-finished","client_payload":{"matches":changed}}))
