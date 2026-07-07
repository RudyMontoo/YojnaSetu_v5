import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import { ai } from "./api";

// UI language layer. English is the default; the switcher in the Navbar
// changes every registered string live. Chat/voice language is separate —
// the AI already auto-detects the citizen's spoken/typed language.
export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "bn", label: "বাংলা" },
  { code: "ta", label: "தமிழ்" },
  { code: "te", label: "తెలుగు" },
  { code: "mr", label: "मराठी" },
];

const STRINGS = {
  // nav
  "nav.home":     { en: "Home", hi: "होम", bn: "হোম", ta: "முகப்பு", te: "హోమ్", mr: "होम" },
  "nav.sathi":    { en: "Sathi", hi: "साथी", bn: "সাথী", ta: "சாத்தி", te: "సాథి", mr: "साथी" },
  "nav.schemes":  { en: "Schemes", hi: "योजनाएं", bn: "প্রকল্প", ta: "திட்டங்கள்", te: "పథకాలు", mr: "योजना" },
  "nav.status":   { en: "Status", hi: "स्थिति", bn: "স্ট্যাটাস", ta: "நிலை", te: "స్థితి", mr: "स्थिती" },
  "nav.lens":     { en: "Lens", hi: "लेंस", bn: "লেন্স", ta: "லென்ஸ்", te: "లెన్స్", mr: "लेन्स" },
  "nav.profile":  { en: "Profile", hi: "प्रोफ़ाइल", bn: "প্রোফাইল", ta: "சுயவிவரம்", te: "ప్రొఫైల్", mr: "प्रोफाइल" },
  // home hero
  "home.greet":    { en: "Namaste,", hi: "नमस्ते,", bn: "নমস্তে,", ta: "வணக்கம்,", te: "నమస్తే,", mr: "नमस्कार," },
  "home.tagline":  { en: "Your rights. Your schemes. One place.", hi: "आपके अधिकार। आपकी योजनाएं। एक जगह।", bn: "আপনার অধিকার। আপনার প্রকল্প। এক জায়গায়।", ta: "உங்கள் உரிமைகள். உங்கள் திட்டங்கள். ஒரே இடம்.", te: "మీ హక్కులు. మీ పథకాలు. ఒకే చోట.", mr: "तुमचे हक्क. तुमच्या योजना. एकाच ठिकाणी." },
  "home.findScheme": { en: "Find My Scheme", hi: "मेरी योजना खोजें", bn: "আমার প্রকল্প খুঁজুন", ta: "என் திட்டத்தைக் கண்டறி", te: "నా పథకాన్ని కనుగొనండి", mr: "माझी योजना शोधा" },
  "home.exploreAll": { en: "Explore All", hi: "सभी देखें", bn: "সব দেখুন", ta: "அனைத்தையும் பார்", te: "అన్నీ చూడండి", mr: "सर्व पहा" },
  "home.personalGuide": { en: "Personal Guide", hi: "निजी मार्गदर्शक", bn: "ব্যক্তিগত গাইড", ta: "தனிப்பட்ட வழிகாட்டி", te: "వ్యక్తిగత గైడ్", mr: "वैयक्तिक मार्गदर्शक" },
  "home.meetSathi": { en: "Meet Sathi AI", hi: "साथी AI से मिलिए", bn: "সাথী AI-এর সাথে পরিচিত হন", ta: "சாத்தி AI-ஐ சந்தியுங்கள்", te: "సాథి AIని కలవండి", mr: "साथी AI ला भेटा" },
  "home.sathiDesc": { en: "Your AI guide for government schemes. Ask in any Indian language about eligibility, documents, and how to apply.", hi: "सरकारी योजनाओं के लिए आपका AI मार्गदर्शक। किसी भी भारतीय भाषा में पात्रता, दस्तावेज़ और आवेदन के बारे में पूछें।", bn: "সরকারি প্রকল্পের জন্য আপনার AI গাইড। যেকোনো ভারতীয় ভাষায় যোগ্যতা, নথি এবং আবেদন সম্পর্কে জিজ্ঞাসা করুন।", ta: "அரசு திட்டங்களுக்கான உங்கள் AI வழிகாட்டி. தகுதி, ஆவணங்கள் மற்றும் விண்ணப்பிப்பது பற்றி எந்த இந்திய மொழியிலும் கேளுங்கள்.", te: "ప్రభుత్వ పథకాల కోసం మీ AI గైడ్. అర్హత, పత్రాలు మరియు దరఖాస్తు గురించి ఏ భారతీయ భాషలోనైనా అడగండి.", mr: "सरकारी योजनांसाठी तुमचा AI मार्गदर्शक. पात्रता, कागदपत्रे आणि अर्ज कसा करायचा याबद्दल कोणत्याही भारतीय भाषेत विचारा." },
  "home.chatNow":  { en: "Chat Now", hi: "चैट करें", bn: "চ্যাট করুন", ta: "அரட்டை", te: "చాట్ చేయండి", mr: "चॅट करा" },
  "home.voice":    { en: "Voice", hi: "आवाज़", bn: "ভয়েস", ta: "குரல்", te: "వాయిస్", mr: "आवाज" },
  "home.catEyebrow": { en: "Government Schemes", hi: "सरकारी योजनाएं", bn: "সরকারি প্রকল্প", ta: "அரசு திட்டங்கள்", te: "ప్రభుత్వ పథకాలు", mr: "सरकारी योजना" },
  "home.categories": { en: "Categories", hi: "श्रेणियां", bn: "বিভাগ", ta: "வகைகள்", te: "వర్గాలు", mr: "श्रेणी" },
  "home.view":     { en: "View", hi: "देखें", bn: "দেখুন", ta: "பார்", te: "చూడండి", mr: "पहा" },
  // chat
  "chat.greeting": { en: "Namaste! I am Sathi, your AI guide for government schemes.\n\nTap the mic to speak in any Indian language, or type your question below.", hi: "नमस्ते! मैं साथी हूं — सरकारी योजनाओं के लिए आपका AI मार्गदर्शक।\n\nकिसी भी भारतीय भाषा में बोलने के लिए माइक दबाएं, या नीचे अपना सवाल लिखें।", bn: "নমস্তে! আমি সাথী — সরকারি প্রকল্পের জন্য আপনার AI গাইড।\n\nযেকোনো ভারতীয় ভাষায় কথা বলতে মাইক চাপুন, বা নিচে প্রশ্ন লিখুন।", ta: "வணக்கம்! நான் சாத்தி — அரசு திட்டங்களுக்கான உங்கள் AI வழிகாட்டி.\n\nஎந்த இந்திய மொழியிலும் பேச மைக்கை அழுத்துங்கள், அல்லது கீழே கேள்வியை எழுதுங்கள்.", te: "నమస్తే! నేను సాథి — ప్రభుత్వ పథకాల కోసం మీ AI గైడ్.\n\nఏ భారతీయ భాషలోనైనా మాట్లాడటానికి మైక్ నొక్కండి, లేదా క్రింద మీ ప్రశ్నను టైప్ చేయండి.", mr: "नमस्कार! मी साथी — सरकारी योजनांसाठी तुमचा AI मार्गदर्शक.\n\nकोणत्याही भारतीय भाषेत बोलण्यासाठी माइक दाबा, किंवा खाली प्रश्न लिहा." },
  "chat.placeholder": { en: "Ask about any scheme…", hi: "किसी भी योजना के बारे में पूछें…", bn: "যেকোনো প্রকল্প সম্পর্কে জিজ্ঞাসা করুন…", ta: "எந்தத் திட்டம் பற்றியும் கேளுங்கள்…", te: "ఏ పథకం గురించైనా అడగండి…", mr: "कोणत्याही योजनेबद्दल विचारा…" },
};

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    const code = localStorage.getItem("yojna_lang") || "en";
    if (typeof document !== "undefined") document.documentElement.lang = code;
    return code;
  });

  const setLang = useCallback((code) => {
    localStorage.setItem("yojna_lang", code);
    document.documentElement.lang = code;  // browsers must know the real language
    setLangState(code);
  }, []);

  const t = useCallback(
    (key) => STRINGS[key]?.[lang] ?? STRINGS[key]?.en ?? key,
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLang() {
  return useContext(LanguageContext);
}

// ── Live translation for DYNAMIC text (scheme names, benefits, and any page
// label not hand-registered in STRINGS) ──────────────────────────────────────
// The static dictionary above can only cover a fixed phrase set; it can't
// translate the 1,900+ scheme strings that come from the database. This hook
// batches whatever English strings a component passes in to the cached
// /translate endpoint (Sarvam Mayura, server-side cached), and returns a
// tr(str) lookup. English → identity (no network). Client-side cache means
// switching languages back and forth never re-fetches.

const _clientCache = new Map(); // key `${lang}:${text}` -> translated

export function useAutoTranslate(texts) {
  const { lang } = useLang();
  const [, force] = useState(0);
  const list = Array.isArray(texts) ? texts.filter(Boolean) : [];
  const key = list.join("\u0000"); // stable content-based effect dependency

  useEffect(() => {
    if (lang === "en" || list.length === 0) return;
    const uniq = [...new Set(list)];
    const missing = uniq.filter((t) => !_clientCache.has(lang + ":" + t));
    if (missing.length === 0) return;
    let cancelled = false;
    ai.translate(missing, lang)
      .then((res) => {
        if (cancelled) return;
        (res.translations || []).forEach((tr, i) => {
          _clientCache.set(lang + ":" + missing[i], tr);
        });
        force((n) => n + 1); // re-render with freshly cached translations
      })
      .catch(() => {}); // graceful: fall back to original English
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, key]);

  // tr(original) -> translated (original as fallback while loading / on error)
  return useCallback(
    (s) => (lang === "en" || !s ? s : _clientCache.get(lang + ":" + s) || s),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [lang, key]
  );
}
