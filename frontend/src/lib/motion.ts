/**
 * ClinIQ 2.0 — Animation System
 * src/lib/motion.ts
 *
 * Single source of truth for every Framer Motion configuration.
 * Import named variants and transitions; never hardcode values in components.
 *
 * Quick-reference
 * ───────────────
 * Tokens:    DURATION · EASE · SPRING · T (transition presets)
 * Entries:   fadeUp · fadeDown · fadeIn · slideRight · slideLeft
 *            scaleIn · scaleInSpring
 * Stagger:   staggerContainer + staggerItem · staggerFast + staggerItem
 * Pages:     pageTransition · pageExit
 * Interact:  cardHover · buttonTap · pillHover   (whileHover / whileTap)
 * Feature:   pipelineStage · agentMessage · counterConfig
 * Helpers:   withDelay(variant, ms) · withDuration(variant, key)
 * CSS:       CSS_ANIM.glowPulse · CSS_ANIM.shimmer   (class names, not FM)
 *
 * Usage pattern:
 *   <motion.div variants={fadeUp} initial="hidden" animate="visible" />
 *   <motion.div variants={withDelay(scaleIn, 200)} initial="hidden" animate="visible" />
 *   <motion.button whileHover={cardHover} whileTap={buttonTap} />
 */

import type { Variants, Transition } from 'framer-motion';

// =============================================================================
// TYPES
// =============================================================================

/**
 * Full Framer Motion variant map, aliased for consistent naming.
 * Canonical shape for every variant in this file: { hidden, visible, exit? }.
 * Extra keys (e.g. "hover", "tap") are allowed since Variants is open.
 */
export type MotionVariant = Variants;

/**
 * Framer Motion Transition, aliased for import convenience.
 * Pass to the `transition` prop or embed inside a variant's `transition` key.
 */
export type TransitionConfig = Transition;

/** Union of valid DURATION token names */
export type DurationKey = keyof typeof DURATION;

// =============================================================================
// DURATION TOKENS
// Stored in seconds — Framer Motion's native unit.
// The ms value is in the comment so it matches design-token docs exactly.
// =============================================================================

export const DURATION = {
  instant:   0.06,  //   60 ms — hover bg, color shifts
  fast:      0.12,  //  120 ms — micro-interactions, icon transitions
  normal:    0.22,  //  220 ms — card reveals, state changes
  slow:      0.38,  //  380 ms — page transitions, panel slides
  feature:   0.6,   //  600 ms — hero counter, ring animation
  dramatic:  0.9,   //  900 ms — DeepDive pipeline stage, full-screen
} as const;

// =============================================================================
// EASING
// Cubic bezier arrays: [x1, y1, x2, y2].
// Named for motion character, not mathematical identity.
// =============================================================================

/**
 * Fast out, long gentle settle — ideal for elements entering the viewport.
 * Reaches ~90% of target at ~30% of the timeline; decelerates to rest naturally.
 */
export const EASE_OUT   = [0.16, 1, 0.3, 1]   as [number, number, number, number];

/**
 * Symmetrical ease — start slow, peak in middle, slow to rest.
 * Use for transitions where both origin and destination matter equally.
 */
export const EASE_INOUT = [0.87, 0, 0.13, 1]  as [number, number, number, number];

/** Convenience map — matches spec naming; backed by the named constants above */
export const EASE = {
  out:   EASE_OUT,
  inOut: EASE_INOUT,
} as const;

// =============================================================================
// SPRING CONFIGS
// Full Transition objects — assign directly to the `transition` prop
// or nest as `transition` inside a variant frame.
//
// stiffness = how fast the spring snaps (higher = snappier)
// damping   = how quickly oscillation dies (lower = more bounce)
// =============================================================================

/** Crisp, responsive — default for most interactive elements */
export const SPRING_DEFAULT: Transition = {
  type:      'spring',
  stiffness: 400,
  damping:   35,
};

/** Playful bounce — ring reveals, hero numbers, celebratory feedback */
export const SPRING_BOUNCE: Transition = {
  type:      'spring',
  stiffness: 300,
  damping:   20,
};

/** Slow settle — drawer slides, large panel reveals */
export const SPRING_GENTLE: Transition = {
  type:      'spring',
  stiffness: 200,
  damping:   30,
};

