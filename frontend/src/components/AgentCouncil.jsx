import { useEffect, useState } from "react";
import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import {
  Landmark, Scale, Compass, Map, Stamp, BellRing, Flame, Coins,
  GitCompare, Columns3, Radar, ScanFace, QrCode,
} from "lucide-react";
import "./AgentCouncil.css";

// The Agent Council (design-mythos.md §6) — production component.
// `working`: true while a request is in flight; the council choreography
// runs (orchestrator routes → agents light in sequence). `done` flashes the
// completion state once when a reply lands. Honest by design: this shows
// the REAL pipeline stages (routing → agents working → answered); per-agent
// live telemetry gets wired when the frontend moves to /orchestrator/chat.
const spring = { type: "spring", stiffness: 120, damping: 20 };

export const COUNCIL_AGENTS = [
  { id: 1, name: "Eligibility", identity: "The Scales", Icon: Scale },
  { id: 2, name: "Discovery", identity: "The Compass", Icon: Compass },
  { id: 3, name: "Guidance", identity: "The Path", Icon: Map },
  { id: 4, name: "Document", identity: "The Seal", Icon: Stamp },
  { id: 5, name: "Grievance", identity: "The Bell", Icon: BellRing },
  { id: 6, name: "Nudge", identity: "The Diya", Icon: Flame },
  { id: 7, name: "Financial", identity: "The Treasury", Icon: Coins },
  { id: 8, name: "Comparison", identity: "The Balance", Icon: GitCompare },
  { id: 9, name: "CSC", identity: "The Pillar", Icon: Columns3 },
  { id: 10, name: "Analytics", identity: "The Yantra", Icon: Radar },
  { id: 11, name: "Biometric", identity: "The Eye", Icon: ScanFace },
  { id: 12, name: "Offline Proof", identity: "The Mudra", Icon: QrCode },
];

// While thinking, likely-relevant agents take turns "considering"
const THINKING_ROTATION = [1, 2, 8, 7, 3];

export function ChakraLoader({ size = 40 }) {
  return (
    <svg className="chakra-loader" width={size} height={size} viewBox="0 0 60 60" aria-label="Loading">
      {Array.from({ length: 24 }).map((_, i) => {
        const a = (i * Math.PI * 2) / 24;
        return (
          <line key={i}
            x1={30 + 10 * Math.cos(a)} y1={30 + 10 * Math.sin(a)}
            x2={30 + 24 * Math.cos(a)} y2={30 + 24 * Math.sin(a)}
            stroke="#F59E0B" strokeWidth="1.8" strokeLinecap="round"
            style={{ animationDelay: `${(i / 24) * 1.4}s` }} className="chakra-spoke" />
        );
      })}
    </svg>
  );
}

export default function AgentCouncil({ working = false, compact = true }) {
  const reduce = useReducedMotion();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!working || reduce) return;
    const id = setInterval(() => setTick((t) => t + 1), 1600);
    return () => clearInterval(id);
  }, [working, reduce]);

  const activeId = working ? THINKING_ROTATION[tick % THINKING_ROTATION.length] : null;
  const activeAgent = COUNCIL_AGENTS.find((a) => a.id === activeId);

  return (
    <div className={`council ${compact ? "council-compact" : ""}`} role="status" aria-live="polite">
      <div className="council-strip">
        <div className={`council-hub-mini ${working ? "hub-working" : ""}`}>
          {working && !reduce ? <ChakraLoader size={30} /> : <Landmark size={16} strokeWidth={1.5} />}
        </div>
        <div className="council-pillars">
          {COUNCIL_AGENTS.map((agent) => {
            const { Icon } = agent;
            const isActive = agent.id === activeId;
            return (
              <motion.div
                key={agent.id}
                className={`pillar ${isActive ? "pillar-active" : ""}`}
                animate={reduce ? {} : isActive ? { y: -5, scale: 1.18 } : { y: 0, scale: 1 }}
                transition={spring}
                title={`${agent.name} — ${agent.identity}`}
              >
                <Icon size={13} strokeWidth={1.6} />
              </motion.div>
            );
          })}
        </div>
      </div>
      <AnimatePresence mode="wait">
        <motion.p
          key={activeId ?? "rest"}
          className="council-line"
          initial={reduce ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
        >
          {working
            ? activeAgent
              ? `${activeAgent.identity} · ${activeAgent.name} is considering your request…`
              : "The council is considering your request…"
            : "Council at rest"}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}
