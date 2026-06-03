"""
Reorganize state schemes from state-wise → sector-wise JSON files.
Also creates combined (central + state) sector files.
Run: python reorganize_by_sector.py
"""
import json, os
from pathlib import Path

BASE = Path(__file__).parent
STATES_DIR = BASE / "schemes" / "states"
SECTOR_OUT = BASE / "schemes" / "state_by_sector"
COMBINED_OUT = BASE / "schemes" / "combined"

SECTOR_OUT.mkdir(exist_ok=True)
COMBINED_OUT.mkdir(exist_ok=True)

# ── 1. Load all state schemes and group by sector ─────────────────────────
sector_map = {}  # sector -> list of scheme dicts (with state info appended)

for state_file in STATES_DIR.glob("*.json"):
    if state_file.name == "all_states.json":
        continue
    with open(state_file, encoding="utf-8") as f:
        state_data = json.load(f)

    state_en = state_data["state_en"]
    state_hi = state_data["state_hi"]

    for scheme in state_data["schemes"]:
        sector = scheme.get("sector", "other")
        scheme_copy = dict(scheme)
        scheme_copy["state_en"] = state_en
        scheme_copy["state_hi"] = state_hi
        scheme_copy["type"] = "State"
        sector_map.setdefault(sector, []).append(scheme_copy)

# ── 2. Save state-only sector files ─────────────────────────────────────────
print("=== State Schemes (Sector-wise) ===")
for sector, schemes in sorted(sector_map.items()):
    out_path = SECTOR_OUT / f"{sector}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"sector": sector, "type": "state", "count": len(schemes), "schemes": schemes},
                  f, ensure_ascii=False, indent=2)
    print(f"✅ {sector}: {len(schemes)} state schemes → {out_path.name}")

# ── 3. Load central schemes and merge into combined sector files ──────────────
print("\n=== Combined (Central + State) Sector Files ===")
CENTRAL_DIR = BASE / "schemes"
all_sectors = set(sector_map.keys())

# Read all central sector jsons
for central_file in CENTRAL_DIR.glob("*.json"):
    if central_file.name == "all_schemes.json":
        continue
    with open(central_file, encoding="utf-8") as f:
        central_data = json.load(f)
    sector = central_data.get("sector")
    if not sector:
        continue
    all_sectors.add(sector)
    central_schemes = central_data.get("schemes", [])
    state_schemes = sector_map.get(sector, [])

    combined = {
        "sector": sector,
        "central_count": len(central_schemes),
        "state_count": len(state_schemes),
        "total": len(central_schemes) + len(state_schemes),
        "central_schemes": central_schemes,
        "state_schemes": state_schemes,
    }
    out_path = COMBINED_OUT / f"{sector}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"✅ {sector}: {len(central_schemes)} central + {len(state_schemes)} state = {combined['total']} total")

print(f"\n📁 State-by-sector files → schemes/state_by_sector/")
print(f"📁 Combined files       → schemes/combined/")