/**
 * Named spring map.
 * Spec names: spring · springBounce · springGentle
 */
export const SPRING = {
  spring:       SPRING_DEFAULT,
  springBounce: SPRING_BOUNCE,
  springGentle: SPRING_GENTLE,
} as const;

// =============================================================================
// COMBINED EASING MAP  (spec-exact naming: easeOut · easeInOut · spring · …)
// =============================================================================

export const EASING = {
  easeOut:      EASE_OUT,
  easeInOut:    EASE_INOUT,
  spring:       SPRING_DEFAULT,
  springBounce: SPRING_BOUNCE,
  springGentle: SPRING_GENTLE,
} as const;

// =============================================================================
// TRANSITION PRESETS
// Pre-composed Transition objects keyed by duration name.
// T.normal is the workhorse; T.spring/springBounce/springGentle for physics.
// =============================================================================

// Private builder — keeps the T table readable with no repetition
function tw(duration: number, ease: [number, number, number, number]): Transition {
  return { type: 'tween', duration, ease };
}

export const T: Record<string, Transition> = {
  //  ── Tween (cubic-bezier) ─────────────────────────────────────────────────
  instant:     tw(DURATION.instant,  EASE_OUT),
  fast:        tw(DURATION.fast,     EASE_OUT),
  normal:      tw(DURATION.normal,   EASE_OUT),
  slow:        tw(DURATION.slow,     EASE_OUT),
  feature:     tw(DURATION.feature,  EASE_OUT),
  dramatic:    tw(DURATION.dramatic, EASE_OUT),

  normalInOut: tw(DURATION.normal,   EASE_INOUT),
  slowInOut:   tw(DURATION.slow,     EASE_INOUT),

  //  ── Spring ───────────────────────────────────────────────────────────────
  spring:       SPRING_DEFAULT,
  springBounce: SPRING_BOUNCE,
  springGentle: SPRING_GENTLE,
};

// =============================================================================
// ENTRY VARIANTS
// Every variant follows the hidden → visible → exit shape.
// hidden  = initial state (before mount / before enter)
// visible = resting state (mounted and in viewport)
// exit    = leaving state (AnimatePresence unmount)
// =============================================================================

/**
 * Slide up from 16 px below + fade in.
 * Default entry for cards, sections, and content blocks.
 */
export const fadeUp: MotionVariant = {
  hidden:  { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0,  transition: T.normal },
  exit:    { opacity: 0, y: -8, transition: T.fast   },
};

/**
 * Slide down from 16 px above + fade in.
 * Use for dropdowns, tooltips, and menus that originate above the trigger.
 */
export const fadeDown: MotionVariant = {
  hidden:  { opacity: 0, y: -16 },
  visible: { opacity: 1, y: 0,    transition: T.normal },
  exit:    { opacity: 0, y: 8,    transition: T.fast   },
};

/**
 * Opacity only — no positional change.
 * Use for overlays, modals, and content that must not shift the layout.
 */
export const fadeIn: MotionVariant = {
  hidden:  { opacity: 0 },
  visible: { opacity: 1, transition: T.normal },
  exit:    { opacity: 0, transition: T.fast   },
};

/**
 * Slide in from the left (entry from −24 px).
 * Use for side panels, nav drawers, and tabs activating left-to-right.
 */
export const slideRight: MotionVariant = {
  hidden:  { opacity: 0, x: -24 },
  visible: { opacity: 1, x: 0,   transition: T.normal },
  exit:    { opacity: 0, x: -12, transition: T.fast   },
};

/**
 * Slide in from the right (entry from +24 px).
 * Use for notifications, agent messages, and right-hand drawers.
 */
export const slideLeft: MotionVariant = {
  hidden:  { opacity: 0, x: 24 },
  visible: { opacity: 1, x: 0,  transition: T.normal },
  exit:    { opacity: 0, x: 12, transition: T.fast   },
};

/**
 * Scale from 0.94 + fade in — cards and panels popping into layout.
 * Subtle: only a 6% size shift so large containers don't feel rubber-band-y.
 */
