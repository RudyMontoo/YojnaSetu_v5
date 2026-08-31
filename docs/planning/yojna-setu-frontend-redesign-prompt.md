# Frontend Redesign Prompt — Yojna Setu

## Context
This is Yojna Setu, an AI platform helping Indian citizens discover and apply for
government welfare schemes, built on a 12-agent architecture (including the merged
Jeevan-Setu pension delivery agents). Before doing anything, read the existing
CLAUDE.md and any DESIGN.md / design-system files in the project root so you understand
current tokens, locked directories, and conventions. Do not touch backend logic, agent
orchestration code, or API contracts — this is a frontend/UI/UX task only.

## Goal
Redesign the frontend visual language while preserving the existing color palette,
contrast ratios, and layout templates. Reskin it around Indian mythology —
Mahabharata and Ramayana motifs — so the product feels dignified, "godly," and
rooted in Indian civic culture, without becoming kitschy or cluttered. Think temple
architecture, mandala geometry, dharma/duty symbolism, subtle gold/copper accenting —
not literal cartoon gods.

## Hard constraints (do not violate)
- Reuse the current color tokens and contrast ratios as the base palette — do not
  introduce a new palette from scratch. Extend it with gradient variants of the
  existing hues rather than replacing them.
- Keep the existing page templates/layout structure (same information architecture,
  same component boundaries) — this is a re-skin, not a rebuild.
- Maintain accessibility: WCAG AA contrast minimums, reduced-motion fallback for all
  animations.
- No literal religious imagery of deities. Use symbolic/architectural motifs
  (temple arches, lotus geometry, mandala patterns, diya/light motifs, chakra-inspired
  loaders) rather than depicting gods directly — this keeps it respectful and
  professional rather than gimmicky.

## Design system tasks
1. Propose an extended design language document (design-mythos.md) that maps:
   - A refined gradient system built from the existing palette
   - Typography pairing that feels dignified/classical without sacrificing
     readability (e.g. a serif/display font for headers, clean sans for body)
   - Iconography direction (line icons with subtle Indian-motif detailing)
   - Motion principles (see below)
2. Get my sign-off on this design-mythos.md before touching components.

## Agent status visualization (priority feature)
Currently the 10–12 agents just show as plain "Agent X is working" text. Replace this
with a proper multi-agent orchestration visualization:
- Each agent gets a distinct visual identity (icon/color role, not a deity) reflecting
  its function — e.g. the verification agent, the biometric agent, the offline-proof
  agent — so users can tell at a glance who's doing what.
- Show live status (idle / active / done / error) with smooth state-transition
  animations, not just text swaps.
- Design this as a real architectural diagram/flow view users can glance at — not a
  cramped sidebar list — something that could visually represent a "council of
  agents" working in sequence or parallel.
- Use subtle 3D or layered-depth motion (parallax, soft shadows, floating cards) for
  this panel specifically, since it's the flagship visual moment of the product.

## 3D animation (required, not optional)
Use Three.js (via react-three-fiber) for real 3D elements — this is a core part of
the redesign, not a stretch goal:
- A 3D hero/landing moment: a rotating or lightly-animated centerpiece built from the
  mythology motifs (e.g. a layered mandala/chakra geometry, or an architectural arch)
  that responds subtly to scroll or cursor movement.
- The agent status panel should use real depth, not just CSS shadows: agent
  cards/nodes positioned in a 3D space (e.g. orbiting a central hub, or arranged in
  layered depth) that animate as agents activate/complete, with the camera doing a
  gentle parallax on scroll or interaction.
- Keep 3D scenes lightweight — low poly counts, optimized geometry, and always ship a
  static/2D fallback for low-end devices and `prefers-reduced-motion` — this is a
  civic platform used on a wide range of phones, it can't tank load times or exclude
  users on weaker hardware.
- Performance budget: 3D scenes should not push initial load past what's reasonable
  for a 3G/mid-range Android user — lazy-load the 3D canvas after critical content
  renders.

## Motion & polish
- Use Framer Motion for 2D transitions, hover states, page transitions, and
  micro-interactions (button presses, card reveals) — should feel premium and
  intentional, not default-template.
- Loading states should tie into the theme (e.g. a temple-arch progress motif) rather
  than a generic spinner.

## Deliverable format
- First: design-mythos.md + 2-3 static mockup screens (as code, in an isolated
  branch/preview route) for review before touching the rest of the app.
- After approval: apply system-wide, screen by screen, starting with the agent
  status view.
