import { lazy, Suspense, useEffect, useState } from "react";
import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import {
  Landmark, Scale, Compass, Map, Stamp, BellRing, Flame, Coins,
  GitCompare, Columns3, Radar, ScanFace, QrCode, ArrowLeft,
} from "lucide-react";
import { Link } from "react-router-dom";
import "./MythosPreview.css";

// ── Mockup screens for design-mythos.md sign-off. Isolated route: nothing
//    here touches existing pages. Screen 1: 3D hero. Screen 2: Agent Council.
//    Screen 3: themed loaders + micro-interactions.

const Mandala3D = lazy(() => import("../../components/Mandala3D"));

const spring = { type: "spring", stiffness: 120, damping: 20 };

/* Static SVG fallback: reduced-motion users and while the 3D chunk loads */
function MandalaStatic({ size = 300 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-hidden="true">
      <circle cx="60" cy="60" r="55" stroke="rgba(245,158,11,0.4)" strokeWidth="0.8" />
      <circle cx="60" cy="60" r="48" stroke="rgba(255,107,53,0.3)" strokeWidth="0.5" />
      <circle cx="60" cy="60" r="18" stroke="rgba(245,158,11,0.7)" strokeWidth="1.2" />
      {Array.from({ length: 24 }).map((_, i) => {
        const a = (i * Math.PI * 2) / 24;
        return (
          <line key={i}
            x1={60 + 18 * Math.cos(a)} y1={60 + 18 * Math.sin(a)}
            x2={60 + 48 * Math.cos(a)} y2={60 + 48 * Math.sin(a)}
            stroke={i % 2 ? "rgba(255,107,53,0.45)" : "rgba(245,158,11,0.8)"}
            strokeWidth={i % 2 ? 0.5 : 1} />
        );
      })}
      <circle cx="60" cy="60" r="5" fill="#F59E0B" />
    </svg>
  );
}

/* ── Screen 2 data: the Agent Council (design-mythos.md §6) ── */
const COUNCIL = [
  { id: 1, name: "Eligibility", identity: "The Scales", Icon: Scale, hue: "saffron" },
  { id: 2, name: "Discovery", identity: "The Compass", Icon: Compass, hue: "gold" },
  { id: 3, name: "Guidance", identity: "The Path", Icon: Map, hue: "saffron" },
  { id: 4, name: "Document", identity: "The Seal", Icon: Stamp, hue: "gold" },
  { id: 5, name: "Grievance", identity: "The Bell", Icon: BellRing, hue: "saffron" },
  { id: 6, name: "Nudge", identity: "The Diya", Icon: Flame, hue: "gold" },
  { id: 7, name: "Financial", identity: "The Treasury", Icon: Coins, hue: "green" },
  { id: 8, name: "Comparison", identity: "The Balance", Icon: GitCompare, hue: "gold" },
  { id: 9, name: "CSC", identity: "The Pillar", Icon: Columns3, hue: "gold" },
  { id: 10, name: "Analytics", identity: "The Yantra", Icon: Radar, hue: "blue" },
  { id: 11, name: "Biometric", identity: "The Eye", Icon: ScanFace, hue: "saffron" },
  { id: 12, name: "Offline Proof", identity: "The Mudra", Icon: QrCode, hue: "green" },
];

/* Demo status choreography: a request flows through the council */
const DEMO_SEQUENCE = [
  { active: [1], done: [] },
  { active: [2], done: [1] },
  { active: [7, 8], done: [1, 2] },       // parallel work
  { active: [4], done: [1, 2, 7, 8] },
  { active: [], done: [1, 2, 7, 8, 4] },
];

function AgentNode({ agent, status, index, total, reduce }) {
  // council arc: pillars in a durbar semicircle, three depth planes
  const t = index / (total - 1);
  const angle = Math.PI * (1 - t);               // 180° → 0°
  const rx = 46, ry = 30;                        // % of container
  const x = 50 + rx * Math.cos(angle);
  const y = 78 - ry * Math.sin(angle);
  const depth = index % 3;                       // 3 z-planes for layered parallax
  const { Icon } = agent;

  return (
    <motion.div
      className={`council-node hue-${agent.hue} status-${status} depth-${depth}`}
      style={{ left: `${x}%`, top: `${y}%` }}
      animate={
        reduce ? {} :
        status === "active" ? { y: -10, scale: 1.12 } :
        status === "done" ? { y: 0, scale: 1 } :
        { y: 0, scale: 1 }
      }
      transition={spring}
      aria-label={`Agent ${agent.name}: ${status}`}
    >
      <div className="council-node-orb">
        <Icon size={depth === 1 ? 20 : 17} strokeWidth={1.5} />
        {status === "active" && !reduce && <span className="node-pulse" />}
        {status === "done" && <motion.span className="node-tick" initial={reduce ? false : { scale: 0 }} animate={{ scale: 1 }} transition={spring}>✓</motion.span>}
      </div>
      <span className="council-node-name">{agent.name}</span>
      <span className="council-node-identity">{agent.identity}</span>
    </motion.div>
  );
}

