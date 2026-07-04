# design-mythos.md — Yojna Setu "Dharma" Visual Language

> Extension of the existing design system (`src/index.css` tokens). Nothing here replaces
> the current palette, contrast ratios, or page templates. This maps how the existing
> language gets a dignified, mythology-rooted reskin. **Awaiting sign-off before any
> system-wide application** — mockups live at `/preview/mythos`.

## 1. Reading the brief

Temple architecture, not temples. Dharma symbolism, not deities. The product should feel
like standing in a well-lit stone corridor of a public institution built centuries ago and
maintained yesterday: permanence, duty, quiet gold. Kitsch is the failure mode; restraint
is the design.

## 2. Gradient system (built strictly from existing tokens)

Existing hues: `--navy #08090f`, `--navy-light #0d0e1c`, `--saffron #FF6B35`,
`--saffron-dark #e05520`, `--gold #F59E0B`, `--green #22C55E`.

| Token | Definition | Use |
|---|---|---|
| `--grad-dusk` | `linear-gradient(170deg, #0d0e1c 0%, #08090f 60%)` | Page backgrounds (already implicit; formalized) |
| `--grad-aarti` | `linear-gradient(135deg, #FF6B35 0%, #F59E0B 100%)` | Primary CTAs, active agent states — the "flame" gradient |
| `--grad-copper` | `linear-gradient(135deg, rgba(245,158,11,.28), rgba(255,107,53,.08))` | Card edge-light, dividers, arch strokes |
| `--grad-temple-glow` | `radial-gradient(ellipse at 50% 0%, rgba(245,158,11,.10), transparent 65%)` | Section-top halos (replaces current generic saffron orb on key screens) |
| `--grad-tulsi` | `linear-gradient(135deg, #22C55E, rgba(34,197,94,.35))` | Success / "done" agent states only |

Rule: gradients are *variants of existing hues only* — no new base colors. Contrast of
text over any gradient stays WCAG AA (existing `--text-primary` on navy passes; saffron
gradients never carry body text, only large display or icon fills).

## 3. Typography

| Role | Face | Rationale |
|---|---|---|
| Display / page titles / hero | **Cormorant Garamond** (600/700) | Classical, inscription-like without being ornamental. Used ≥ 28px only — never body sizes (readability guard). |
| Body / UI | **Inter** (existing token, unchanged) | Current body face stays; zero regression risk |
| Devanagari / Indic | **Noto Sans Devanagari** (existing) | Already loaded; pairs cleanly under Cormorant headers |
| Numerals in stats | Inter tabular-nums | Alignment in agent panel + status timelines |

Display serif is confined to headers and the hero. All existing body text, buttons,
forms keep Inter at current sizes — the reskin never touches reading text.

## 4. Iconography

- Base: existing lucide line icons (already everywhere) — keep for all UI chrome.
- Motif layer (decorative only, never functional): a small SVG set drawn in-house —
  **temple arch** (section frames, loading motif), **lotus geometry** (8-petal, empty
  states), **diya flame** (nudge/notification accents), **chakra ring** (loaders — the
  24-spoke mandala already in the Home hero becomes the system-wide loading identity).
- Rule: motif SVGs are single-color strokes in `--gold`/`--saffron` at ≤ 40% opacity,
  1–1.5px stroke. No filled illustrations, no figures, no deities.

## 5. Motion principles

1. **Everything springs, nothing slides linearly** — `spring(stiffness 120, damping 20)`
   (already established in `components/motion.jsx`).
2. **Light moves like aarti** — glow/gradient transitions ease slowly (400–600ms);
   structural moves are quick (≤ 250ms). Light is ceremonial, structure is utilitarian.
3. **One flagship 3D moment per screen, maximum** — the hero mandala (landing) and the
   Agent Council panel (chat/status). Everything else is 2D framer-motion.
4. **`prefers-reduced-motion` collapses all of it** — 3D canvases render a static SVG
   fallback, springs become instant, loaders become static arcs. Non-negotiable.
5. **3D budget**: lazy-loaded canvas (never blocks first paint), DPR capped at 1.5,
   < 3k triangles per scene, no post-processing. Mid-range Android is the target device.

## 6. Agent Council — the flagship visualization

Replaces "Agent X is working" text. A **council semicircle**: agent nodes arranged in an
arc (like pillars in a durbar hall) around a central orchestrator hub. Layered depth:
nodes float on 3 z-planes with soft parallax; the active agent's pillar lifts, lights
with `--grad-aarti`, and a pulse travels along the connecting line from the hub.

Visual identities (icon + color-role, function-derived, no deities):

| Agent | Identity | Icon (lucide) | State color family |
|---|---|---|---|
| Orchestrator | The Hub — chakra ring | `landmark` | gold |
| 1 Eligibility | The Scales | `scale` | saffron |
| 2 Discovery | The Compass | `compass` | gold |
| 3 Guidance | The Path | `map` | saffron |
| 4 Document | The Seal | `stamp` | copper/gold |
| 5 Grievance | The Bell (nyaya-ghanta) | `bell-ring` | saffron |
| 6 Nudge | The Diya | `flame` | gold |
| 7 Financial | The Treasury | `coins` | green |
| 8 Comparison | The Balance | `git-compare` | gold |
| 9 CSC | The Pillar | `columns-3` | copper |
| 10 Analytics | The Yantra | `radar` | blue (existing `--blue`) |
| 11 Biometric | The Eye | `scan-face` | saffron |
| 12 Offline Proof | The Mudra | `qr-code` | green |

States: `idle` (dim, 40% opacity, slow breathe) → `active` (lift + flame gradient +
pulse line) → `done` (settles, `--grad-tulsi` tick) → `error` (existing `--red`, gentle
shake once, never loops). All transitions are springs; text status remains alongside for
screen readers (`aria-live="polite"`).

## 7. Loading states

- **Chakra loader**: 24-spoke ring, spokes illuminate clockwise (SVG, CSS animation).
- **Arch progress**: temple-arch outline draws stroke-dasharray left-pillar → apex →
  right-pillar as progress; falls back to a plain bar under reduced motion.
- Generic spinners are retired wherever these land.

## 8. What does NOT change

Palette bases, contrast pairs, page templates, information architecture, component
boundaries, nav structure, Inter as body face, lucide as UI icon set, all backend
contracts. This is a skin, applied screen-by-screen after sign-off, starting with the
agent status view.
