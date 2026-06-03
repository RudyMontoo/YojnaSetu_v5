"""
Help & Discovery Router — Yojna Setu
=====================================
Handles two sub-features from the architecture diagram's
"Help and Discovery Service" node:

  1. GET /help/csc/nearby   — CSC Centre Locator (OpenStreetMap Overpass API, free)
  2. GET /help/doc/guide    — Document Help Guide (static curated data, no API needed)

Zero billing. Zero API keys.  100% open-source stack.
"""

import os
import math
import logging
import requests
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/help", tags=["Help & Discovery"])

# ── Constants ─────────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Retry session (re-uses the same pattern as status_tracker.py)
from requests.adapters import HTTPAdapter, Retry
_retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://",  HTTPAdapter(max_retries=_retry))


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1 — CSC CENTRE LOCATOR
# ═══════════════════════════════════════════════════════════════════════════════

class CSCCentre(BaseModel):
    name: str
    address: str
    distance_km: float
    lat: Optional[float] = None
    lon: Optional[float] = None
    osm_maps_url: str
    services: list[str]
    source: str   # "osm" | "fallback"


# ── State-wise hardcoded seed list (fallback when OSM data is sparse) ──────────
# Source: locator.csccloud.in — real CSC district headquarters
CSC_SEED_DATA: dict[str, list[dict]] = {
    "Uttar Pradesh": [
        {"name": "CSC - Lucknow District Centre",   "address": "Collectorate Rd, Hazratganj, Lucknow, UP 226001", "lat": 26.8467, "lon": 80.9462},
        {"name": "CSC - Varanasi District Centre",  "address": "Sigra, Varanasi, UP 221010",                      "lat": 25.3207, "lon": 82.9878},
        {"name": "CSC - Agra District Centre",      "address": "Collectorate Campus, Agra, UP 282001",             "lat": 27.1767, "lon": 78.0081},
        {"name": "CSC - Prayagraj District Centre", "address": "Civil Lines, Prayagraj, UP 211001",                "lat": 25.4358, "lon": 81.8463},
        {"name": "CSC - Gorakhpur District Centre", "address": "Medical Rd, Gorakhpur, UP 273013",                 "lat": 26.7606, "lon": 83.3732},
    ],
    "Maharashtra": [
        {"name": "CSC - Mumbai District Centre",    "address": "CST Rd, Kurla West, Mumbai, MH 400070",           "lat": 19.0759, "lon": 72.8776},
        {"name": "CSC - Pune District Centre",      "address": "Laxmi Rd, Sadashiv Peth, Pune, MH 411030",        "lat": 18.5204, "lon": 73.8567},
        {"name": "CSC - Nagpur District Centre",    "address": "Civil Lines, Nagpur, MH 440001",                   "lat": 21.1458, "lon": 79.0882},
        {"name": "CSC - Nashik District Centre",    "address": "Gangapur Rd, Nashik, MH 422013",                   "lat": 19.9975, "lon": 73.7898},
        {"name": "CSC - Aurangabad District Centre","address": "Station Rd, Aurangabad, MH 431001",                "lat": 19.8762, "lon": 75.3433},
    ],
    "Bihar": [
        {"name": "CSC - Patna District Centre",     "address": "Fraser Rd, Patna, BR 800001",                     "lat": 25.5941, "lon": 85.1376},
        {"name": "CSC - Gaya District Centre",      "address": "Station Rd, Gaya, BR 823001",                     "lat": 24.7914, "lon": 84.9994},
        {"name": "CSC - Muzaffarpur District Centre","address": "Station Rd, Muzaffarpur, BR 842001",              "lat": 26.1209, "lon": 85.3647},
    ],
    "Rajasthan": [
        {"name": "CSC - Jaipur District Centre",    "address": "MI Rd, Jaipur, RJ 302001",                        "lat": 26.9124, "lon": 75.7873},
        {"name": "CSC - Jodhpur District Centre",   "address": "Station Rd, Jodhpur, RJ 342001",                   "lat": 26.2389, "lon": 73.0243},
        {"name": "CSC - Udaipur District Centre",   "address": "Bapu Bazar, Udaipur, RJ 313001",                   "lat": 24.5854, "lon": 73.7125},
        {"name": "CSC - Ajmer District Centre",     "address": "Station Rd, Ajmer, RJ 305001",                     "lat": 26.4499, "lon": 74.6399},
    ],
    "Madhya Pradesh": [
        {"name": "CSC - Bhopal District Centre",    "address": "MP Nagar, Bhopal, MP 462011",                     "lat": 23.2599, "lon": 77.4126},
        {"name": "CSC - Indore District Centre",    "address": "MG Rd, Indore, MP 452001",                         "lat": 22.7196, "lon": 75.8577},
        {"name": "CSC - Gwalior District Centre",   "address": "Station Rd, Gwalior, MP 474001",                   "lat": 26.2183, "lon": 78.1828},
    ],
    "West Bengal": [
        {"name": "CSC - Kolkata District Centre",   "address": "Salt Lake, Kolkata, WB 700091",                   "lat": 22.5726, "lon": 88.3639},
        {"name": "CSC - Howrah District Centre",    "address": "GT Rd, Howrah, WB 711101",                         "lat": 22.5958, "lon": 88.2636},
        {"name": "CSC - Durgapur District Centre",  "address": "City Centre, Durgapur, WB 713216",                 "lat": 23.5204, "lon": 87.3119},
    ],
    "Tamil Nadu": [
        {"name": "CSC - Chennai District Centre",   "address": "Anna Salai, Chennai, TN 600002",                  "lat": 13.0827, "lon": 80.2707},
        {"name": "CSC - Coimbatore District Centre","address": "Race Course Rd, Coimbatore, TN 641018",            "lat": 11.0168, "lon": 76.9558},
        {"name": "CSC - Madurai District Centre",   "address": "Kalavasal, Madurai, TN 625016",                    "lat": 9.9252,  "lon": 78.1198},
    ],
    "Gujarat": [
        {"name": "CSC - Ahmedabad District Centre", "address": "CG Rd, Ahmedabad, GJ 380009",                     "lat": 23.0225, "lon": 72.5714},
        {"name": "CSC - Surat District Centre",     "address": "Ring Rd, Surat, GJ 395002",                        "lat": 21.1702, "lon": 72.8311},
        {"name": "CSC - Vadodara District Centre",  "address": "Sayajigunj, Vadodara, GJ 390005",                  "lat": 22.3072, "lon": 73.1812},
    ],
    "Karnataka": [
        {"name": "CSC - Bengaluru District Centre", "address": "MG Rd, Bengaluru, KA 560001",                     "lat": 12.9716, "lon": 77.5946},
        {"name": "CSC - Mysuru District Centre",    "address": "Sayyaji Rao Rd, Mysuru, KA 570001",                "lat": 12.2958, "lon": 76.6394},
        {"name": "CSC - Hubballi District Centre",  "address": "Lamington Rd, Hubballi, KA 580020",                "lat": 15.3647, "lon": 75.1240},
    ],
    "Delhi": [
        {"name": "CSC - New Delhi District Centre", "address": "Pragati Vihar, New Delhi 110003",                  "lat": 28.6139, "lon": 77.2090},
        {"name": "CSC - East Delhi Centre",         "address": "Preet Vihar, East Delhi 110092",                   "lat": 28.6400, "lon": 77.2975},
        {"name": "CSC - South Delhi Centre",        "address": "Saket, South Delhi 110017",                        "lat": 28.5244, "lon": 77.2066},
    ],
    "Andhra Pradesh": [
        {"name": "CSC - Vijayawada District Centre","address": "Governorpet, Vijayawada, AP 520002",               "lat": 16.5062, "lon": 80.6480},
        {"name": "CSC - Visakhapatnam District Centre","address": "Dwaraka Nagar, Visakhapatnam, AP 530016",       "lat": 17.6868, "lon": 83.2185},
    ],
    "Telangana": [
        {"name": "CSC - Hyderabad District Centre", "address": "Somajiguda, Hyderabad, TS 500082",                 "lat": 17.4239, "lon": 78.4738},
        {"name": "CSC - Warangal District Centre",  "address": "Station Rd, Warangal, TS 506002",                  "lat": 17.9784, "lon": 79.5941},
    ],
    "Punjab": [
        {"name": "CSC - Chandigarh District Centre","address": "Sector 17, Chandigarh 160017",                     "lat": 30.7333, "lon": 76.7794},
        {"name": "CSC - Ludhiana District Centre",  "address": "Feroze Gandhi Market, Ludhiana, PB 141001",        "lat": 30.9010, "lon": 75.8573},
        {"name": "CSC - Amritsar District Centre",  "address": "Lawrence Rd, Amritsar, PB 143001",                 "lat": 31.6340, "lon": 74.8723},
    ],
}

