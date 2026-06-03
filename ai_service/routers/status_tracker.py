"""
Yojna Setu — Scheme Application Status Tracker
Scrapes real government portals to fetch application status.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
import json
from typing import Optional
from requests.adapters import HTTPAdapter, Retry

from ai_service.utils.auth import require_api_key
from ai_service.utils.rate_limiter import status_limiter

router = APIRouter(prefix="/status", tags=["Status Tracker"])

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
}

# Retry strategy: 3 retries with exponential backoff (1s, 2s, 4s)
_retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
SESSION.mount("https://", HTTPAdapter(max_retries=_retry_strategy))
SESSION.mount("http://",  HTTPAdapter(max_retries=_retry_strategy))

# ─── Request / Response Models ──────────────────────────────────────────────

class StatusRequest(BaseModel):
    scheme_key: str          # e.g. "pmkisan", "pmayg", "nrega"
    identifier: str          # Aadhaar / Registration No / Job Card No
    state_code: Optional[str] = None   # e.g. "UP", "MH" (needed for NREGA)

class StatusStage(BaseModel):
    stage: str
    completed: bool
    date: Optional[str] = None
    amount: Optional[str] = None

class StatusResponse(BaseModel):
    scheme_name: str
    applicant_name: Optional[str] = None
    current_stage: str
    stages: list[StatusStage]
    raw_details: dict
    source_url: str
    note: Optional[str] = None

# ─── Supported Schemes Registry ──────────────────────────────────────────────

SCHEME_REGISTRY = {
    "pmkisan": {
        "name": "PM Kisan Samman Nidhi",
        "stages": ["Registered", "Aadhaar Verified", "Land Verified", "Bank Verified",
                   "1st Installment", "2nd Installment", "3rd Installment", "Active"],
        "scraper": "scrape_pmkisan",
        "url": "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx",
    },
    "pmayg": {
        "name": "PM Awas Yojana - Gramin",
        "stages": ["Applied", "Verified by BDO", "Sanctioned", "1st Installment (Foundation)",
                   "2nd Installment (Lintel)", "3rd Installment (Roof)", "Completed & Geo-tagged"],
        "scraper": "scrape_pmayg",
        "url": "https://pmayg.nic.in/netiay/Benificiary.aspx",
    },
    "nrega": {
        "name": "MGNREGS (MNREGA)",
        "stages": ["Job Card Issued", "Work Demanded", "Work Allocated",
                   "Work Started", "Muster Roll Generated", "Wages Paid"],
        "scraper": "scrape_nrega",
        "url": "https://nrega.nic.in/netnrega/statusReport.aspx",
    },
    "nsp": {
        "name": "National Scholarship Portal",
        "stages": ["Application Submitted", "Institute Verified", "District Verified",
                   "State Verified", "Central Verified", "Amount Disbursed"],
        "scraper": "scrape_nsp",
        "url": "https://scholarships.gov.in/fresh/trackApplicationStatus",
    },
    "pmjay": {
        "name": "Ayushman Bharat PM-JAY",
        "stages": ["Eligibility Confirmed", "Card Generated", "Card Active", "Claim Submitted",
                   "Claim Approved", "Amount Paid to Hospital"],
        "scraper": "scrape_pmjay",
        "url": "https://beneficiary.nha.gov.in",
    },
    "pmuy": {
        "name": "PM Ujjwala Yojana",
        "stages": ["Application Received", "KYC Verified", "Connection Approved",
                   "Cylinder Delivered", "Subsidy Linked to Bank"],
        "scraper": "scrape_pmuy",
        "url": "https://www.mylpg.in",
    },
}

# ─── Individual Scrapers ─────────────────────────────────────────────────────

def scrape_pmkisan(identifier: str, **kwargs) -> dict:
    """Fetch PM Kisan beneficiary status by Aadhaar or registration number."""
    base_url = "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx"
    try:
        # First GET to get viewstate tokens
        resp = SESSION.get(base_url, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        viewstate = soup.find("input", {"id": "__VIEWSTATE"})
        eventval = soup.find("input", {"id": "__EVENTVALIDATION"})

        id_type = "ADNO" if re.match(r"^\d{12}$", identifier.replace(" ", "")) else "BNFID"
        payload = {
            "__VIEWSTATE": viewstate["value"] if viewstate else "",
            "__EVENTVALIDATION": eventval["value"] if eventval else "",
            "ctl00$ContentPlaceHolder1$ddlMode": id_type,
            "ctl00$ContentPlaceHolder1$txtAadharNo": identifier.replace(" ", ""),
            "ctl00$ContentPlaceHolder1$btnSubmit": "Get Data",
        }
        resp = SESSION.post(base_url, data=payload, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse beneficiary name and payment details
        name_el = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_lblBenfName"})
        payments = []
        table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_gvPaymentDetail"})
        if table:
            rows = table.find_all("tr")[1:]
            for row in rows[:6]:
                cols = [c.get_text(strip=True) for c in row.find_all("td")]
                if cols:
                    payments.append({"installment": cols[0], "amount": cols[1] if len(cols) > 1 else "N/A",
                                     "date": cols[2] if len(cols) > 2 else "N/A", "status": cols[-1]})

        name = name_el.get_text(strip=True) if name_el else "Not Found"
        current = f"Installment {len(payments)} Completed" if payments else "Not Registered"

        return {"name": name, "payments": payments, "total_installments": len(payments),
                "current_stage": current}

    except Exception as e:
        return {"error": str(e), "current_stage": "Unable to fetch — check portal directly"}


def scrape_pmayg(identifier: str, **kwargs) -> dict:
    """Fetch PMAY-Gramin beneficiary status by registration number."""
    base_url = "https://pmayg.nic.in/netiay/Benificiary.aspx"
    try:
        resp = SESSION.get(base_url, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        vs = soup.find("input", {"id": "__VIEWSTATE"})
        ev = soup.find("input", {"id": "__EVENTVALIDATION"})

        payload = {
            "__VIEWSTATE": vs["value"] if vs else "",
            "__EVENTVALIDATION": ev["value"] if ev else "",
            "ctl00$ContentPlaceHolder1$txtregistration": identifier,
            "ctl00$ContentPlaceHolder1$Btn_detail": "Search",
        }
        resp = SESSION.post(base_url, data=payload, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        name_el = soup.find("td", string=re.compile(r"Beneficiary Name", re.I))
        name = name_el.find_next_sibling("td").get_text(strip=True) if name_el else "Not Found"

        installments = []
        inst_table = soup.find("table", class_=re.compile(r"payment|installment", re.I))
        if inst_table:
            for row in inst_table.find_all("tr")[1:]:
                cols = [c.get_text(strip=True) for c in row.find_all("td")]
                if cols:
                    installments.append({"stage": cols[0], "amount": cols[1] if len(cols) > 1 else "",
                                         "date": cols[2] if len(cols) > 2 else "", "status": cols[-1]})

        stage_map = {0: "Applied", 1: "1st Installment - Foundation",
                     2: "2nd Installment - Lintel Level", 3: "Completed"}
        current = stage_map.get(len(installments), f"{len(installments)} installments released")

        return {"name": name, "installments": installments, "current_stage": current}

    except Exception as e:
        return {"error": str(e), "current_stage": "Unable to fetch"}


def scrape_nsp(identifier: str, **kwargs) -> dict:
    """Fetch NSP scholarship application status by application ID."""
    base_url = "https://scholarships.gov.in/fresh/trackApplicationStatus"
    try:
        resp = SESSION.get(f"{base_url}?applicationId={identifier}", timeout=12)
        soup = BeautifulSoup(resp.text, "lxml")

        status_el = soup.find("div", class_=re.compile(r"status|track", re.I))
        rows = {}
        if status_el:
            for row in status_el.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 2:
                    rows[cols[0].get_text(strip=True)] = cols[1].get_text(strip=True)

        current = rows.get("Current Status", "Check portal directly")
        return {"application_id": identifier, "details": rows, "current_stage": current}

    except Exception as e:
        return {"error": str(e), "current_stage": "Unable to fetch"}


def scrape_nrega(identifier: str, state_code: str = None, **kwargs) -> dict:
    """Fetch MGNREGA job card status."""
    base_url = "https://nrega.nic.in/netnrega/StatusReport_-NREGA_jobcard.aspx"
    try:
        resp = SESSION.get(f"{base_url}?reg={identifier}", timeout=12)
        soup = BeautifulSoup(resp.text, "lxml")

        name_el = soup.find(string=re.compile(r"applicant|worker", re.I))
        name = name_el.find_next() if name_el else None
        days_el = soup.find(string=re.compile(r"days worked", re.I))
        days = days_el.find_next().get_text(strip=True) if days_el else "N/A"

        return {"name": name.get_text(strip=True) if name else "Not Found",
                "days_worked": days,
                "current_stage": f"Active — {days} days worked this year"}
    except Exception as e:
        return {"error": str(e), "current_stage": "Unable to fetch"}


def scrape_pmjay(identifier: str, **kwargs) -> dict:
    """Check Ayushman Bharat (PM-JAY) eligibility and card status."""
    try:
        api_url = f"https://beneficiary.nha.gov.in/mera/beneficiary/checkBeneficiary?id={identifier}"
        resp = SESSION.get(api_url, timeout=10)
        data = resp.json() if resp.status_code == 200 else {}
        eligible = data.get("isEligible", False)
        name = data.get("name", "Not Found")
        card = data.get("cardStatus", "Not Generated")
        return {"name": name, "eligible": eligible, "card_status": card,
                "current_stage": "Card Active" if card == "ACTIVE" else "Card Not Generated" if eligible else "Not Eligible"}
    except Exception as e:
        return {"error": str(e), "current_stage": "Unable to fetch"}


def scrape_pmuy(identifier: str, **kwargs) -> dict:
    """Check PM Ujjwala Yojana LPG connection status."""
    try:
        url = f"https://www.mylpg.in/customer/application-status?id={identifier}"
        resp = SESSION.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        status_el = soup.find("div", class_=re.compile(r"status", re.I))
        status_text = status_el.get_text(strip=True) if status_el else "Check mylpg.in directly"
        return {"current_stage": status_text}
    except Exception as e:
        return {"error": str(e), "current_stage": "Unable to fetch"}


# ─── Dispatcher ──────────────────────────────────────────────────────────────

SCRAPER_MAP = {
    "pmkisan": scrape_pmkisan,
    "pmayg": scrape_pmayg,
    "nrega": scrape_nrega,
    "nsp": scrape_nsp,
    "pmjay": scrape_pmjay,
    "pmuy": scrape_pmuy,
}

# ─── API Endpoints ────────────────────────────────────────────────────────────

@router.post("/check", response_model=StatusResponse, dependencies=[Depends(require_api_key)])
async def check_status(req: StatusRequest, request: Request):
    """
    Check real-time scheme application status.
    
    - **scheme_key**: one of pmkisan, pmayg, nrega, nsp, pmjay, pmuy
    - **identifier**: Aadhaar number / Application ID / Registration Number
    - **state_code**: required only for NREGA (e.g. "UP", "MH")
    """
    status_limiter.check(status_limiter.get_client_ip(request))
    scheme_key = req.scheme_key.lower()
    if scheme_key not in SCHEME_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Scheme '{scheme_key}' not supported. Supported: {list(SCHEME_REGISTRY.keys())}"
        )

    scheme = SCHEME_REGISTRY[scheme_key]
    scraper = SCRAPER_MAP[scheme_key]

    raw = scraper(req.identifier, state_code=req.state_code)
    current_stage = raw.get("current_stage", "Unknown")

    # Build stages with completion flags
    all_stages = scheme["stages"]
    try:
        current_idx = next(
            (i for i, s in enumerate(all_stages) if s.lower() in current_stage.lower()),
            -1
        )
    except Exception:
        current_idx = -1

    stages = [
        StatusStage(stage=s, completed=(i <= current_idx))
        for i, s in enumerate(all_stages)
    ]

    return StatusResponse(
        scheme_name=scheme["name"],
        applicant_name=raw.get("name"),
        current_stage=current_stage,
        stages=stages,
        raw_details=raw,
        source_url=scheme["url"],
        note="Data fetched live from government portal. If incorrect, verify directly on the portal."
    )


@router.get("/schemes")
async def list_supported_schemes():
    """List all schemes supported for status tracking."""
    return {
        key: {"name": val["name"], "stages": val["stages"], "portal": val["url"]}
        for key, val in SCHEME_REGISTRY.items()
    }
