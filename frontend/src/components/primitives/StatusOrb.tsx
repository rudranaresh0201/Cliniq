import { motion } from 'framer-motion';

interface StatusOrbProps {
  live: boolean;
  size?: number;
}

const GREEN  = '#22C55E';
const MUTED  = 'var(--text-muted, #4A4A5A)';

export function StatusOrb({ live, size = 12 }: StatusOrbProps) {
  const color = live ? GREEN : MUTED;
  const inner = Math.round(size * 0.55);

  return (
    <span
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        flexShrink: 0,
      }}
    >
      {/* Outer expanding ring — opacity + scale pulse */}
      <motion.span
        animate={live
          ? { scale: [1, 2, 1], opacity: [0.55, 0, 0.55] }
          : { scale: 1, opacity: 0 }
        }
        transition={live
          ? { duration: 2, repeat: Infinity, ease: 'easeInOut' }
          : { duration: 0 }
        }
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          border: `1.5px solid ${color}`,
          pointerEvents: 'none',
        }}
      />

      {/* Inner solid dot with ambient glow */}
      <span
        style={{
          width: inner,
          height: inner,
          borderRadius: '50%',
          backgroundColor: color,
          display: 'block',
          position: 'relative',
          boxShadow: live
            ? `0 0 ${size}px rgba(34,197,94,0.5), 0 0 ${size * 2}px rgba(34,197,94,0.25)`
            : 'none',
          transition: 'background-color 0.3s, box-shadow 0.3s',
        }}
      />
    </span>
  );
}
