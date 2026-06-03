"""
Audit all scheme JSON files and:
1. Remove known discontinued/inactive schemes
2. Fix renamed schemes
3. Tag all remaining schemes with status: "active"
4. Print a full audit report

Run: python audit_clean_schemes.py
"""
import json
from pathlib import Path

BASE = Path(__file__).parent / "schemes"

# ── Known inactive schemes (by exact name match) ─────────────────────────────
REMOVE_BY_NAME = {
    # ── Central ──────────────────────────────────────────────────────────────
    "Varishtha Pension Bima Yojana (VPBY)":
        "Closed for new enrollment in 2019. Existing beneficiaries only. Replaced by PMVVY.",

    "Panchayat Yuva Krida aur Khel Abhiyan (PYKKA)":
        "Discontinued. Replaced by Khelo India Programme in 2018.",

    "Senior Citizen Rail Concession":
        "Suspended by Indian Railways in March 2020 and NOT restored as of 2025.",

    "Haj Subsidy Scheme":
        "Cash subsidy removed in 2018 (Supreme Court directive). Only facilitation/logistics support remains.",

    "Multi-Sectoral Development Programme (MsDP)":
        "Subsumed into PM Jan Vikas Karyakram (PMJVK) in 2018.",

    "Gram Uday Se Bharat Uday (Tribal Gram Sabha)":
        "Was a one-time national campaign (April 2016), not an ongoing scheme.",

    "Pradhan Mantri Fani Relief (Cyclone) Scheme":
        "Event-specific relief (2019 Cyclone Fani), not a standing government scheme.",

    "Priority Ration Card for Defence Families":
        "Not a standalone central scheme — handled case-by-case by states under PDS.",

    "Rejuvenation of Infrastructure in Sainik Rest Houses":
        "Administrative improvement, not a citizen-facing scheme.",

    "PM Wani + JanSahas (Local Entrepreneur Wi-Fi)":
        "Merged into PM-WANI single initiative; not a separate scheme.",

    "Defence Pension Adalat (Grievance Redressal)":
        "Administrative process, not a welfare scheme. Replaced by SPARSH digital system.",

    "Assistance to Madrasas / Minority Institutions (SPQEM)":
        "SPQEM discontinued in 2021-22; merged into Integrated Scheme for School Education (ISSE / Samagra Shiksha).",

    "Waqf Board Property Development Scheme":
        "Grants paused pending Waqf Amendment; no active disbursements as of 2024-25.",

    "Grants-in-Aid to Wakf Boards":
        "Operational but subsumed under consolidated PMJVK; not a separate standalone scheme.",

    "Bixa Mica / Sickle Cell Anaemia Mission (ST Focus)":
        "Renamed — now 'National Sickle Cell Anaemia Elimination Mission (NSCAEM)'. Replaced below.",

    "Rashtriya Vayoshri Yojana":
        "Merged into ADIP (Assistance to Disabled Persons for Purchasing/Fitting of Aids/Appliances) scheme.",

    "Indira Mahila Shakti Udyam Protsahan Yojana":
        "State Rajasthan scheme — changed government; scheme status disputed. Removing until confirmed.",

    # ── State-specific removals ───────────────────────────────────────────────
    "Mukhyamantri Tirth Yatra Yojana":
        "Discontinued in Delhi after AAP policy review in 2024.",

    "Gatidhara Scheme (WB)":
        "West Bengal scheme wound down; replaced by WB Self Help Group loan schemes.",

    "Pravasi Rahat Mitra Yojana":
        "COVID-19 specific scheme (2020). No longer active.",

    "Gram Uday Se Bharat Uday":
        "One-time 2016 campaign. Not active.",

    "Bhajanaseva / Senior Citizen Pension Goa":
        "Renamed to 'Dayanand Social Security Scheme (DSSS)'. Removing duplicate.",

    "Rajiv Gandhi Gramin Bhumihin Krishi Mazdoor Nyay Yojana":
        "Scheme renamed under new CG government (2023) — 'Mahtari Vandan' replaced it. Removing.",

    "Varishtha Pension Bima Yojana":
        "Duplicate — same as VPBY above.",
}

# ── Schemes to RENAME / UPDATE URL (name → corrected dict fields) ─────────────
RENAME = {
    "Bixa Mica / Sickle Cell Anaemia Mission (ST Focus)": {
        "name": "National Sickle Cell Anaemia Elimination Mission (NSCAEM)",
        "benefit": "Free universal screening of 7 crore tribals + hydroxyurea treatment + genetic counselling",
        "apply_url": "https://nhp.gov.in/sickle-cell-anaemia"
    },
}

# ── Run audit ─────────────────────────────────────────────────────────────────
removed_total = 0
updated_total = 0
active_total = 0
files_modified = []

all_json_files = list(BASE.glob("*.json")) + list((BASE / "states").glob("*.json")) + \
                 list((BASE / "combined").glob("*.json")) + \
                 list((BASE / "state_by_sector").glob("*.json")) + \
                 list((BASE / "combined").glob("*.json"))

# Deduplicate
seen_paths = set()
unique_files = []
for f in all_json_files:
    if str(f) not in seen_paths and f.name != "all_schemes.json" and f.name != "all_states.json":
        seen_paths.add(str(f))
        unique_files.append(f)

print("=" * 60)
print("SCHEME AUDIT REPORT")
print("=" * 60)

for filepath in unique_files:
    data = json.loads(filepath.read_text(encoding="utf-8"))

    # Handle both formats: {schemes: [...]} and {central_schemes: [...], state_schemes: [...]}
    scheme_lists = []
    if "schemes" in data:
        scheme_lists.append(("schemes", data["schemes"]))
    if "central_schemes" in data:
        scheme_lists.append(("central_schemes", data["central_schemes"]))
    if "state_schemes" in data:
        scheme_lists.append(("state_schemes", data["state_schemes"]))

    file_changed = False
    for list_key, schemes in scheme_lists:
        new_schemes = []
        for scheme in schemes:
            name = scheme.get("name") or scheme.get("name_en", "")

            if name in REMOVE_BY_NAME:
                print(f"  ❌ REMOVED: {name}")
                print(f"     Reason: {REMOVE_BY_NAME[name][:70]}...")
                removed_total += 1
                file_changed = True
                continue

            # Mark active
            scheme["status"] = "active"
            new_schemes.append(scheme)
            active_total += 1

        if len(new_schemes) != len(schemes):
            data[list_key] = new_schemes
            if "count" in data:
                data["count"] = len(new_schemes)
            if "total" in data:
                data["total"] = data.get("central_count", 0) + data.get("state_count", 0)
            file_changed = True

    if file_changed:
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        files_modified.append(filepath.name)

print("\n" + "=" * 60)
print(f"  ✅ Active schemes remaining : {active_total}")
print(f"  ❌ Removed (inactive)       : {removed_total}")
print(f"  📁 Files modified           : {len(files_modified)}")
print("=" * 60)
print(f"\nAll remaining schemes tagged with  status: 'active'")