function AgentCouncil() {
  const reduce = useReducedMotion();
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setStep((s) => (s + 1) % (DEMO_SEQUENCE.length + 1)), 2200);
    return () => clearInterval(id);
  }, [reduce]);

  const seq = DEMO_SEQUENCE[Math.min(step, DEMO_SEQUENCE.length - 1)];
  const statusOf = (id) =>
    seq.active.includes(id) ? "active" : seq.done.includes(id) ? "done" : "idle";
  const activeNames = COUNCIL.filter((a) => seq.active.includes(a.id)).map((a) => a.name);

  return (
    <div className="council-stage" role="img" aria-label="Agent council status diagram">
      <div className="council-arch" aria-hidden="true" />
      {/* central orchestrator hub */}
      <div className="council-hub">
        <Landmark size={22} strokeWidth={1.5} />
        <span>Orchestrator</span>
      </div>
      {COUNCIL.map((agent, i) => (
        <AgentNode key={agent.id} agent={agent} status={statusOf(agent.id)}
                   index={i} total={COUNCIL.length} reduce={reduce} />
      ))}
      <div className="council-caption" aria-live="polite">
        <AnimatePresence mode="wait">
          <motion.p key={step} initial={reduce ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            {activeNames.length
              ? `${activeNames.join(" and ")} ${activeNames.length > 1 ? "are" : "is"} working on your request`
              : seq.done.length ? "Council has answered. All agents at rest." : "Council at rest — ask Sathi anything."}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ── Screen 3: themed loaders ── */
function ChakraLoader({ size = 56 }) {
  return (
    <svg className="chakra-loader" width={size} height={size} viewBox="0 0 60 60" aria-label="Loading">
      {Array.from({ length: 24 }).map((_, i) => {
        const a = (i * Math.PI * 2) / 24;
        return (
          <line key={i}
            x1={30 + 10 * Math.cos(a)} y1={30 + 10 * Math.sin(a)}
            x2={30 + 24 * Math.cos(a)} y2={30 + 24 * Math.sin(a)}
            stroke="#F59E0B" strokeWidth="1.6" strokeLinecap="round"
            style={{ animationDelay: `${(i / 24) * 1.4}s` }} className="chakra-spoke" />
        );
      })}
    </svg>
  );
}

function ArchProgress({ progress = 0.66 }) {
  const d = "M 10 90 L 10 45 Q 10 12 50 12 Q 90 12 90 45 L 90 90";
  return (
    <svg width="120" height="110" viewBox="0 0 100 100" aria-label={`Progress ${Math.round(progress * 100)}%`}>
      <path d={d} fill="none" stroke="rgba(245,158,11,0.15)" strokeWidth="3" strokeLinecap="round" />
      <path d={d} fill="none" stroke="url(#aarti)" strokeWidth="3" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - progress} />
      <defs>
        <linearGradient id="aarti" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#FF6B35" /><stop offset="1" stopColor="#F59E0B" />
        </linearGradient>
      </defs>
      <text x="50" y="72" textAnchor="middle" className="arch-pct">{Math.round(progress * 100)}%</text>
    </svg>
  );
}

export default function MythosPreview() {
  const reduce = useReducedMotion();
  const [archDemo, setArchDemo] = useState(0.2);
  useEffect(() => {
    if (reduce) { setArchDemo(0.66); return; }
    const id = setInterval(() => setArchDemo((p) => (p >= 1 ? 0.1 : p + 0.02)), 120);
    return () => clearInterval(id);
  }, [reduce]);

  return (
    <div className="mythos-wrap">
      <Link to="/home" className="mythos-back"><ArrowLeft size={14} /> Back to app</Link>

      {/* ── Screen 1: Hero ── */}
      <section className="mythos-hero">
        <div className="mythos-3d">
          {reduce ? <MandalaStatic /> : (
            <Suspense fallback={<MandalaStatic />}>
              <Mandala3D height={340} />
            </Suspense>
          )}
        </div>
        <motion.h1 initial={reduce ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
          Yojna <span>Setu</span>
        </motion.h1>
        <motion.p className="mythos-hero-sub" initial={reduce ? false : { opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: 0.1 }}>
          Your rights, delivered with dignity.
        </motion.p>
        <motion.div className="mythos-hero-btns" initial={reduce ? false : { opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: 0.18 }}>
          <button className="mythos-btn-primary">Find My Scheme</button>
          <button className="mythos-btn-ghost">Explore All</button>
        </motion.div>
        <p className="mythos-note">Screen 1 — 3D chakra hero (cursor parallax; static SVG under reduced motion)</p>
      </section>

      {/* ── Screen 2: Agent Council ── */}
      <section className="mythos-section">
        <h2>The Agent Council</h2>
        <p className="mythos-section-sub">Live multi-agent status as a durbar-hall arc. Watch the demo request flow through.</p>
        <AgentCouncil />
        <p className="mythos-note">Screen 2 — replaces "Agent X is working" text. States: idle · active (flame lift) · done (green tick) · error (single shake). Screen-reader text mirrors every state.</p>
      </section>

      {/* ── Screen 3: loaders + micro-interactions ── */}
      <section className="mythos-section">
        <h2>Ceremony of Waiting</h2>
        <p className="mythos-section-sub">Loading identity: no generic spinners.</p>
        <div className="mythos-loader-row">
          <div className="mythos-loader-card"><ChakraLoader /><span>Chakra loader — thinking</span></div>
          <div className="mythos-loader-card"><ArchProgress progress={archDemo} /><span>Arch progress — uploads &amp; steps</span></div>
          <div className="mythos-loader-card">
            <motion.button className="mythos-btn-primary" whileTap={reduce ? undefined : { scale: 0.96 }}
                           whileHover={reduce ? undefined : { y: -2 }}>
              Press me
            </motion.button>
            <span>Button physics — press &amp; lift</span>
          </div>
        </div>
        <p className="mythos-note">Screen 3 — chakra/arch loaders, spring micro-interactions. All collapse under reduced motion.</p>
      </section>

      <footer className="mythos-footer">
        design-mythos.md · mockups for sign-off · existing palette &amp; templates untouched
      </footer>
    </div>
  );
}
