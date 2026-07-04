import { useNavigate } from 'react-router-dom'
import { Mic, MessageCircle, ArrowRight, Sparkles } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { Reveal, Stagger, StaggerItem } from '../components/motion'
import { useLang } from '../lib/i18n'
import { useEffect, useState, lazy, Suspense } from 'react'
import { useScroll } from 'framer-motion'
import { TrendingUp, Newspaper } from 'lucide-react'
import { gateway } from '../lib/api'

const MandalaTower3D = lazy(() => import('../components/MandalaTower3D'))
import '../components/components.css'
import './HomePage.css'

// GlobalBackground3D in App.jsx owns the 3D canvas — no canvas needed here.
const prefersReducedMotion = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/* Animated SVG Ashoka Chakra / Mandala */
function MandalaLogo() {
    return (
        <div className="mandala-wrapper">
            <svg className="mandala-svg" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                {/* Outer ring */}
                <circle cx="60" cy="60" r="55" stroke="rgba(232,141,10,0.25)" strokeWidth="1" />
                <circle cx="60" cy="60" r="48" stroke="rgba(232,141,10,0.15)" strokeWidth="0.5" />
                {/* Inner ring */}
                <circle cx="60" cy="60" r="18" stroke="rgba(232,141,10,0.6)" strokeWidth="1.5" fill="rgba(232,141,10,0.06)" />
                {/* Center dot */}
                <circle cx="60" cy="60" r="4" fill="#e88d0a" opacity="0.9" />
                {/* 24 Spokes (Ashoka Chakra) */}
                {Array.from({ length: 24 }).map((_, i) => {
                    const angle = (i * 360) / 24
                    const rad = (angle * Math.PI) / 180
                    const x1 = 60 + 18 * Math.cos(rad)
                    const y1 = 60 + 18 * Math.sin(rad)
                    const x2 = 60 + 48 * Math.cos(rad)
                    const y2 = 60 + 48 * Math.sin(rad)
                    return (
                        <line
                            key={i}
                            x1={x1} y1={y1} x2={x2} y2={y2}
                            stroke={i % 2 === 0 ? 'rgba(232,141,10,0.7)' : 'rgba(232,141,10,0.3)'}
                            strokeWidth={i % 2 === 0 ? '1.2' : '0.6'}
                        />
                    )
                })}
                {/* Decorative dots on outer ring */}
                {Array.from({ length: 8 }).map((_, i) => {
                    const angle = (i * 360) / 8
                    const rad = (angle * Math.PI) / 180
                    const x = 60 + 55 * Math.cos(rad)
                    const y = 60 + 55 * Math.sin(rad)
                    return <circle key={i} cx={x} cy={y} r="2.5" fill="rgba(232,141,10,0.6)" />
                })}
                {/* Glow in center */}
                <circle cx="60" cy="60" r="10" fill="rgba(232,141,10,0.1)" />
            </svg>
            {/* Outer glow ring that pulses */}
            <div className="mandala-glow-ring" />
        </div>
    )
}

const CATEGORIES = [
    { icon: '🌾', label: 'Krishi', sub: 'Agriculture', desc: 'Farming support, crop insurance & rural development.', link: 'Agriculture', count: '24' },
    { icon: '🏛️', label: 'Avas', sub: 'Housing', desc: 'Government housing assistance & construction aid.', link: 'Housing', count: '12' },
    { icon: '🩺', label: 'Swasthya', sub: 'Healthcare', desc: 'Free insurance & primary health for all families.', link: 'Health', count: '18' },
    { icon: '📚', label: 'Shiksha', sub: 'Education', desc: 'Scholarships, free education & skill upliftment.', link: 'Education', count: '31' },
    { icon: '🪷', label: 'Mahila', sub: 'Women', desc: 'Empowerment programs for women & mothers.', link: 'Women', count: '22' },
    { icon: '⚙️', label: 'Rozgar', sub: 'Employment', desc: 'Job creation, self-employment & skill dev aid.', link: 'Employment', count: '15' },
]

