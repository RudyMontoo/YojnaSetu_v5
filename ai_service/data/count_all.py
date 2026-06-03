"""Final grand count of all schemes across all folders."""
import json
from pathlib import Path

BASE = Path(__file__).parent / "schemes"
grand_total = 0
sector_totals = {}

print("=" * 55)
print("YOJNA SETU — GRAND SCHEME COUNT")
print("=" * 55)

# Count all central + new sector files (root of schemes/)
print("\n📦 CENTRAL SCHEMES (by sector):")
for f in sorted(BASE.glob("*.json")):
    if f.name == "all_schemes.json":
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    schemes = data.get("schemes", [])
    n = len(schemes)
    sector = data.get("sector", f.stem)
    sector_totals[sector] = sector_totals.get(sector, 0) + n
    grand_total += n
    print(f"  {sector:<25} {n:>4} schemes")

# Count state schemes
print("\n🗺️ STATE SCHEMES:")
state_total = 0
for f in sorted((BASE / "states").glob("*.json")):
    if f.name == "all_states.json":
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    n = len(data.get("schemes", []))
    state_total += n
    grand_total += n
    print(f"  {data.get('state_en','?'):<30} {n:>3} schemes")

print(f"\n  TOTAL STATE SCHEMES: {state_total}")
print("\n" + "=" * 55)
print(f"  🏆 GRAND TOTAL: {grand_total} SCHEMES")
print("=" * 55)
