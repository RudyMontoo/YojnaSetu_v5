"""State schemes - Remaining 16 states (bilingual)"""

REMAINING_STATES = {
    "uttarakhand": {
        "state_en": "Uttarakhand", "state_hi": "उत्तराखंड",
        "schemes": [
            {"name_en": "Mukhyamantri Swarozgar Yojana (UK)", "name_hi": "मुख्यमंत्री स्वरोजगार योजना",
             "benefit_en": "Loans Rs 25,000-25 lakh with 25% marginal money grant for youth enterprises", "benefit_hi": "युवा उद्यमों के लिए ₹25,000-25 लाख ऋण + 25% मार्जिन मनी अनुदान",
             "eligibility": "UK domicile, age 18-45, education min Class 8", "documents": ["Aadhaar", "UK domicile", "Business plan", "Bank account"], "apply_url": "https://msy.uk.gov.in", "sector": "employment"},
            {"name_en": "Vatsalya Yojana (UK)", "name_hi": "वात्सल्य योजना (उत्तराखंड)",
             "benefit_en": "Rs 900/month for children orphaned by COVID-19 till age 21 + education support", "benefit_hi": "COVID से अनाथ बच्चों को 21 वर्ष तक ₹900/माह + शिक्षा सहायता",
             "eligibility": "Children who lost both parents to COVID in Uttarakhand", "documents": ["Death certificates", "Birth certificate", "Aadhaar"], "apply_url": "https://uk.gov.in", "sector": "women_child"},
            {"name_en": "Uttarakhand Gramin Himalayan Scheme", "name_hi": "उत्तराखंड ग्रामीण हिमालय योजना",
             "benefit_en": "Enhanced MGNREGA wages + additional 50 days for hill/remote districts", "benefit_hi": "पहाड़ी/दूरस्थ जिलों में बेहतर MGNREGA मजदूरी + 50 अतिरिक्त दिन",
             "eligibility": "MGNREGA job card holders in hilly districts of Uttarakhand", "documents": ["Job card", "Aadhaar", "Bank account"], "apply_url": "https://nrega.nic.in", "sector": "rural_development"},
            {"name_en": "Atal Ayushman Uttarakhand Yojana", "name_hi": "अटल आयुष्मान उत्तराखंड योजना",
             "benefit_en": "Rs 5 lakh/year health insurance for all UK families (extends PM-JAY)", "benefit_hi": "सभी UK परिवारों को ₹5 लाख/वर्ष स्वास्थ्य बीमा",
             "eligibility": "All Uttarakhand residents (UK domicile)", "documents": ["Aadhaar", "UK domicile/ration card"], "apply_url": "https://ayushmanuttarakhand.org", "sector": "health"},
            {"name_en": "Mukhyamantri Kisan Protsahan Nidhi", "name_hi": "मुख्यमंत्री किसान प्रोत्साहन निधि",
             "benefit_en": "Rs 2,000/year additional input support to UK hill farmers on top of PM Kisan", "benefit_hi": "PM Kisan के अतिरिक्त पहाड़ी किसानों को ₹2,000/वर्ष",
             "eligibility": "PM Kisan-enrolled farmers in Uttarakhand", "documents": ["PM Kisan registration", "Aadhaar", "Bank account"], "apply_url": "https://uk.gov.in", "sector": "agriculture"},
            {"name_en": "Homestay Yojana (UK Tourism Support)", "name_hi": "होमस्टे योजना (UK पर्यटन)",
             "benefit_en": "Interest subsidy + training for rural families to set up homestays for tourists", "benefit_hi": "ग्रामीण परिवारों को होमस्टे के लिए ब्याज सब्सिडी + प्रशिक्षण",
             "eligibility": "Rural Uttarakhand families in tourist areas", "documents": ["Aadhaar", "Land/house proof", "Bank account"], "apply_url": "https://uttarakhandtourism.gov.in", "sector": "employment"},
        ]
    },
    "goa": {
        "state_en": "Goa", "state_hi": "गोवा",
        "schemes": [
            {"name_en": "Dayanand Social Security Scheme (DSSS)", "name_hi": "दयानंद सामाजिक सुरक्षा योजना",
             "benefit_en": "Rs 2,500/month pension for all Goa residents aged 18+ below poverty line", "benefit_hi": "गोवा BPL निवासियों को ₹2,500/माह पेंशन",
             "eligibility": "Goa domicile, BPL, aged 18+, not receiving other pension", "documents": ["Aadhaar", "Goa domicile", "BPL card", "Bank account"], "apply_url": "https://goaonline.gov.in", "sector": "social_security"},
            {"name_en": "Griha Aadhar (Goa Housing Support)", "name_hi": "गृह आधार (गोवा)",
             "benefit_en": "Rs 2,500/month to housewife of Goa domicile family for household support", "benefit_hi": "गोवा डोमिसाइल परिवार की गृहिणी को ₹2,500/माह घरेलू सहायता",
             "eligibility": "Married women with Goa domicile, family income < Rs 3 lakh/month", "documents": ["Aadhaar", "Goa domicile", "Marriage certificate", "Bank account"], "apply_url": "https://goaonline.gov.in", "sector": "women_child"},
            {"name_en": "Mukhyamantri Shetkari Sahay Nidhi (Goa)", "name_hi": "मुख्यमंत्री शेतकरी सहाय निधि (गोवा)",
             "benefit_en": "Financial support for Goa farmers affected by weather/crop failure", "benefit_hi": "गोवा किसानों को मौसम/फसल नुकसान पर वित्तीय सहायता",
             "eligibility": "Registered Goa farmers with verifiable crop loss", "documents": ["Aadhaar", "Land records", "Crop loss report", "Bank account"], "apply_url": "https://agri.goa.gov.in", "sector": "agriculture"},
            {"name_en": "Bhajanaseva / Senior Citizen Pension Goa", "name_hi": "भजनसेवा / वरिष्ठ नागरिक पेंशन",
             "benefit_en": "Rs 4,000/month pension for destitute senior citizens in Goa", "benefit_hi": "गोवा के असहाय वृद्धों को ₹4,000/माह पेंशन",
             "eligibility": "Goa domicile, aged 60+, destitute/very low income", "documents": ["Aadhaar", "Goa domicile", "Age proof", "Bank account"], "apply_url": "https://goaonline.gov.in", "sector": "senior_citizens"},
            {"name_en": "Kali Mata Scheme (Marriage Assistance Goa)", "name_hi": "काली माता योजना (विवाह सहायता गोवा)",
             "benefit_en": "Rs 5,000 grant for marriage of BPL girl child in Goa", "benefit_hi": "गोवा BPL बालिका के विवाह पर ₹5,000 अनुदान",
             "eligibility": "Goa BPL families, bride aged 18+", "documents": ["Aadhaar", "BPL card", "Marriage proof", "Bank account"], "apply_url": "https://goaonline.gov.in", "sector": "women_child"},
        ]
    },
    "jammu_kashmir": {
        "state_en": "Jammu & Kashmir", "state_hi": "जम्मू & कश्मीर",
        "schemes": [
            {"name_en": "PMDP — Prime Minister's Development Package for J&K", "name_hi": "प्रधानमंत्री विकास पैकेज जम्मू-कश्मीर",
             "benefit_en": "Rs 80,000 crore infrastructure + employment + industrial development package for J&K", "benefit_hi": "J&K के लिए ₹80,000 करोड़ बुनियादी ढाँचा + रोजगार + औद्योगिक विकास",
             "eligibility": "J&K domicile residents benefiting from public infrastructure works", "documents": ["Aadhaar", "J&K domicile"], "apply_url": "https://jkgov.gov.in", "sector": "rural_development"},
            {"name_en": "J&K Back to Village (B2V) Programme", "name_hi": "बैक टू विलेज (B2V) कार्यक्रम",
             "benefit_en": "Government officers visit villages to deliver 26 schemes at doorstep", "benefit_hi": "सरकारी अधिकारी गाँव आकर 26 योजनाओं का लाभ पहुँचाते हैं",
             "eligibility": "All J&K rural residents", "documents": ["Aadhaar", "Relevant scheme-specific documents"], "apply_url": "https://jkgov.gov.in", "sector": "rural_development"},
            {"name_en": "Apni Zameen Apna Makaan (J&K Housing)", "name_hi": "अपनी जमीन अपना मकान",
             "benefit_en": "Residential plots allocation at subsidized rates for West Pakistan refugees and landless", "benefit_hi": "पश्चिमी पाकिस्तान शरणार्थियों और भूमिहीनों को सब्सिडी दर पर भूखंड",
             "eligibility": "West Pakistan refugees settled in J&K, landless families", "documents": ["Refugee certificate", "Aadhaar", "Landless proof"], "apply_url": "https://jkgov.gov.in", "sector": "housing"},
            {"name_en": "J&K Industrial Incentive Scheme (JKIIS)", "name_hi": "J&K औद्योगिक प्रोत्साहन योजना",
             "benefit_en": "Capital investment subsidy 30-50% + GST reimbursement for new industrial units in J&K", "benefit_hi": "J&K में नई औद्योगिक इकाइयों को 30-50% पूंजी निवेश सब्सिडी + GST वापसी",
             "eligibility": "Entrepreneurs setting up industries in J&K", "documents": ["Aadhaar", "J&K domicile", "Business plan", "Bank account"], "apply_url": "https://jkindustries.gov.in", "sector": "employment"},
            {"name_en": "HADP — Holistic Agriculture Development Plan (J&K)", "name_hi": "कृषि समग्र विकास कार्यक्रम J&K",
             "benefit_en": "Rs 5,000 crore for horticulture, organic farming, saffron + farmer income doubling in J&K", "benefit_hi": "J&K में बागवानी, जैविक खेती, केसर + किसान आय दोगुनी करने के लिए ₹5,000 करोड़",
             "eligibility": "J&K farmers especially in horticulture/saffron/organic segments", "documents": ["Aadhaar", "Land records", "Bank account"], "apply_url": "https://jkagri.gov.in", "sector": "agriculture"},
            {"name_en": "Umbrella Scheme for SC/ST in J&K", "name_hi": "J&K SC/ST छाता योजना",
             "benefit_en": "Education, housing, economic support for SC/ST communities in J&K", "benefit_hi": "J&K में SC/ST समुदायों को शिक्षा, आवास, आर्थिक सहायता",
             "eligibility": "SC/ST communities in J&K", "documents": ["SC/ST certificate", "Aadhaar", "J&K domicile"], "apply_url": "https://jkgov.gov.in", "sector": "sc_welfare"},
        ]
    },
    "tripura": {
        "state_en": "Tripura", "state_hi": "त्रिपुरा",
        "schemes": [
            {"name_en": "Mukhyamantri Vigyan Unnayan Yojana", "name_hi": "मुख्यमंत्री विज्ञान उन्नयन योजना",
             "benefit_en": "Free science equipment, lab setup for government school students in Tripura", "benefit_hi": "त्रिपुरा सरकारी स्कूल छात्रों को मुफ्त विज्ञान उपकरण, प्रयोगशाला",
             "eligibility": "Students at government schools in Tripura (Class 8-12)", "documents": ["School enrollment", "Aadhaar"], "apply_url": "https://tripura.gov.in", "sector": "education"},
            {"name_en": "Tripura Swasthya Sati (Health Scheme)", "name_hi": "त्रिपुरा स्वास्थ्य साथी",
             "benefit_en": "Rs 2 lakh/year cashless health cover for BPL Tripura families", "benefit_hi": "त्रिपुरा BPL परिवारों को ₹2 लाख/वर्ष कैशलेस स्वास्थ्य बीमा",
             "eligibility": "Tripura BPL families", "documents": ["Aadhaar", "BPL card", "Tripura residence"], "apply_url": "https://tripura.gov.in", "sector": "health"},
            {"name_en": "Mukhyamantri Griha Nirman Yojana (Tripura)", "name_hi": "मुख्यमंत्री गृह निर्माण योजना",
             "benefit_en": "Rs 1.5 lakh state housing grant for BPL families in Tripura not under PMAY", "benefit_hi": "PMAY से बाहर त्रिपुरा BPL परिवारों को ₹1.5 लाख राज्य अनुदान",
             "eligibility": "Tripura BPL families without own house", "documents": ["Aadhaar", "BPL card", "Land/plot ownership"], "apply_url": "https://tripura.gov.in", "sector": "housing"},
            {"name_en": "Rubber Board Support Scheme (Tripura)", "name_hi": "रबर बोर्ड सहायता योजना",
             "benefit_en": "Replanting subsidy + skill training for rubber farmers in Tripura", "benefit_hi": "त्रिपुरा के रबर किसानों को पुनरोपण सब्सिडी + प्रशिक्षण",
             "eligibility": "Tripura small rubber farmers", "documents": ["Aadhaar", "Land records", "Rubber Board registration"], "apply_url": "https://rubberboard.org.in", "sector": "agriculture"},
        ]
    },
    "nagaland": {
        "state_en": "Nagaland", "state_hi": "नागालैंड",
        "schemes": [
            {"name_en": "Nagaland Bamboo Mission", "name_hi": "नागालैंड बाँस मिशन",
             "benefit_en": "Bamboo cultivation support + value addition units + market linkage for tribal farmers", "benefit_hi": "जनजातीय किसानों को बाँस खेती + मूल्य संवर्धन + बाजार संपर्क",
             "eligibility": "Nagaland tribal farmers with land for bamboo", "documents": ["Aadhaar", "ST certificate", "Land records"], "apply_url": "https://nagaland.gov.in", "sector": "agriculture"},
            {"name_en": "Nagaland State Youth Entrepreneurship Policy", "name_hi": "नागालैंड युवा उद्यमिता नीति",
             "benefit_en": "Seed grants Rs 5-10 lakh + mentoring for Nagaland youth startups", "benefit_hi": "नागालैंड युवाओं को ₹5-10 लाख बीज अनुदान + मेंटरिंग",
             "eligibility": "Nagaland youth aged 18-35 with innovative business idea", "documents": ["Aadhaar", "Nagaland domicile", "Business plan"], "apply_url": "https://nagaland.gov.in", "sector": "employment"},
            {"name_en": "Nagaland Organic Mission", "name_hi": "नागालैंड जैविक मिशन",
             "benefit_en": "Full support for organic certification + access to premium markets for NE organic produce", "benefit_hi": "जैविक प्रमाणन + NE जैविक उत्पाद के लिए प्रीमियम बाजार",
             "eligibility": "Nagaland farmers practicing organic farming", "documents": ["Aadhaar", "Land records", "Organic practice declaration"], "apply_url": "https://nagaland.gov.in", "sector": "agriculture"},
            {"name_en": "Nagaland Free Coaching for UPSC/State PSC", "name_hi": "UPSC/राज्य PSC मुफ्त कोचिंग",
             "benefit_en": "Free coaching in Kohima/Mumbai for Nagaland civil services aspirants", "benefit_hi": "नागालैंड के UPSC/PSC उम्मीदवारों के लिए कोहिमा/मुंबई में मुफ्त कोचिंग",
             "eligibility": "Nagaland domicile youth with graduation degree", "documents": ["Aadhaar", "Nagaland domicile", "Degree certificate"], "apply_url": "https://nagaland.gov.in", "sector": "education"},
        ]
    },
    "manipur": {
        "state_en": "Manipur", "state_hi": "मणिपुर",
        "schemes": [
            {"name_en": "Imphal Free Zone (IFZ) Industrial Incentives", "name_hi": "इम्फाल मुक्त क्षेत्र औद्योगिक प्रोत्साहन",
             "benefit_en": "Tax holidays + capital subsidy for industries in Manipur industrial zones", "benefit_hi": "मणिपुर औद्योगिक क्षेत्रों में उद्योगों को टैक्स छूट + पूंजी सब्सिडी",
             "eligibility": "Entrepreneurs setting up in Manipur industrial zones", "documents": ["Aadhaar", "Business registration", "Project plan"], "apply_url": "https://manipur.gov.in", "sector": "employment"},
            {"name_en": "Chief Minister Gi Harana (Manipur Farmer Support)", "name_hi": "मुख्यमंत्री गी हरना (किसान सहायता मणिपुर)",
             "benefit_en": "Rs 6,000/year additional farmer support on top of PM Kisan for Manipur farmers", "benefit_hi": "PM Kisan के अतिरिक्त मणिपुर किसानों को ₹6,000/वर्ष",
             "eligibility": "PM Kisan-enrolled Manipur farmers", "documents": ["PM Kisan registration", "Aadhaar", "Land records"], "apply_url": "https://manipur.gov.in", "sector": "agriculture"},
            {"name_en": "Manipur Sports University Scholarship", "name_hi": "मणिपुर खेल विश्वविद्यालय छात्रवृत्ति",
             "benefit_en": "Free education + Rs 5,000/month stipend for sports students at Manipur Sports University", "benefit_hi": "मणिपुर स्पोर्ट्स यूनिवर्सिटी छात्रों को मुफ्त शिक्षा + ₹5,000/माह",
             "eligibility": "Students admitted to Manipur Sports University", "documents": ["Aadhaar", "Admission letter", "Sports certificate"], "apply_url": "https://msu.ac.in", "sector": "sports"},
            {"name_en": "Manipur Jan Arogya Yojana", "name_hi": "मणिपुर जन आरोग्य योजना",
             "benefit_en": "Rs 3 lakh/year health coverage for BPL Manipur families at empanelled hospitals", "benefit_hi": "BPL मणिपुर परिवारों को ₹3 लाख/वर्ष स्वास्थ्य बीमा",
             "eligibility": "Manipur BPL families", "documents": ["Aadhaar", "BPL card", "Manipur domicile"], "apply_url": "https://manipur.gov.in", "sector": "health"},
        ]
    },
    "meghalaya": {
        "state_en": "Meghalaya", "state_hi": "मेघालय",
        "schemes": [
            {"name_en": "Meghalaya Health Insurance Scheme (MHIS)", "name_hi": "मेघालय स्वास्थ्य बीमा योजना",
             "benefit_en": "Rs 5 lakh/year cashless treatment at 200+ hospitals for all Meghalaya residents", "benefit_hi": "मेघालय निवासियों को ₹5 लाख/वर्ष कैशलेस इलाज 200+ अस्पतालों में",
             "eligibility": "All Meghalaya residents (domicile required)", "documents": ["Aadhaar", "Meghalaya domicile"], "apply_url": "https://meghalaya.gov.in", "sector": "health"},
            {"name_en": "Meghalaya Basin Development Authority (MBDA) Livelihood", "name_hi": "MBDA आजीविका योजना मेघालय",
             "benefit_en": "Skill training + micro-enterprise support in 4 river basins of Meghalaya", "benefit_hi": "मेघालय की 4 नदी घाटियों में कौशल प्रशिक्षण + सूक्ष्म उद्यम सहायता",
             "eligibility": "Residents along 4 river basin areas of Meghalaya", "documents": ["Aadhaar", "Meghalaya domicile", "Bank account"], "apply_url": "https://meghalaya.gov.in", "sector": "employment"},
            {"name_en": "Orange Revolution Scheme (Meghalaya Orange Farming)", "name_hi": "ऑरेंज रिवोल्यूशन मेघालय",
             "benefit_en": "Subsidy + market linkage for Khasi mandarin orange growers in Meghalaya", "benefit_hi": "मेघालय खासी मंदारिन संतरा उत्पादकों को सब्सिडी + बाजार संपर्क",
             "eligibility": "Meghalaya orange-growing farmers in tribal areas", "documents": ["Aadhaar", "Land records", "Tribe certificate"], "apply_url": "https://meghalaya.gov.in", "sector": "agriculture"},
            {"name_en": "Meghalaya Pension for Senior Citizens", "name_hi": "मेघालय वृद्धावस्था पेंशन",
             "benefit_en": "Rs 1,000/month pension for BPL senior citizens in Meghalaya", "benefit_hi": "मेघालय BPL वृद्धों को ₹1,000/माह पेंशन",
             "eligibility": "Meghalaya domicile, aged 60+, BPL", "documents": ["Aadhaar", "Meghalaya domicile", "Age proof", "Bank account"], "apply_url": "https://meghalaya.gov.in", "sector": "senior_citizens"},
        ]
    },
    "mizoram": {
        "state_en": "Mizoram", "state_hi": "मिजोरम",
        "schemes": [
            {"name_en": "New Land Use Policy (NLUP) Mizoram", "name_hi": "नई भूमि उपयोग नीति मिजोरम",
             "benefit_en": "Financial support for shifting cultivators to adopt settled farming livelihoods", "benefit_hi": "झूम खेती करने वालों को स्थायी कृषि आजीविका अपनाने के लिए वित्तीय सहायता",
             "eligibility": "Mizoram shifting cultivators (jhum farmers)", "documents": ["Aadhaar", "Village membership", "Land record"], "apply_url": "https://mizoram.gov.in", "sector": "agriculture"},
            {"name_en": "Mizoram CM-Comprehensive Health Scheme (CM-CHS)", "name_hi": "मिजोरम CM स्वास्थ्य योजना",
             "benefit_en": "Rs 4 lakh/year cashless treatment for BPL Mizoram families", "benefit_hi": "मिजोरम BPL परिवरों को ₹4 लाख/वर्ष कैशलेस इलाज",
             "eligibility": "Mizoram BPL families", "documents": ["Aadhaar", "Mizoram domicile", "BPL card"], "apply_url": "https://mizoram.gov.in", "sector": "health"},
            {"name_en": "Mizoram Rural Bank Credit for SHGs", "name_hi": "मिजोरम ग्रामीण SHG ऋण योजना",
             "benefit_en": "Subsidized credit via Mizoram Rural Bank for women SHGs in remote areas", "benefit_hi": "दूरस्थ क्षेत्रों में महिला SHG को मिजोरम Rural Bank से रियायती ऋण",
             "eligibility": "Women SHGs registered in Mizoram", "documents": ["SHG registration", "Aadhaar", "Bank account"], "apply_url": "https://mizoram.gov.in", "sector": "financial_inclusion"},
        ]
    },
    "arunachal_pradesh": {
        "state_en": "Arunachal Pradesh", "state_hi": "अरुणाचल प्रदेश",
        "schemes": [
            {"name_en": "CM Arogya Arunachal Yojana", "name_hi": "मुख्यमंत्री आरोग्य अरुणाचल योजना",
             "benefit_en": "Rs 5 lakh/year cashless health cover at 200+ hospitals extending PM-JAY in AP", "benefit_hi": "PM-JAY विस्तार — ₹5 लाख/वर्ष कैशलेस इलाज 200+ अस्पतालों में",
             "eligibility": "All Arunachal Pradesh residents (domicile required)", "documents": ["Aadhaar", "AP domicile certificate"], "apply_url": "https://arunachalpradesh.gov.in", "sector": "health"},
            {"name_en": "Arunachal Pradesh Buddhist Circuit Tourism Development", "name_hi": "अरुणाचल बौद्ध सर्किट पर्यटन योजना",
             "benefit_en": "Grants for homestays, local guides, cultural enterprise along Buddhist circuit", "benefit_hi": "बौद्ध सर्किट पर होमस्टे, स्थानीय गाइड, सांस्कृतिक उद्यम के लिए अनुदान",
             "eligibility": "AP communities near Buddhist monasteries/circuits", "documents": ["Aadhaar", "AP domicile", "Business plan"], "apply_url": "https://arunachalpradesh.gov.in", "sector": "employment"},
            {"name_en": "AP Kiwi / Organic Farming Support", "name_hi": "अरुणाचल प्रदेश कीवी / जैविक खेती",
             "benefit_en": "Subsidy on kiwi, orange, apple plantation + organic certification for AP hill farmers", "benefit_hi": "AP पहाड़ी किसानों को कीवी, संतरा, सेब रोपण + जैविक प्रमाणन सब्सिडी",
             "eligibility": "Arunachal Pradesh farmers with suitable hilly land", "documents": ["Aadhaar", "Land records", "AP domicile"], "apply_url": "https://arunachalpradesh.gov.in", "sector": "agriculture"},
        ]
    },
    "sikkim": {
        "state_en": "Sikkim", "state_hi": "सिक्किम",
        "schemes": [
            {"name_en": "Sikkim Organic Mission (100% Organic State)", "name_hi": "सिक्किम जैविक मिशन (100% जैविक राज्य)",
             "benefit_en": "Input support, certification, premium markets — Sikkim is India's 1st fully organic state", "benefit_hi": "निविष्टि सहायता, प्रमाणन, प्रीमियम बाजार — सिक्किम भारत का पहला जैविक राज्य",
             "eligibility": "All Sikkim farmers (mandatory organic — full government support)", "documents": ["Aadhaar", "Sikkim domicile", "Land records"], "apply_url": "https://sikkim.gov.in", "sector": "agriculture"},
            {"name_en": "Sikkim Universal Health Care Scheme", "name_hi": "सिक्किम सार्वभौमिक स्वास्थ्य देखभाल योजना",
             "benefit_en": "Rs 2 lakh/year comprehensive health cover for all Sikkim families", "benefit_hi": "सभी सिक्किम परिवारों को ₹2 लाख/वर्ष स्वास्थ्य बीमा",
             "eligibility": "All Sikkim residents", "documents": ["Aadhaar", "Sikkim domicile"], "apply_url": "https://sikkim.gov.in", "sector": "health"},
            {"name_en": "Sikkim Swabhiman (Dignity for Senior Citizens)", "name_hi": "सिक्किम स्वाभिमान वृद्धा पेंशन",
             "benefit_en": "Rs 2,000-3,000/month social security pension for all Sikkim senior citizens", "benefit_hi": "सभी सिक्किम वृद्धों को ₹2,000-3,000/माह पेंशन",
             "eligibility": "Sikkim domicile residents aged 60+", "documents": ["Aadhaar", "Sikkim domicile", "Age proof", "Bank account"], "apply_url": "https://sikkim.gov.in", "sector": "senior_citizens"},
        ]
    },
    "ladakh": {
        "state_en": "Ladakh (UT)", "state_hi": "लद्दाख (UT)",
        "schemes": [
            {"name_en": "Ladakh Autonomous Hill Development Council Schemes", "name_hi": "लद्दाख स्वायत्त पर्वतीय विकास परिषद योजनाएं",
             "benefit_en": "Local infrastructure + livelihood grants through LAHDC Leh and LAHDC Kargil", "benefit_hi": "LAHDC लेह और LAHDC कारगिल के माध्यम से स्थानीय बुनियादी ढाँचा + आजीविका",
             "eligibility": "Ladakh UT residents", "documents": ["Aadhaar", "Ladakh domicile"], "apply_url": "https://ladakh.gov.in", "sector": "rural_development"},
            {"name_en": "Snow Leopard Conservation Livelihood Scheme", "name_hi": "हिम तेंदुआ संरक्षण आजीविका योजना",
             "benefit_en": "Income support for herders as community protectors of snow leopards and wildlife", "benefit_hi": "हिम तेंदुए और वन्यजीव संरक्षक समुदाय चरवाहों को आय सहायता",
             "eligibility": "Herding communities near snow leopard habitats in Ladakh", "documents": ["Aadhaar", "Ladakh domicile", "Herder identity"], "apply_url": "https://ladakh.gov.in", "sector": "environment"},
            {"name_en": "Ladakh Tourism Homestay Scheme", "name_hi": "लद्दाख पर्यटन होमस्टे योजना",
             "benefit_en": "Subsidized renovation grants + training for Ladakh families offering tourist homestays", "benefit_hi": "पर्यटक होमस्टे चलाने वाले लद्दाख परिवारों को सब्सिडी + प्रशिक्षण",
             "eligibility": "Ladakh families with space for tourist accommodation", "documents": ["Aadhaar", "Ladakh domicile", "House/property proof"], "apply_url": "https://ladakhtourism.in", "sector": "employment"},
        ]
    },
    "andaman_nicobar": {
        "state_en": "Andaman & Nicobar Islands", "state_hi": "अंडमान निकोबार द्वीप समूह",
        "schemes": [
            {"name_en": "Island Development Agency (IDA) Livelihood Scheme", "name_hi": "द्वीप विकास एजेंसी आजीविका योजना",
             "benefit_en": "Tourism, fisheries, horticulture-based livelihood support for island communities", "benefit_hi": "द्वीप समुदायों के लिए पर्यटन, मत्स्य, बागवानी आधारित आजीविका सहायता",
             "eligibility": "A&N Islands residents in targeted development areas", "documents": ["Aadhaar", "A&N residence proof"], "apply_url": "https://andaman.gov.in", "sector": "employment"},
            {"name_en": "A&N Coconut Development Board Subsidy", "name_hi": "A&N नारियल विकास बोर्ड सब्सिडी",
             "benefit_en": "Input subsidy + replanting support + value-adding unit grants for coconut farmers", "benefit_hi": "नारियल किसानों को निवेश सब्सिडी + पुनरोपण + मूल्य संवर्धन इकाई अनुदान",
             "eligibility": "A&N coconut farmers", "documents": ["Aadhaar", "Land records", "A&N residence"], "apply_url": "https://coconutboard.gov.in", "sector": "agriculture"},
        ]
    },
    "lakshadweep": {
        "state_en": "Lakshadweep", "state_hi": "लक्षद्वीप",
        "schemes": [
            {"name_en": "Integrated Island Development (Lakshadweep UT)", "name_hi": "एकीकृत द्वीप विकास लक्षद्वीप",
             "benefit_en": "Fisheries, tourism, coconut processing — livelihood support for Lakshadweep islanders", "benefit_hi": "मत्स्य, पर्यटन, नारियल प्रसंस्करण — लक्षद्वीप द्वीपवासियों की आजीविका सहायता",
             "eligibility": "Lakshadweep residents", "documents": ["Aadhaar", "Lakshadweep domicile"], "apply_url": "https://lakshadweep.gov.in", "sector": "employment"},
            {"name_en": "Lakshadweep Tuna Fisheries Development", "name_hi": "लक्षद्वीप टूना मत्स्य विकास",
             "benefit_en": "Deep-sea fishing vessel subsidy + cold chain + export facilitation for tuna fishers", "benefit_hi": "टूना मछुआरों को गहरे समुद्र की नाव + कोल्ड चेन + निर्यात सुविधा",
             "eligibility": "Lakshadweep fishing community", "documents": ["Aadhaar", "Fishing license", "Lakshadweep domicile"], "apply_url": "https://lakshadweep.gov.in", "sector": "fisheries"},
        ]
    },
    "chandigarh": {
        "state_en": "Chandigarh (UT)", "state_hi": "चंडीगढ़ (UT)",
        "schemes": [
            {"name_en": "Chandigarh EV Policy 2022", "name_hi": "चंडीगढ़ EV नीति",
             "benefit_en": "Rs 10,000-30,000 subsidy on electric 2/3-wheelers + free charging infrastructure", "benefit_hi": "चंडीगढ़ में EV दोपहिया/तिपहिया पर ₹10,000-30,000 सब्सिडी + मुफ्त चार्जिंग",
             "eligibility": "Chandigarh residents buying approved EVs", "documents": ["Aadhaar", "Chandigarh address proof", "Purchase invoice"], "apply_url": "https://chandigarh.gov.in", "sector": "energy"},
            {"name_en": "Chandigarh Shehri Awas Sahayata Yojana", "name_hi": "चंडीगढ़ शहरी आवास सहायता योजना",
             "benefit_en": "Affordable housing units under PMAY for EWS/LIG in Chandigarh UT", "benefit_hi": "चंडीगढ़ UT में EWS/LIG के लिए PMAY के तहत किफायती आवास",
             "eligibility": "Chandigarh UT EWS/LIG families without own home", "documents": ["Aadhaar", "Income proof", "Chandigarh residence"], "apply_url": "https://chandigarh.gov.in", "sector": "housing"},
        ]
    },
    "puducherry": {
        "state_en": "Puducherry", "state_hi": "पुदुच्चेरी",
        "schemes": [
            {"name_en": "Puducherry Chief Minister Health Insurance Scheme", "name_hi": "पुदुच्चेरी मुख्यमंत्री स्वास्थ्य बीमा",
             "benefit_en": "Rs 5 lakh/year health cover for all Puducherry families at select hospitals", "benefit_hi": "सभी पुदुच्चेरी परिवारों को ₹5 लाख/वर्ष स्वास्थ्य बीमा",
             "eligibility": "All Puducherry UT residents", "documents": ["Aadhaar", "Puducherry domicile/ration card"], "apply_url": "https://puducherry.gov.in", "sector": "health"},
            {"name_en": "Puducherry Adi Dravidar Housing Scheme", "name_hi": "पुदुच्चेरी आदि द्राविड़ आवास योजना",
             "benefit_en": "Free housing + essential amenities for SC/Adi Dravidar families in Puducherry", "benefit_hi": "SC/ आदि द्राविड़ परिवारों को मुफ्त आवास + जरूरी सुविधाएं",
             "eligibility": "SC/Adi Dravidar BPL families in Puducherry", "documents": ["Aadhaar", "SC certificate", "Puducherry domicile"], "apply_url": "https://puducherry.gov.in", "sector": "housing"},
            {"name_en": "Puducherry Special Incentive Scheme for Industries", "name_hi": "पुदुच्चेरी उद्योग विशेष प्रोत्साहन योजना",
             "benefit_en": "Power tariff subsidy + building plan fee waiver for new industries in Puducherry", "benefit_hi": "पुदुच्चेरी में नए उद्योगों को बिजली दर सब्सिडी + नक्शा शुल्क माफी",
             "eligibility": "Entrepreneurs establishing industries in Puducherry UT", "documents": ["Aadhaar", "Business registration", "Project report"], "apply_url": "https://industrypuducherry.gov.in", "sector": "employment"},
        ]
    },
    "dadra_daman_diu": {
        "state_en": "Dadra, Daman & Diu", "state_hi": "दादरा, दमन व दीव",
        "schemes": [
            {"name_en": "DPIIT Industrial Policy — Dadra Nagar Haveli", "name_hi": "DPIIT औद्योगिक नीति – दादरा नगर हवेली",
             "benefit_en": "Income tax & excise benefits + cheap industrial land for factories in DNH", "benefit_hi": "DNH में कारखानों को आयकर/उत्पाद शुल्क लाभ + सस्ती औद्योगिक भूमि",
             "eligibility": "Entrepreneurs setting up manufacturing in DNH", "documents": ["Aadhaar", "Business registration", "Project report"], "apply_url": "https://dnh.nic.in", "sector": "employment"},
            {"name_en": "DNH & DD Housing for Fishermen", "name_hi": "DNH & DD मछुआरा आवास योजना",
             "benefit_en": "Subsidized housing for fishing community in coastal areas of Daman, Diu, DNH", "benefit_hi": "दमन, दीव, DNH के तटीय क्षेत्रों में मछुआरा समुदाय को सब्सिडी आवास",
             "eligibility": "Fishing community residents of DNH & DD", "documents": ["Aadhaar", "Fisherman ID", "UT domicile"], "apply_url": "https://daman.nic.in", "sector": "housing"},
        ]
    },
}

if __name__ == "__main__":
    import json, os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from save_state_schemes import ALL_STATE_SCHEMES
    os.makedirs("schemes/states", exist_ok=True)

    total_new = 0
    for state_key, state_data in REMAINING_STATES.items():
        filepath = f"schemes/states/{state_key}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        count = len(state_data["schemes"])
        total_new += count
        print(f"✅ {state_data['state_en']}: {count} schemes → {filepath}")

    print(f"\n🎉 Added {total_new} schemes across {len(REMAINING_STATES)} new states/UTs")
