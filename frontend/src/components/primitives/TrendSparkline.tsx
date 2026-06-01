// Native SVG sparkline — no recharts dependency.
// Renders a smooth bezier curve + gradient area fill, matching the recharts spec visually.

import { useId, useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface TrendSparklineProps {
  data: number[];
  color: string;
  unit: string;
  trend: 'up' | 'down' | 'stable';
  danger?: boolean;
}

const W = 120;
const H = 40;
const PAD_X = 4;
const PAD_Y = 4;

// Normalize data → SVG coordinate space
function toPoints(data: number[]): [number, number][] {
  if (data.length < 2) return [];
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const plotW = W - PAD_X * 2;
  const plotH = H - PAD_Y * 2;

  return data.map((v, i) => [
    PAD_X + (i / (data.length - 1)) * plotW,
    PAD_Y + plotH - ((v - min) / range) * plotH,
  ]);
}

// Catmull-Rom → cubic Bézier for a smooth curve through all points
function smoothLinePath(pts: [number, number][]): string {
  if (pts.length < 2) return '';
  const d: string[] = [`M ${pts[0][0]} ${pts[0][1]}`];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(i - 1, 0)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(i + 2, pts.length - 1)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    d.push(`C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2[0]} ${p2[1]}`);
  }
  return d.join(' ');
}

// Close line path down to bottom to form area fill
function areaPath(pts: [number, number][]): string {
  if (pts.length < 2) return '';
  const line = smoothLinePath(pts);
  const last = pts[pts.length - 1];
  const first = pts[0];
  return `${line} L ${last[0]} ${H} L ${first[0]} ${H} Z`;
}

interface TooltipState {
  x: number;
  y: number;
  value: number;
  visible: boolean;
}

export function TrendSparkline({ data, color, unit, danger = false }: TrendSparklineProps) {
  const uid = useId().replace(/:/g, '');
  const gradientId = `sg-${uid}`;
  const clipId = `sc-${uid}`;
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState>({ x: 0, y: 0, value: 0, visible: false });

  if (data.length < 2) return null;

  const pts = toPoints(data);
  const lastPt = pts[pts.length - 1];
  const linePath = smoothLinePath(pts);
  const fillPath = areaPath(pts);

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const rawX = ((e.clientX - rect.left) / rect.width) * W;
    const idx = Math.round(((rawX - PAD_X) / (W - PAD_X * 2)) * (data.length - 1));
    const clampedIdx = Math.max(0, Math.min(data.length - 1, idx));
    const pt = pts[clampedIdx];
    setTooltip({ x: pt[0], y: pt[1], value: data[clampedIdx], visible: true });
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block', width: W, height: H + 28 }}>
      <svg
        ref={svgRef}
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(t => ({ ...t, visible: false }))}
        style={{ display: 'block', overflow: 'visible', cursor: 'crosshair' }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.2} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
          <clipPath id={clipId}>
            <rect x={0} y={0} width={W} height={H} />
          </clipPath>
        </defs>

        <g clipPath={`url(#${clipId})`}>
          {/* Area fill */}
          <path d={fillPath} fill={`url(#${gradientId})`} />
          {/* Line */}
          <path d={linePath} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        </g>

        {/* Crosshair vertical line */}
        {tooltip.visible && (
          <line
            x1={tooltip.x} y1={0}
            x2={tooltip.x} y2={H}
            stroke={color}
            strokeWidth={1}
            strokeDasharray="2 2"
            opacity={0.4}
          />
        )}

        {/* Hover dot at cursor */}
        {tooltip.visible && (
          <circle cx={tooltip.x} cy={tooltip.y} r={3} fill={color} />
        )}

        {/* Last-point dot */}
        <motion.circle
          cx={lastPt[0]}
          cy={lastPt[1]}
          r={4}
          fill={color}
          animate={danger
            ? { r: [4, 6, 4], opacity: [1, 0.5, 1] }
            : { r: 4, opacity: 1 }
          }
          transition={danger
            ? { duration: 1.5, repeat: Infinity, ease: 'easeInOut' }
            : {}
          }
        />
        {danger && (
          <motion.circle
            cx={lastPt[0]}
            cy={lastPt[1]}
            r={6}
            fill="none"
            stroke={color}
            strokeWidth={1}
            animate={{ r: [6, 10], opacity: [0.6, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
      </svg>

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: Math.min(Math.max(tooltip.x - 24, 0), W - 52),
            background: 'var(--bg-glass)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '4px 8px',
            fontSize: '11px',
            fontFamily: 'JetBrains Mono, monospace',
            fontWeight: 500,
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
          }}
        >
          {typeof tooltip.value === 'number'
            ? tooltip.value % 1 === 0
              ? tooltip.value
              : tooltip.value.toFixed(1)
            : tooltip.value}
          {' '}
          <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>{unit}</span>
        </div>
      )}
    </div>
  );
}