export const scaleIn: MotionVariant = {
  hidden:  { opacity: 0, scale: 0.94 },
  visible: { opacity: 1, scale: 1,    transition: T.normal       },
  exit:    { opacity: 0, scale: 0.96, transition: T.fast         },
};

/**
 * Scale from 0.88 with springBounce — rings, hero elements, emphasis states.
 * The extra scale delta (12%) and physics spring signal importance.
 */
export const scaleInSpring: MotionVariant = {
  hidden:  { opacity: 0, scale: 0.88 },
  visible: { opacity: 1, scale: 1,    transition: T.springBounce },
  exit:    { opacity: 0, scale: 0.94                             },
};

// =============================================================================
// STAGGER VARIANTS
// Pair a container with staggerChildren and children with any entry variant.
//
// Pattern:
//   <motion.ul variants={staggerContainer} initial="hidden" animate="visible">
//     {items.map(item => (
//       <motion.li key={item.id} variants={staggerItem}>{item.text}</motion.li>
//     ))}
//   </motion.ul>
// =============================================================================

/**
 * Standard stagger container.
 * Children animate in sequence with 40 ms between each, 100 ms initial delay.
 * Pair with staggerItem on each child.
 */
export const staggerContainer: MotionVariant = {
  hidden:  {},
  visible: {
    transition: {
      staggerChildren: 0.04,
      delayChildren:   0.1,
    },
  },
};

/**
 * Stagger item: fadeUp with normal duration.
 * Drop-in child for staggerContainer.
 */
export const staggerItem: MotionVariant = {
  hidden:  { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0,  transition: T.normal },
  exit:    { opacity: 0, y: -8, transition: T.fast   },
};

/**
 * Fast stagger container for dense sequences.
 * Half the inter-child delay — use for agent message feeds and log lines.
 * Pair with staggerItem (or any entry variant) on each child.
 */
export const staggerFast: MotionVariant = {
  hidden:  {},
  visible: {
    transition: {
      staggerChildren: 0.025,
      delayChildren:   0.05,
    },
  },
};

// =============================================================================
// PAGE TRANSITION VARIANTS
// Used with AnimatePresence at the route level.
// AnimatePresence passes the `exit` key to the outgoing route component.
//
//   <AnimatePresence mode="wait">
//     <motion.main key={route} variants={pageTransition}
//       initial="hidden" animate="visible" exit="exit">
//       <Outlet />
//     </motion.main>
//   </AnimatePresence>
// =============================================================================

/**
 * Full-page enter: slow fadeUp.
 * Also carries an exit frame so it works standalone with AnimatePresence.
 */
export const pageTransition: MotionVariant = {
  hidden:  { opacity: 0, y: 16  },
  visible: { opacity: 1, y: 0,   transition: T.slow },
  exit:    { opacity: 0, y: -16, transition: T.fast },
};

/**
 * Separate page exit companion when the enter and exit feel different enough
 * to warrant distinct configurations (e.g. snap exit vs. slow enter).
 */
export const pageExit: MotionVariant = {
  hidden:  { opacity: 0, y: -16 },
  visible: { opacity: 1, y: 0   },
  exit:    { opacity: 0, y: -16, transition: T.fast },
};

// =============================================================================
// INTERACTIVE ELEMENT PRESETS
// Pass directly to whileHover / whileTap — NOT as named variant strings.
//
//   <motion.div whileHover={cardHover} whileTap={buttonTap} />
//
// These are plain objects, not MotionVariant — they describe a target state
// rather than a named variant map.
// =============================================================================

/**
 * Card hover: lift by 2 px, no scale.
 * Scale on cards feels cheap at large sizes; vertical lift conveys hover intent
 * without distorting surrounding content.
 */
export const cardHover = {
  y:          -2,
  transition: T.fast,
} as const;

/** Button tap: compress to 97% for tactile press feedback */
export const buttonTap = {
  scale:      0.97,
  transition: T.instant,
} as const;

/**
 * Pill / chip hover: +2% scale.
 * Appropriate for small, bounded shapes where scale reads as responsiveness,
 * not distortion.
 */
export const pillHover = {
  scale:      1.02,
  transition: T.fast,
} as const;

// =============================================================================
// FEATURE-SPECIFIC VARIANTS
// Purpose-built for individual ClinIQ components; named for their use case.
// =============================================================================

