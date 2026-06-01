import { motion } from 'framer-motion';
import { scaleIn, SPRING_BOUNCE, CSS_ANIM } from '../../lib/motion';

export type RiskStatus = 'critical' | 'warning' | 'stable' | 'monitoring';

interface PillTokens {
  bg: string;
  border: string;
  color: string;
  dot: string;
  glow: string;
}

const TOKENS: Record<RiskStatus, PillTokens> = {
  critical:   { bg: 'rgba(255,68,68,0.12)',  border: 'rgba(255,68,68,0.3)',  color: '#FF6B6B', dot: '#FF4444', glow: '0 0 8px rgba(255,68,68,0.5)' },
  warning:    { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', color: '#FBBF24', dot: '#F59E0B', glow: '0 0 8px rgba(245,158,11,0.5)' },
  stable:     { bg: 'rgba(34,197,94,0.12)',  border: 'rgba(34,197,94,0.3)',  color: '#4ADE80', dot: '#22C55E', glow: '0 0 8px rgba(34,197,94,0.5)'  },
  monitoring: { bg: 'rgba(45,212,191,0.12)', border: 'rgba(45,212,191,0.3)', color: '#2DD4BF', dot: '#14B8A6', glow: '0 0 8px rgba(45,212,191,0.5)' },
};

const LABEL: Record<RiskStatus, string> = {
  critical:   'Critical',
  warning:    'Warning',
  stable:     'Stable',
  monitoring: 'Monitoring',
};

interface RiskPillProps {
  status: RiskStatus;
}

export function RiskPill({ status }: RiskPillProps) {
  const t = TOKENS[status];
  return (
    <motion.span
      variants={scaleIn}
      initial="hidden"
      animate="visible"
      transition={SPRING_BOUNCE}
      whileHover={{ scale: 1.02 }}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '6px 14px',
        borderRadius: '999px',
        background: t.bg,
        border: `1px solid ${t.border}`,
        color: t.color,
        fontSize: '13px',
        fontWeight: 600,
        lineHeight: 1,
        letterSpacing: '0.1px',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        userSelect: 'none',
        cursor: 'default',
        whiteSpace: 'nowrap',
      }}
    >
      <span
        className={status === 'critical' ? CSS_ANIM.glowPulse.className : undefined}
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          backgroundColor: t.dot,
          boxShadow: t.glow,
          flexShrink: 0,
        }}
      />
      {LABEL[status]}
    </motion.span>
  );
}
