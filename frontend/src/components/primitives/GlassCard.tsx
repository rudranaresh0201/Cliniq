import type { ReactNode, CSSProperties } from 'react';
import { motion } from 'framer-motion';
import { scaleIn } from '../../lib/motion';

type Glow = 'accent' | 'critical' | 'warning' | 'stable' | 'none';

interface GlassCardProps {
  children: ReactNode;
  glow?: Glow;
  elevated?: boolean;
  className?: string;
  style?: CSSProperties;
}

const GLOW_SHADOW: Record<Exclude<Glow, 'none'>, string> = {
  critical: '0 0 40px var(--critical-glow), inset 0 1px 0 rgba(255,68,68,0.1)',
  accent:   '0 0 40px var(--accent-glow),   inset 0 1px 0 rgba(124,101,246,0.1)',
  stable:   '0 0 40px var(--stable-glow),   inset 0 1px 0 rgba(34,197,94,0.1)',
  warning:  '0 0 40px var(--warning-glow),  inset 0 1px 0 rgba(245,158,11,0.1)',
};

const ELEVATED = '0 24px 48px rgba(0,0,0,0.4)';

function buildBoxShadow(glow: Glow, elevated: boolean): string {
  const g = glow !== 'none' ? GLOW_SHADOW[glow] : '';
  if (g && elevated) return `${g}, ${ELEVATED}`;
  if (g) return g;
  if (elevated) return ELEVATED;
  return 'none';
}

export function GlassCard({ children, glow = 'none', elevated = false, className, style }: GlassCardProps) {
  return (
    <motion.div
      variants={scaleIn}
      initial="hidden"
      animate="visible"
      className={className}
      style={{
        background: 'var(--bg-glass)',
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '16px',
        boxShadow: buildBoxShadow(glow, elevated),
        transition: 'box-shadow var(--transition-base)',
        ...style,
      }}
    >
      {children}
    </motion.div>
  );
}
