"""
Merge state scheme parts and save as JSON files.
Run: python save_state_schemes.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from state_schemes_part1 import STATE_SCHEMES_PART1
from state_schemes_part2 import STATE_SCHEMES_PART2

ALL_STATE_SCHEMES = {**STATE_SCHEMES_PART1, **STATE_SCHEMES_PART2}

os.makedirs("schemes/states", exist_ok=True)

total = 0
for state_key, state_data in ALL_STATE_SCHEMES.items():
    filepath = f"schemes/states/{state_key}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state_data, f, ensure_ascii=False, indent=2)
    count = len(state_data["schemes"])
    total += count
    print(f"✅ {state_data['state_en']} ({state_data['state_hi']}): {count} schemes → {filepath}")

# Save one combined file
with open("schemes/states/all_states.json", "w", encoding="utf-8") as f:
    json.dump(ALL_STATE_SCHEMES, f, ensure_ascii=False, indent=2)

print(f"\n🎉 Total state schemes: {total} across {len(ALL_STATE_SCHEMES)} states")
print("📁 Saved to: ai_service/data/schemes/states/")
print("\n📊 Summary:")
print(f"   Central schemes : 150 (10 sectors × 15 schemes)")
print(f"   State schemes   : {total} ({len(ALL_STATE_SCHEMES)} states)")
print(f"   GRAND TOTAL     : {150 + total} schemes")