export default function HomePage() {
    const navigate = useNavigate()
    const { t } = useLang()
    const { scrollYProgress } = useScroll()
    const [trending, setTrending] = useState([])
    const [news, setNews] = useState([])
    useEffect(() => {
        gateway.trending().then(d => setTrending(d.trending || [])).catch(() => {})
        gateway.recentSchemes().then(d => setNews(d.recent || [])).catch(() => {})
    }, [])

    return (
        <div className="page-wrapper home-wrapper">
            <div className="home-bg-aurora">
                <div className="aurora-orb orb-1" />
                <div className="aurora-orb orb-2" />
                <div className="aurora-orb orb-3" />
                <div className="aurora-orb orb-4" />
            </div>

            {/* Full-page 3D flythrough background — scroll drives the camera
                through the mandala tunnel behind ALL content */}
            {!prefersReducedMotion && (
                <div className="home-3d-bg">
                    <Suspense fallback={null}>
                        <MandalaTower3D height="100%" progress={() => scrollYProgress.get()} />
                    </Suspense>
                </div>
            )}

            <Navbar />
            <main className="home-main">

                {/* ── Hero ── */}
                <section className="home-hero-cultural">
                    <div className="hero-bg-rays" />
                    {prefersReducedMotion && <Reveal y={14}><MandalaLogo /></Reveal>}
                    <Reveal delay={0.08}>
                        <h1 className="hero-title-cultural font-display">
                            {t('home.greet')} <span className="hero-title-saffron">Bharat</span>
                        </h1>
                    </Reveal>
                    <Reveal delay={0.16}><p className="hero-dharma-line">{t('home.tagline')}</p></Reveal>
                    <Reveal delay={0.24}>
                        <div className="hero-btns">
                            <button className="btn-cultural-primary btn-aarti" onClick={() => navigate('/chat')}>
                                {t('home.findScheme')}
                            </button>
                            <button className="btn-cultural-outline" onClick={() => navigate('/schemes')}>
                                {t('home.exploreAll')}
                            </button>
                        </div>
                    </Reveal>
                </section>

                <div className="home-lower-section">
                    {/* ── Trending (cultural template) ── */}
                    {trending.length > 0 && (
                        <Reveal><section className="sathi-cultural-card" style={{ marginBottom: 22 }}>
                            <div className="sathi-tag"><TrendingUp size={10} /> Trending This Week</div>
                            <div style={{ display: 'flex', gap: 10, overflowX: 'auto', padding: '6px 2px 2px', scrollbarWidth: 'none' }}>
                                {trending.map((tr, i) => (
                                    <button key={tr.scheme_code} className="btn-cultural-ghost"
                                        style={{ flexShrink: 0, whiteSpace: 'nowrap' }}
                                        onClick={() => navigate('/chat', { state: { prefill: `Tell me about ${tr.scheme_name}` } })}>
                                        <span className="text-saffron" style={{ fontWeight: 800, marginRight: 6 }}>#{i + 1}</span>
                                        {tr.scheme_name}
                                    </button>
                                ))}
                            </div>
                        </section></Reveal>
                    )}

                    {/* ── Newly added schemes (cultural template) ── */}
                    {news.length > 0 && (
                        <Reveal><section className="sathi-cultural-card" style={{ marginBottom: 22 }}>
                            <div className="sathi-tag"><Newspaper size={10} /> Newly Added Schemes</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 6 }}>
                                {news.slice(0, 4).map((n) => (
                                    <button key={n.scheme_code} className="btn-cultural-ghost"
                                        style={{ width: '100%', justifyContent: 'space-between', display: 'flex', alignItems: 'center', textAlign: 'left' }}
                                        onClick={() => navigate('/chat', { state: { prefill: `Tell me about ${n.scheme_name}` } })}>
                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.scheme_name}</span>
                                        <span className="badge badge-saffron" style={{ flexShrink: 0, marginLeft: 10 }}>{n.state}</span>
                                    </button>
                                ))}
                            </div>
                        </section></Reveal>
                    )}

                    {/* ── Meet Sathi AI ── */}
                    <Reveal><section className="sathi-cultural-card">
                        <div className="sathi-tag"><Sparkles size={10} /> {t('home.personalGuide')}</div>
                        <div className="sathi-card-inner">
                            <div className="sathi-avatar-cultural">
                                <svg viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg" width="40" height="40">
                                    <circle cx="30" cy="22" r="10" fill="rgba(232,141,10,0.9)" />
                                    <circle cx="30" cy="22" r="6" fill="#0d0e1c" />
                                    <circle cx="27" cy="20" r="2" fill="#e88d0a" />
                                    <circle cx="33" cy="20" r="2" fill="#e88d0a" />
                                    <rect x="18" y="35" width="24" height="16" rx="4" fill="rgba(232,141,10,0.8)" />
                                    <rect x="22" y="40" width="4" height="6" rx="1" fill="#0d0e1c" />
                                    <rect x="34" y="40" width="4" height="6" rx="1" fill="#0d0e1c" />
                                    <line x1="30" y1="32" x2="30" y2="35" stroke="rgba(232,141,10,0.8)" strokeWidth="2" />
                                </svg>
                            </div>
                            <div className="sathi-card-body">
                                <h2 className="sathi-card-title font-display">{t('home.meetSathi')}</h2>
                                <p className="sathi-card-desc">{t('home.sathiDesc')}</p>
                            </div>
                            <div className="sathi-card-btns">
                                <button className="btn-cultural-primary sathi-btn" onClick={() => navigate('/chat')}>
                                    <MessageCircle size={13} /> {t('home.chatNow')}
                                </button>
                                <button className="btn-cultural-ghost" onClick={() => navigate('/chat')}>
                                    <Mic size={13} /> {t('home.voice')}
                                </button>
                            </div>
                        </div>
                    </section></Reveal>

                    {/* ── Categories ── */}
                    <section className="home-cat-section">
                        <Reveal><div className="home-cat-heading">
                            <p className="cat-heading-eyebrow">{t('home.catEyebrow')}</p>
                            <h2 className="cat-heading-main font-display">Yojna <span className="cat-heading-saffron">{t('home.categories')}</span></h2>
                            <div className="cat-heading-line" />
                        </div></Reveal>
                        <Stagger className="home-cat-grid-cultural">
                            {CATEGORIES.map((cat) => (
                                <StaggerItem key={cat.label} className="cat-card-cultural" onClick={() => navigate(`/schemes?category=${cat.link}`)}>
                                    <div className="cat-card-top">
                                        <div className="cat-icon-wrap">{cat.icon}</div>
                                        <span className="cat-card-count">{cat.count}</span>
                                    </div>
                                    <div className="cat-card-label">{cat.label}</div>
                                    <div className="cat-card-sub">{cat.sub}</div>
                                    <p className="cat-card-desc">{cat.desc}</p>
                                    <div className="cat-card-link">{t('home.view')} {cat.sub} <ArrowRight size={11} /></div>
                                </StaggerItem>
                            ))}
                        </Stagger>
                    </section>
                </div>

                <div style={{ height: 80 }} />
            </main>
            <BottomNav />
        </div>
    )
}
