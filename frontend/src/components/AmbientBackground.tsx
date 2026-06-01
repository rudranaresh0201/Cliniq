// Shared 3-layer ambient background used by every patient-facing page.
// Layer 1 (void base) lives on the page root div — this component provides layers 2 + 3.
// Layer 2: fixed radial glow, risk-state-aware, breathes via scale+opacity loop.
// Layer 3: SVG feTurbulence noise at opacity 0.015 — organic depth without grain.

import { useId } from 'react';
import { motion } from 'framer-motion';

export type AmbientGlow = 'accent' | 'warning' | 'critical' | 'stable';

interface AmbientBackgroundProps {
  glow?: AmbientGlow;
}

const GLOW_GRADIENT: Record<AmbientGlow, string> = {
  accent:   'radial-gradient(ellipse 60vw 40vh at 50% 0%, rgba(124,101,246,0.06) 0%, transparent 70%)',
  warning:  'radial-gradient(ellipse 60vw 40vh at 50% 0%, rgba(245,158,11,0.06)  0%, transparent 70%)',
  critical: 'radial-gradient(ellipse 60vw 40vh at 50% 0%, rgba(255,68,68,0.07)   0%, transparent 70%)',
  stable:   'radial-gradient(ellipse 60vw 40vh at 50% 0%, rgba(34,197,94,0.05)   0%, transparent 70%)',
};

export function AmbientBackground({ glow = 'accent' }: AmbientBackgroundProps) {
  const uid = useId().replace(/:/g, '');

  return (
    <>
      {/* Layer 2 — risk glow, breathes 4s mirror */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.1, ease: 'easeOut' }}
        style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }}
      >
        <motion.div
          animate={{ opacity: [0.7, 1.0], scale: [1, 1.04] }}
          transition={{ duration: 4, ease: 'easeInOut', repeat: Infinity, repeatType: 'mirror' }}
          style={{ position: 'absolute', inset: 0, background: GLOW_GRADIENT[glow], transformOrigin: '50% 0%' }}
        />
      </motion.div>

      {/* Layer 3 — noise texture */}
      <svg
        style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', zIndex: 0, pointerEvents: 'none', opacity: 0.015 }}
        aria-hidden
      >
        <defs>
          <filter id={`amb-noise-${uid}`}>
            <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch" />
            <feColorMatrix type="saturate" values="0" />
          </filter>
        </defs>
        <rect width="100%" height="100%" filter={`url(#amb-noise-${uid})`} />
      </svg>
    </>
  );
}