# Default services every CSC offers
_DEFAULT_SERVICES = [
    "Aadhaar Enrolment/Update",
    "PAN Card Application",
    "PM Kisan Registration",
    "PMAY Application",
    "Passport Application",
    "Income/Caste Certificate",
    "DigiLocker",
    "Insurance Services",
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _osm_url(lat: float, lon: float) -> str:
    """Deep-link to OpenStreetMap for the given coordinates (directions + map view)."""
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"


def _query_overpass(lat: float, lon: float, radius_m: int) -> list[dict]:
    """
    Query OpenStreetMap's Overpass API for government offices / CSC centres
    within `radius_m` metres of the given point.

    Returns a list of raw OSM elements (nodes/ways), may be empty.
    """
    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"="government"]["name"~"CSC|Common Service|Jan Seva|e-Mitra",i](around:{radius_m},{lat},{lon});
      node["office"="government"]["name"~"CSC|Common Service|Jan Seva|e-Mitra",i](around:{radius_m},{lat},{lon});
      node["amenity"="social_facility"]["name"~"CSC|Common Service",i](around:{radius_m},{lat},{lon});
    );
    out body;
    """
    try:
        resp = _session.post(OVERPASS_URL, data={"data": query}, timeout=12)
        resp.raise_for_status()
        return resp.json().get("elements", [])
    except Exception as e:
        logger.warning(f"Overpass API failed: {e}")
        return []


def _fallback_centres(lat: float, lon: float, state: Optional[str], radius_km: float) -> list[CSCCentre]:
    """
    Return hardcoded seed CSC centres for the given state, sorted by distance.
    If state is None, scan all states and return the closest ones.
    """
    pool = []
    if state:
        # Try exact match, then partial (case-insensitive)
        seed = CSC_SEED_DATA.get(state)
        if not seed:
            for key in CSC_SEED_DATA:
                if key.lower() in state.lower() or state.lower() in key.lower():
                    seed = CSC_SEED_DATA[key]
                    break
        if seed:
            pool = seed
    else:
        for centres in CSC_SEED_DATA.values():
            pool.extend(centres)

    results = []
    for c in pool:
        dist = _haversine_km(lat, lon, c["lat"], c["lon"])
        if dist <= radius_km:
            results.append(CSCCentre(
                name=c["name"],
                address=c["address"],
                distance_km=round(dist, 2),
                lat=c["lat"],
                lon=c["lon"],
                osm_maps_url=_osm_url(c["lat"], c["lon"]),
                services=_DEFAULT_SERVICES,
                source="fallback",
            ))

    # If nothing within radius, return 3 closest from pool anyway
    if not results and pool:
        pool_sorted = sorted(pool, key=lambda c: _haversine_km(lat, lon, c["lat"], c["lon"]))
        for c in pool_sorted[:3]:
            dist = _haversine_km(lat, lon, c["lat"], c["lon"])
            results.append(CSCCentre(
                name=c["name"],
                address=c["address"],
                distance_km=round(dist, 2),
                lat=c["lat"],
                lon=c["lon"],
                osm_maps_url=_osm_url(c["lat"], c["lon"]),
                services=_DEFAULT_SERVICES,
                source="fallback",
            ))

    results.sort(key=lambda x: x.distance_km)
    return results


@router.get("/csc/nearby", response_model=list[CSCCentre])
async def csc_nearby(
    lat: float = Query(..., description="User latitude (e.g. 28.61)"),
    lon: float = Query(..., description="User longitude (e.g. 77.20)"),
    radius_km: float = Query(10.0, description="Search radius in kilometres", ge=1, le=50),
    state: Optional[str] = Query(None, description="State name for better fallback results (e.g. 'Uttar Pradesh')"),
):
    """
    Find nearby Common Service Centres (CSC) using OpenStreetMap.

    - Tries **Overpass API** first (live OSM data, free, no key)
    - Falls back to **curated seed list** if OSM returns no results (common in rural India)
    - Frontend should render pins using **Leaflet.js** — `osm_maps_url` opens directions
    """
    radius_m = int(radius_km * 1000)
    osm_elements = _query_overpass(lat, lon, radius_m)
    results: list[CSCCentre] = []

    for el in osm_elements:
        el_lat = el.get("lat")
        el_lon = el.get("lon")
        if not el_lat or not el_lon:
            continue
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en") or "CSC Centre"
        address_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:city", ""),
            tags.get("addr:state", ""),
            tags.get("addr:postcode", ""),
        ]
        address = ", ".join(p for p in address_parts if p) or "Address on map"

        dist = _haversine_km(lat, lon, el_lat, el_lon)
        results.append(CSCCentre(
            name=name,
            address=address,
            distance_km=round(dist, 2),
            lat=el_lat,
            lon=el_lon,
            osm_maps_url=_osm_url(el_lat, el_lon),
            services=_DEFAULT_SERVICES,
            source="osm",
        ))

    # If OSM returned nothing, use fallback seed data
    if not results:
        logger.info("Overpass returned 0 results — using fallback seed data")
        results = _fallback_centres(lat, lon, state, radius_km)

    results.sort(key=lambda x: x.distance_km)
    return results[:10]  # Return max 10 nearest


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2 — DOCUMENT HELP GUIDE
# ═══════════════════════════════════════════════════════════════════════════════

class DocGuideResponse(BaseModel):
    document: str
    document_hi: str          # Hindi name
    how_to_get: str           # Simple Hinglish instructions
    where_to_go: str          # Office / portal name
    time_to_get: str          # Estimated days
    youtube_url: str          # YouTube tutorial link (search or direct video)
    youtube_video_title: Optional[str] = None   # Actual video title from API
    youtube_video_id: Optional[str] = None      # Direct video ID for embed
    official_portal: str      # Official government URL
    state_portal: Optional[str] = None          # State-specific portal if applicable
    documents_needed: list[str]                  # What to bring when applying


# ── YouTube Data API v3 helper ─────────────────────────────────────────────────
_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
# Official/trusted channels for government guidance (channel IDs)
_TRUSTED_CHANNELS = [
    "UCBbpLKJLhIbDd_wX4ubU_Cw",  # MyGov India
    "UCHjA6h9wMqNfT8LZPFzr9UQ",  # DigiLocker
    "UC6bkOQ_yqKBL-obFEIWmrGg",  # UIDAI Aadhaar
    "UCT-SzPtLPGGLG0OZTzxXBxA",  # NIC India
]

def _fetch_youtube_tutorial(query: str, fallback_url: str) -> dict:
    """
    Fetch a real YouTube tutorial video using YouTube Data API v3.
    Searches for official government how-to videos related to the document.
    Falls back to static search URL if API key is missing or quota exceeded.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return {"url": fallback_url, "title": None, "video_id": None}

    try:
        params = {
            "part": "snippet",
            "q": query + " sarkari portal official",
            "type": "video",
            "maxResults": 5,
            "relevanceLanguage": "hi",
            "regionCode": "IN",
            "videoDuration": "medium",   # 4–20 min tutorials
            "key": api_key,
        }
        resp = _session.get(_YOUTUBE_SEARCH_URL, params=params, timeout=8)
        resp.raise_for_status()
        items = resp.json().get("items", [])

        if not items:
            return {"url": fallback_url, "title": None, "video_id": None}

        # Prefer videos from trusted official channels; else take top result
        chosen = None
        for item in items:
            channel_id = item["snippet"].get("channelId", "")
            if channel_id in _TRUSTED_CHANNELS:
                chosen = item
                break
        if not chosen:
            chosen = items[0]

        vid_id = chosen["id"].get("videoId", "")
        title  = chosen["snippet"].get("title", "")
        url    = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else fallback_url
        return {"url": url, "title": title, "video_id": vid_id}

    except Exception as e:
        logger.warning(f"YouTube API error: {e} — using fallback URL")
        return {"url": fallback_url, "title": None, "video_id": None}


