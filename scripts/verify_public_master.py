import sys
from pathlib import Path
from zonaok_jugadors_auto import load, verify_master

p = Path(sys.argv[1])
d = load(p, "41")
verify_master(d)
if not d["players"] or not d["matchAppearances"]:
    raise SystemExit("Master buit o incomplet")
if p.stat().st_size > 90_000_000:
    raise SystemExit("Límit preventiu de mida superat")
print("Master verificat", len(d["players"]), len(d["memberships"]), len(d["matchAppearances"]))
