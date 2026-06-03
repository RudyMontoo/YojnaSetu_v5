"""
Defence sector schemes — for defence personnel, veterans, and their families.
Run: python add_defence_sector.py
"""
import json, os

DEFENCE_SCHEMES = [
    {
        "name": "Ex-Servicemen Contributory Health Scheme (ECHS)",
        "ministry": "Ministry of Defence",
        "benefit": "Cashless medical treatment at 422+ polyclinics and empanelled hospitals for ex-servicemen and dependents",
        "benefit_hi": "भूतपूर्व सैनिकों और आश्रितों को 422+ पॉलीक्लीनिक/अस्पतालों में कैशलेस चिकित्सा",
        "eligibility": "Retired defence personnel (Army/Navy/Air Force) and their dependents",
        "documents": ["ECHS card", "Aadhaar", "PPO (Pension Payment Order)", "Discharge book"],
        "apply_url": "https://echs.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Armed Forces Flag Day Fund (AFFDF)",
        "ministry": "Ministry of Defence / KSB",
        "benefit": "Financial grants for welfare of serving soldiers, veterans, war widows and their wards",
        "benefit_hi": "सैनिकों, भूतपूर्व सैनिकों, वीर नारियों और उनके बच्चों के कल्याण हेतु वित्तीय सहायता",
        "eligibility": "Serving/retired defence personnel and war widows",
        "documents": ["Service/discharge certificate", "Aadhaar", "Bank account"],
        "apply_url": "https://ksb.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "PM Scholarship Scheme for Ex-Servicemen / Coast Guard",
        "ministry": "Ministry of Defence / KSB",
        "benefit": "Rs 3,000/month (boys) and Rs 3,500/month (girls) scholarship for wards of ex-servicemen",
        "benefit_hi": "भूतपूर्व सैनिकों के बच्चों को ₹3,000 (लड़के) / ₹3,500 (लड़कियाँ) प्रतिमाह छात्रवृत्ति",
        "eligibility": "Wards of ex-servicemen / Coast Guard pursuing professional degree courses",
        "documents": ["Aadhaar", "Ex-serviceman certificate", "Admission proof", "Bank account"],
        "apply_url": "https://ksb.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Canteen Stores Department (CSD) Facilities",
        "ministry": "Ministry of Defence",
        "benefit": "Subsidized goods (groceries, electronics, vehicles) at CSD canteens at ~15-30% less than market price",
        "benefit_hi": "CSD कैंटीन में बाजार से 15-30% सस्ते में सामान (किराना, इलेक्ट्रॉनिक्स, वाहन)",
        "eligibility": "Serving and retired defence personnel and their families",
        "documents": ["CSD smart card", "I-card of defence personnel"],
        "apply_url": "https://csdafia.com",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Veer Nari (War Widow) Pension",
        "ministry": "Ministry of Defence",
        "benefit": "Special Family Pension equal to last pay drawn, for life, to widows of battle casualties",
        "benefit_hi": "युद्ध में शहीद सैनिक की पत्नी को आजीवन अंतिम वेतन के बराबर विशेष पारिवारिक पेंशन",
        "eligibility": "Widows of defence personnel who died in battle/line of duty",
        "documents": ["Death certificate", "Marriage certificate", "Aadhaar", "Bank account", "PPO"],
        "apply_url": "https://desw.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Liberal Family Pension (LFP)",
        "ministry": "Ministry of Defence",
        "benefit": "Enhanced pension (60% of last pay) to family if death occurs in line of duty",
        "benefit_hi": "सेवा के दौरान मृत्यु होने पर परिवार को अंतिम वेतन का 60% पारिवारिक पेंशन",
        "eligibility": "Family of defence personnel who died on duty (non-battle casualty)",
        "documents": ["Discharge/death certificate", "Aadhaar", "PPO", "Bank account"],
        "apply_url": "https://pcda.nic.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Army Group Insurance Fund (AGIF)",
        "ministry": "Ministry of Defence (Army)",
        "benefit": "Insurance cover Rs 50 lakh for officers, Rs 30 lakh for JCOs/OR on death/disability",
        "benefit_hi": "अधिकारियों को ₹50 लाख, JCO/OR को ₹30 लाख बीमा (मृत्यु/विकलांगता)",
        "eligibility": "All serving Indian Army personnel",
        "documents": ["Service record", "AGIF membership card", "Nomination form"],
        "apply_url": "https://agif.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Navy Group Insurance Scheme (NGIS)",
        "ministry": "Ministry of Defence (Navy)",
        "benefit": "Life insurance Rs 30-50 lakh + disability cover for Navy personnel",
        "benefit_hi": "नौसेना कर्मियों को ₹30-50 लाख जीवन बीमा + विकलांगता कवर",
        "eligibility": "All serving Indian Navy personnel",
        "documents": ["Service record", "NGIS membership", "Nomination form"],
        "apply_url": "https://indiannavy.nic.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Air Force Group Insurance Society (AFGIS)",
        "ministry": "Ministry of Defence (Air Force)",
        "benefit": "Life cover Rs 50 lakh + educational grants for wards of IAF personnel",
        "benefit_hi": "IAF कर्मियों को ₹50 लाख जीवन बीमा + बच्चों को शैक्षिक अनुदान",
        "eligibility": "All serving Indian Air Force personnel",
        "documents": ["Service record", "AFGIS card", "Nomination"],
        "apply_url": "https://iafgis.com",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Ex-Servicemen Resettlement Scheme (MSME Loan)",
        "ministry": "Ministry of MSME / KSB",
        "benefit": "Collateral-free business loans up to Rs 25 lakh with preferential interest rate",
        "benefit_hi": "भूतपूर्व सैनिकों को बिना गारंटी ₹25 लाख तक व्यापार ऋण",
        "eligibility": "Retired defence personnel starting new business ventures",
        "documents": ["Discharge certificate", "Aadhaar", "Business plan", "Bank account"],
        "apply_url": "https://ksb.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "One Rank One Pension (OROP)",
        "ministry": "Ministry of Defence",
        "benefit": "Uniform pension for same rank/length of service regardless of retirement date; revised every 5 years",
        "benefit_hi": "समान रैंक और सेवा अवधि पर एक समान पेंशन; हर 5 साल में संशोधन",
        "eligibility": "All retired defence personnel (Army, Navy, Air Force)",
        "documents": ["PPO", "Aadhaar", "Discharge book", "Bank account"],
        "apply_url": "https://desw.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Sainik School Admission (Reserved Seats)",
        "ministry": "Ministry of Defence",
        "benefit": "25% reserved seats + fee concession for wards of defence/ex-servicemen in 33 Sainik Schools",
        "benefit_hi": "33 सैनिक स्कूलों में रक्षा कर्मियों के बच्चों के लिए 25% आरक्षण + शुल्क रियायत",
        "eligibility": "Wards of serving/retired defence personnel aged 10-12 (Class 6) or 13-15 (Class 9)",
        "documents": ["Service/discharge certificate", "Aadhaar", "Birth certificate", "School marksheet"],
        "apply_url": "https://sainikschooladmission.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Kendriya Vidyalaya Priority Admission",
        "ministry": "HRD / Ministry of Defence",
        "benefit": "Priority Category 1 admission at all 1,250+ KVs for children of serving defence personnel",
        "benefit_hi": "सेवारत रक्षा कर्मियों के बच्चों को KV में प्राथमिकता प्रवेश (श्रेणी 1)",
        "eligibility": "Children of serving defence personnel (transferred frequently)",
        "documents": ["Service certificate with posting order", "Aadhaar", "Birth certificate"],
        "apply_url": "https://kvsangathan.nic.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "AWWA Scholarship (Army Wives Welfare Association)",
        "ministry": "Army / AWWA",
        "benefit": "Scholarships Rs 1,000-5,000/month for wards of deceased/disabled soldiers",
        "benefit_hi": "शहीद/विकलांग सैनिकों के बच्चों को ₹1,000-5,000/माह छात्रवृत्ति",
        "eligibility": "Wards of deceased, disabled, or low-income Army personnel",
        "documents": ["Service/death certificate", "Disability certificate if applicable", "Aadhaar", "School enrollment"],
        "apply_url": "https://awwa.nic.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Gallantry Award Annuity",
        "ministry": "Ministry of Defence / Home Affairs",
        "benefit": "Monthly annuity Rs 3,000-20,000 for Param Vir Chakra, Vir Chakra, Ashok Chakra awardees",
        "benefit_hi": "परम वीर चक्र, वीर चक्र, अशोक चक्र विजेताओं को ₹3,000-20,000/माह वार्षिकी",
        "eligibility": "Personnel who have received national gallantry awards",
        "documents": ["Gallantry award certificate", "Aadhaar", "Bank account"],
        "apply_url": "https://desw.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "SPARSH (System for Pension Administration Raksha)",
        "ministry": "Ministry of Defence",
        "benefit": "Direct, paperless pension disbursement to defence pensioners bank accounts with grievance portal",
        "benefit_hi": "रक्षा पेंशनभोगियों को सीधे बैंक में डिजिटल पेंशन + शिकायत पोर्टल",
        "eligibility": "All defence pensioners (Army/Navy/Air Force retired)",
        "documents": ["PPO", "Aadhaar", "Bank account"],
        "apply_url": "https://sparsh.defencepension.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Defence Land Allotment Scheme",
        "ministry": "Ministry of Defence",
        "benefit": "Subsidized residential plots in designated areas for serving/retired defence personnel",
        "benefit_hi": "सेवारत/भूतपूर्व रक्षा कर्मियों को नामित क्षेत्रों में सब्सिडी पर आवासीय भूमि",
        "eligibility": "Serving and retired defence personnel (priority to battle casualties)",
        "documents": ["Service certificate", "Discharge book", "Aadhaar", "No-property certificate"],
        "apply_url": "https://desw.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Ex-Servicemen Self-Employment Scheme (EXSSECS)",
        "ministry": "Ministry of Labour / KSB",
        "benefit": "Free skill training + placement support + Rs 1 lakh startup grant for resettlement",
        "benefit_hi": "पुनर्वास के लिए मुफ्त कौशल प्रशिक्षण + ₹1 लाख स्टार्टअप अनुदान",
        "eligibility": "Retired defence personnel within 2 years of discharge",
        "documents": ["Discharge certificate", "Aadhaar", "Bank account"],
        "apply_url": "https://ksb.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Central Sainik Board (CSB) Welfare Funds",
        "ministry": "Ministry of Defence / KSB",
        "benefit": "Emergency financial assistance (Rs 10,000-50,000) for ex-servicemen in distress",
        "benefit_hi": "जरूरतमंद भूतपूर्व सैनिकों को आपातकालीन वित्तीय सहायता ₹10,000-50,000",
        "eligibility": "Ex-servicemen and war widows in financial distress",
        "documents": ["Discharge certificate", "Aadhaar", "Bank account", "Application to Zila Sainik Board"],
        "apply_url": "https://ksb.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Priority Ration Card for Defence Families",
        "ministry": "State Food Departments (Central directive)",
        "benefit": "Priority Household (PHH) ration card regardless of income for families of battle casualties",
        "benefit_hi": "युद्ध शहीदों के परिवारों को आय सीमा के बिना PHH राशन कार्ड",
        "eligibility": "Families of defence personnel killed in action (battle casualty)",
        "documents": ["Death/casualty certificate", "Aadhaar", "Family ID"],
        "apply_url": "State food department portal",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Rejuvenation of Infrastructure in Sainik Rest Houses",
        "ministry": "Ministry of Defence / KSB",
        "benefit": "Subsidized accommodation at Sainik Rest Houses across India for travelling veterans",
        "benefit_hi": "यात्रारत भूतपूर्व सैनिकों को देशभर में सैनिक रेस्ट हाउस में सब्सिडी पर आवास",
        "eligibility": "All ex-servicemen and their dependents",
        "documents": ["ECHS/ID card", "Aadhaar"],
        "apply_url": "https://ksb.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "Defence Pension Adalat (Grievance Redressal)",
        "ministry": "Ministry of Defence",
        "benefit": "Regular camps to resolve pending pension/disability/family pension grievances on-the-spot",
        "benefit_hi": "पेंशन/विकलांगता/पारिवारिक पेंशन शिकायतों के मौके पर निपटारे के लिए नियमित शिविर",
        "eligibility": "All defence pensioners with unresolved pension issues",
        "documents": ["PPO", "Discharge certificate", "Grievance application"],
        "apply_url": "https://desw.gov.in",
        "sector": "defence",
        "type": "Central"
    },
    {
        "name": "National Defence Fund (NDF) — Welfare Grants",
        "ministry": "PMO / Ministry of Defence",
        "benefit": "Education scholarships + financial grants to wards of battle casualties from PM's fund",
        "benefit_hi": "PM के राष्ट्रीय रक्षा कोष से युद्ध शहीदों के बच्चों को शिक्षा छात्रवृत्ति",
        "eligibility": "Wards and widows of defence/paramilitary personnel killed in action",
        "documents": ["Casualty certificate", "Aadhaar", "Educational proof", "Bank account"],
        "apply_url": "https://ndf.gov.in",
        "sector": "defence",
        "type": "Central"
    },
]

def save():
    os.makedirs("schemes", exist_ok=True)
    os.makedirs("schemes/combined", exist_ok=True)
    os.makedirs("schemes/state_by_sector", exist_ok=True)

    # Save as its own sector file
    out = {"sector": "defence", "schemes": DEFENCE_SCHEMES}
    with open("schemes/defence.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ defence.json: {len(DEFENCE_SCHEMES)} schemes saved")

    # Also save in combined/ (no state schemes for defence, so same file)
    combined = {
        "sector": "defence",
        "central_count": len(DEFENCE_SCHEMES),
        "state_count": 0,
        "total": len(DEFENCE_SCHEMES),
        "central_schemes": DEFENCE_SCHEMES,
        "state_schemes": [],
        "note": "Defence schemes are central by nature; state-level schemes are handled via Rajya Sainik Boards"
    }
    with open("schemes/combined/defence.json", "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"✅ combined/defence.json saved")
    print(f"\n🎉 {len(DEFENCE_SCHEMES)} defence schemes added")
    print("   Covers: ECHS, OROP, pensions, insurance, education, resettlement, gallantry awards")

if __name__ == "__main__":
    save()