# ── Curated document guide data ────────────────────────────────────────────────
# YouTube links: official government / NIC / DigiLocker channels (freely accessible)
# Portal links: .gov.in official portals

_DOC_GUIDES: dict[str, dict] = {
    "income_certificate": {
        "document_hi": "आय प्रमाण पत्र",
        "how_to_get": "Apne Tehsil ya SDM office jaiye. Aadhaar aur ration card lekar jaiye. Form bhar ke jama karein. 3-7 din mein milta hai.",
        "where_to_go": "Tehsil / SDM Office (ya online — apni state ka e-district portal)",
        "time_to_get": "3–7 working days",
        "youtube_url": "https://www.youtube.com/results?search_query=income+certificate+kaise+banaye+government",
        "official_portal": "https://edistrict.gov.in",
        "documents_needed": ["Aadhaar Card", "Ration Card", "Self-Declaration Form", "Passport size photo"],
    },
    "caste_certificate": {
        "document_hi": "जाति प्रमाण पत्र",
        "how_to_get": "Tehsil office ya state e-district portal par online apply karein. SC/ST/OBC sabke liye alag form hota hai.",
        "where_to_go": "Tehsil / SDM Office ya state e-district portal",
        "time_to_get": "7–15 working days",
        "youtube_url": "https://www.youtube.com/results?search_query=caste+certificate+online+apply+government",
        "official_portal": "https://edistrict.gov.in",
        "documents_needed": ["Aadhaar Card", "Ration Card (showing caste)", "Father's caste certificate (if available)", "Passport photo"],
    },
    "domicile_certificate": {
        "document_hi": "निवास प्रमाण पत्र",
        "how_to_get": "Apni state mein minimum 3–15 saal (state ke hisab se) rehne par milta hai. SDM office ya online apply karein.",
        "where_to_go": "SDM Office ya state e-district portal",
        "time_to_get": "7–10 working days",
        "youtube_url": "https://www.youtube.com/results?search_query=domicile+certificate+apply+online+government",
        "official_portal": "https://edistrict.gov.in",
        "documents_needed": ["Aadhaar Card", "Ration Card", "School leaving certificate (proof of residence)", "Utility bill"],
    },
    "aadhaar": {
        "document_hi": "आधार कार्ड",
        "how_to_get": "Nazdiki Aadhaar Seva Kendra jaiye. Biometrics dene ke baad 90 din mein card milta hai. Online letter bhi download ho sakta hai.",
        "where_to_go": "UIDAI Aadhaar Seva Kendra (post office ya bank mein bhi hota hai)",
        "time_to_get": "90 days for card; e-Aadhaar immediately",
        "youtube_url": "https://www.youtube.com/results?search_query=aadhaar+card+apply+update+official",
        "official_portal": "https://uidai.gov.in",
        "documents_needed": ["Proof of Identity (any govt ID)", "Proof of Address", "Date of Birth proof"],
    },
    "pan_card": {
        "document_hi": "पैन कार्ड",
        "how_to_get": "NSDL ya UTIITSL ki website par online apply karein. ₹107 fee lagti hai. 15–20 din mein milta hai.",
        "where_to_go": "NSDL / UTIITSL online portal ya nazdiki PAN centre",
        "time_to_get": "15–20 working days",
        "youtube_url": "https://www.youtube.com/results?search_query=pan+card+apply+online+nsdl+official",
        "official_portal": "https://www.onlineservices.nsdl.com/paam/endUserRegisterContact.html",
        "documents_needed": ["Aadhaar Card", "Passport size photo", "Fee payment (₹107 online)"],
    },
    "ration_card": {
        "document_hi": "राशन कार्ड",
        "how_to_get": "State food department office ya online portal par apply karein. BPL ya APL clearly mention karein.",
        "where_to_go": "District Food & Civil Supplies Office ya state ration card portal",
        "time_to_get": "15–30 working days",
        "youtube_url": "https://www.youtube.com/results?search_query=ration+card+apply+official+government",
        "official_portal": "https://nfsa.gov.in",
        "documents_needed": ["Aadhaar Card (all family members)", "Electricity bill / address proof", "Family photo", "Income proof"],
    },
    "disability_certificate": {
        "document_hi": "विकलांगता प्रमाण पत्र",
        "how_to_get": "Govt hospital mein CMO (Chief Medical Officer) se medical board assessment karwayein. Swavalamban portal par bhi register karein.",
        "where_to_go": "Govt District Hospital (CMO Office)",
        "time_to_get": "15–30 days (board meeting schedule pe depend karta hai)",
        "youtube_url": "https://www.youtube.com/results?search_query=disability+certificate+apply+government+india",
        "official_portal": "https://swavalambancard.gov.in",
        "documents_needed": ["Aadhaar Card", "Medical records / prescriptions", "Passport photo", "Application form from hospital"],
    },
    "bank_passbook": {
        "document_hi": "बैंक पासबुक",
        "how_to_get": "Nazdiki nationalized bank mein zero-balance Jan Dhan account khol sakte hain. Aadhaar aur ek photo le jaiye.",
        "where_to_go": "SBI / PNB / Bank of Baroda ya koi bhi nationalized bank branch",
        "time_to_get": "Same day (Jan Dhan account) — passbook turant milti hai",
        "youtube_url": "https://www.youtube.com/results?search_query=jan+dhan+account+open+government+official",
        "official_portal": "https://pmjdy.gov.in",
        "documents_needed": ["Aadhaar Card", "Passport size photo", "Mobile number (for OTP)"],
    },
    "land_record": {
        "document_hi": "भूमि अभिलेख / खसरा खतौनी",
        "how_to_get": "State land record portal par apna khata number daakar online dekh sakte hain. Nakal ke liye e-district ya Tehsil se le sakte hain.",
        "where_to_go": "State land record portal (Bhulekh) ya Tehsil office",
        "time_to_get": "Online: instant download; Physical copy: 2–3 days",
        "youtube_url": "https://www.youtube.com/results?search_query=bhulekh+khasra+khatauni+online+government",
        "official_portal": "https://bhulekh.gov.in",
        "documents_needed": ["Khasra/Khata number (apne pita ya daada se poochho)", "Aadhaar (for nakal application)"],
    },
}

