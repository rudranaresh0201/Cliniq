import { useEffect, useState } from 'react';
import { motion, useMotionValue, useMotionValueEvent, animate } from 'framer-motion';
import { counterConfig } from '../../lib/motion';

export type ValueSize   = 'hero' | 'lg' | 'md' | 'sm';
export type ValueStatus = 'normal' | 'low' | 'high' | 'critical';

interface ValueDisplayProps {
  value: number | string;
  unit?: string;
  size?: ValueSize;
  status?: ValueStatus;
}

const FONT_SIZE: Record<ValueSize, string> = {
  hero: '72px',
  lg:   '36px',
  md:   '20px',
  sm:   '15px',
};

const FONT_WEIGHT: Record<ValueSize, number> = {
  hero: 700,
  lg:   600,
  md:   500,
  sm:   400,
};

const LETTER_SPACING: Record<ValueSize, string> = {
  hero: '-2px',
  lg:   '-1px',
  md:   '-0.3px',
  sm:   '0px',
};

const UNIT_FONT_SIZE: Record<ValueSize, string> = {
  hero: '22px',
  lg:   '14px',
  md:   '12px',
  sm:   '11px',
};

const UNIT_PADDING_BOTTOM: Record<ValueSize, string> = {
  hero: '8px',
  lg:   '4px',
  md:   '2px',
  sm:   '1px',
};

const HERO_GRADIENT: React.CSSProperties = {
  background: 'linear-gradient(135deg, var(--text-primary, #F0F0F4) 0%, var(--text-accent, #9B87FF) 100%)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text',
  color: 'var(--text-primary)',
};

function resolveColor(status: ValueStatus): string | undefined {
  if (status === 'low' || status === 'high') return '#FBBF24';
  if (status === 'critical') return '#FF4444';
  return undefined; // normal → gradient or inherit
}

export function ValueDisplay({ value, unit, size = 'md', status = 'normal' }: ValueDisplayProps) {
  const isNumeric   = typeof value === 'number' || (typeof value === 'string' && value !== '' && !isNaN(Number(value)));
  const numTarget   = isNumeric ? Number(value) : 0;
  const hasDecimal  = isNumeric && String(value).includes('.');

  const count = useMotionValue(0);
  const [text, setText] = useState<string>(isNumeric ? '0' : String(value));

  // Sync formatted display text to state on every animation frame
  useMotionValueEvent(count, 'change', (v) => {
    setText(hasDecimal ? v.toFixed(1) : String(Math.round(v)));
  });

  useEffect(() => {
    if (!isNumeric) {
      setText(String(value));
      return;
    }
    // Reset to 0 then animate to target on value change
    count.set(0);
    const ctrl = animate(count, numTarget, counterConfig);
    // ctrl.stop is a bound function — safe to return directly as cleanup
    return ctrl.stop;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numTarget]);

  const color = resolveColor(status);

  const valueStyle: React.CSSProperties = {
    fontFamily:         'JetBrains Mono, Fira Code, Cascadia Code, monospace',
    fontSize:           FONT_SIZE[size],
    fontWeight:         FONT_WEIGHT[size],
    lineHeight:         1.1,
    letterSpacing:      LETTER_SPACING[size],
    fontVariantNumeric: 'tabular-nums',
    fontFeatureSettings: '"zero" 1, "liga" 0',
    WebkitFontSmoothing: 'subpixel-antialiased',
    ...(color
      ? { color }
      : size === 'hero' && status === 'normal'
        ? HERO_GRADIENT
        : { color: 'var(--text-primary)' }),
  };

  return (
    <motion.span
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
      style={{ display: 'inline-flex', alignItems: 'baseline' }}
    >
      <span style={valueStyle}>{text}</span>
      {unit && (
        <span
          style={{
            fontFamily:   'JetBrains Mono, monospace',
            fontSize:     UNIT_FONT_SIZE[size],
            fontWeight:   400,
            letterSpacing: '0',
            color:         color ?? 'var(--text-muted)',
            marginLeft:    '4px',
            alignSelf:     'flex-end',
            paddingBottom: UNIT_PADDING_BOTTOM[size],
          }}
        >
          {unit}
        </span>
      )}
    </motion.span>
  );
}