/**
 * DeepDive pipeline stage activation.
 * Dramatic (900 ms) duration signals a substantive computation step, not a
 * UI micro-interaction. easeOut delivers fast initial movement that settles.
 */
export const pipelineStage: MotionVariant = {
  hidden:  { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1,    transition: T.dramatic },
  exit:    { opacity: 0, scale: 0.98, transition: T.normal   },
};

/**
 * Agent message entry (DeepDive reasoning feed, pipeline log stream).
 * Enters from the right — motion direction reads as "data arriving".
 * Pair with staggerFast as the list container for sequential reveal.
 */
export const agentMessage: MotionVariant = {
  hidden:  { opacity: 0, x: 24 },
  visible: { opacity: 1, x: 0,  transition: T.fast },
  exit:    { opacity: 0, x: 12, transition: T.fast },
};

// =============================================================================
// COUNTER CONFIG
// Configuration for useMotionValue + animate() number counters.
//
//   import { animate, useMotionValue, useTransform } from 'framer-motion';
//   import { counterConfig } from '@/lib/motion';
//
//   const count = useMotionValue(0);
//   useEffect(() => {
//     const ctrl = animate(count, targetValue, counterConfig);
//     return ctrl.stop;
//   }, [targetValue]);
//   const display = useTransform(count, Math.round);
// =============================================================================

export const counterConfig: TransitionConfig = {
  type:     'tween',
  duration: DURATION.feature,   // 600 ms — long enough to build drama
  ease:     EASE_OUT,
};

// =============================================================================
// CSS ANIMATION REFERENCES
// Performance-critical loops that run on the GPU compositor thread.
// Defined as CSS keyframes in src/index.css; referenced here by class name.
// Import the className and apply it — do not recreate these in Framer Motion.
//
//   import { CSS_ANIM } from '@/lib/motion';
//   <span className={CSS_ANIM.glowPulse.className} />
// =============================================================================

export const CSS_ANIM = {
  /**
   * Critical risk pill pulse: opacity 1 → 0.4 → 1
   * Keyframe: pulse-dot  |  Class: .animate-risk-pulse
   * Duration: 2 s · infinite · ease-in-out
   */
  glowPulse: {
    className:  'animate-risk-pulse',
    durationMs: 2000,
    iterationCount: 'infinite' as const,
  },

  /**
   * Skeleton loading shimmer: translateX -100% → 100% overlay
   * Apply to a container with class .skeleton — the ::after pseudo handles the sweep.
   * Duration: 1.8 s · infinite · linear
   */
  shimmer: {
    className:  'skeleton',
    durationMs: 1800,
    iterationCount: 'infinite' as const,
  },
} as const;

// =============================================================================
// UTILITIES
// Pure functions — return a new variant without mutating the original.
// =============================================================================

/**
 * Add a delay to any variant's visible frame.
 * Input in milliseconds (consistent with design-token docs).
 *
 * @example
 *   // Stagger three cards by 80 ms each without a container variant
 *   variants={withDelay(scaleIn, index * 80)}
 */
export function withDelay(variant: MotionVariant, delayMs: number): MotionVariant {
  const delay = delayMs / 1000;
  const visible = variant['visible'];

  // Guard: VariantLabels (string|string[]) have no transition to augment
  if (!visible || typeof visible === 'string' || Array.isArray(visible)) {
    return variant;
  }

  const existingTransition = (visible as { transition?: Transition }).transition ?? {};

  return {
    ...variant,
    visible: {
      ...visible,
      transition: { ...existingTransition, delay },
    },
  };
}

/**
 * Override the visible frame's duration while keeping all other properties.
 * Useful for one-off timing adjustments on shared variants.
 *
 * @example
 *   variants={withDuration(fadeUp, 'slow')}   // same fade, slower on this element
 */
export function withDuration(variant: MotionVariant, key: DurationKey): MotionVariant {
  const duration = DURATION[key];
  const visible  = variant['visible'];

  if (!visible || typeof visible === 'string' || Array.isArray(visible)) {
    return variant;
  }

  const existingTransition = (visible as { transition?: Transition }).transition ?? {};

  return {
    ...variant,
    visible: {
      ...visible,
      transition: { ...existingTransition, duration },
    },
  };
}