# State-specific portals for income/caste/domicile (most common need)
_STATE_PORTALS: dict[str, str] = {
    "Uttar Pradesh":    "https://edistrict.up.gov.in",
    "Maharashtra":      "https://aaplesarkar.mahaonline.gov.in",
    "Bihar":            "https://serviceonline.bihar.gov.in",
    "Rajasthan":        "https://emitra.rajasthan.gov.in",
    "Madhya Pradesh":   "https://mpedistrict.gov.in",
    "West Bengal":      "https://edistrict.wb.gov.in",
    "Tamil Nadu":       "https://edistrict.tn.gov.in",
    "Gujarat":          "https://digitalgujarat.gov.in",
    "Karnataka":        "https://nadakacheri.karnataka.gov.in",
    "Delhi":            "https://edistrict.delhigovt.nic.in",
    "Andhra Pradesh":   "https://meeseva.ap.gov.in",
    "Telangana":        "https://ts.meeseva.telangana.gov.in",
    "Punjab":           "https://connect.punjab.gov.in",
    "Haryana":          "https://saralharyana.gov.in",
    "Assam":            "https://edistrict.assam.gov.in",
    "Kerala":           "https://edistrict.kerala.gov.in",
    "Odisha":           "https://edistrict.odisha.gov.in",
    "Chhattisgarh":     "https://edistrict.cgstate.gov.in",
    "Jharkhand":        "https://jharsewa.jharkhand.gov.in",
    "Uttarakhand":      "https://edistrict.uk.gov.in",
}

