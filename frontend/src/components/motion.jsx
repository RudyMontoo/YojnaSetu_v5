import { motion, useReducedMotion } from "framer-motion";

// Restrained motion layer for the existing glassmorphism design.
// Every primitive collapses to static under prefers-reduced-motion.
// Springs over linear easing; transform/opacity only (GPU-cheap).

const spring = { type: "spring", stiffness: 120, damping: 20 };

/** Fade-up on first viewport entry — hero blocks, cards, sections. */
export function Reveal({ children, delay = 0, y = 22, className, style }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      style={style}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ ...spring, delay }}
    >
      {children}
    </motion.div>
  );
}

/** Parent for staggered child reveals (cards in a grid). */
export function Stagger({ children, className, gap = 0.07 }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : "hidden"}
      whileInView="show"
      viewport={{ once: true, amount: 0.15 }}
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap } } }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className, style, onClick }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      style={style}
      onClick={onClick}
      variants={{
        hidden: reduce ? {} : { opacity: 0, y: 18, scale: 0.98 },
        show: { opacity: 1, y: 0, scale: 1, transition: spring },
      }}
      whileHover={reduce ? undefined : { y: -4, transition: { duration: 0.18 } }}
    >
      {children}
    </motion.div>
  );
}

/** Chat bubble pop-in. */
export function BubbleIn({ children, className, fromUser = false }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 10, x: fromUser ? 12 : -12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, x: 0, scale: 1 }}
      transition={{ ...spring, stiffness: 200 }}
    >
      {children}
    </motion.div>
  );
}

/** Page-level fade for route content. */
export function PageFade({ children }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