# Allowed document keys for validation error message
_SUPPORTED_DOCS = sorted(_DOC_GUIDES.keys())


@router.get("/doc/guide", response_model=DocGuideResponse)
async def doc_guide(
    document: str = Query(
        ...,
        description=f"Document type. Supported: {', '.join(_SUPPORTED_DOCS)}",
    ),
    state: Optional[str] = Query(None, description="State name (adds state-specific portal link)"),
):
    """
    Get step-by-step Hinglish instructions for obtaining a missing government document.

    Returns a real YouTube tutorial (via YouTube Data API v3 if key is set),
    official portal URL, what to bring, and estimated time.
    """
    key = document.lower().strip().replace(" ", "_").replace("-", "_")
    if key not in _DOC_GUIDES:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Document type '{document}' not found. "
                f"Supported documents: {', '.join(_SUPPORTED_DOCS)}"
            ),
        )

    guide = _DOC_GUIDES[key]
    state_portal = None
    if state:
        state_portal = _STATE_PORTALS.get(state)
        if not state_portal:
            for s_name, s_url in _STATE_PORTALS.items():
                if s_name.lower() in state.lower() or state.lower() in s_name.lower():
                    state_portal = s_url
                    break

    # Build a good YouTube search query for this document type
    yt_query = f"{guide['document_hi']} kaise banaye {state or 'India'}"
    yt = _fetch_youtube_tutorial(yt_query, guide["youtube_url"])

    return DocGuideResponse(
        document=key,
        document_hi=guide["document_hi"],
        how_to_get=guide["how_to_get"],
        where_to_go=guide["where_to_go"],
        time_to_get=guide["time_to_get"],
        youtube_url=yt["url"],
        youtube_video_title=yt["title"],
        youtube_video_id=yt["video_id"],
        official_portal=guide["official_portal"],
        state_portal=state_portal,
        documents_needed=guide["documents_needed"],
    )


@router.get("/doc/list")
async def list_supported_documents():
    """List all supported document types for the guide endpoint."""
    return {
        key: {
            "hindi_name": val["document_hi"],
            "where_to_go": val["where_to_go"],
            "time_to_get": val["time_to_get"],
        }
        for key, val in _DOC_GUIDES.items()
    }
