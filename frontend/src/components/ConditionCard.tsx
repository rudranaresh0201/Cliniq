import { useState } from 'react';
import type { Condition } from '../types';

interface Props {
  condition: Condition;
  index: number;
}

function barGradient(pct: number) {
  if (pct >= 70) return 'linear-gradient(90deg, #10b981, #06b6d4)';
  if (pct >= 40) return 'linear-gradient(90deg, #f59e0b, #d97706)';
  return 'linear-gradient(90deg, #ef4444, #dc2626)';
}

function badgeStyle(index: number): React.CSSProperties {
  const styles: React.CSSProperties[] = [
    { background: 'linear-gradient(135deg,#10b981,#06b6d4)', color: '#fff' },
    { background: 'linear-gradient(135deg,#6366f1,#4f46e5)', color: '#fff' },
    { background: 'linear-gradient(135deg,#8b5cf6,#7c3aed)', color: '#fff' },
    { background: 'linear-gradient(135deg,#475569,#334155)', color: '#fff' },
  ];
  return styles[index] || styles[3];
}

export default function ConditionCard({ condition, index }: Props) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(condition.confidence);
  const hasEvidence = condition.evidence && condition.evidence.length > 0;

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all duration-200 hover:-translate-y-0.5 animate-fade-in-up"
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        backdropFilter: 'blur(20px)',
        boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
        animationDelay: `${index * 0.08}s`,
        opacity: 0,
      }}
    >
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start gap-4">
          {/* Rank badge */}
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 text-sm font-extrabold"
            style={badgeStyle(index)}
          >
            {index + 1}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="font-bold text-base truncate" style={{ color: '#f1f5f9', fontFamily: 'Sora, sans-serif' }}>
                {condition.name}
              </span>
              <span
                className="text-sm font-extrabold shrink-0 tabular-nums"
                style={{
                  color: pct >= 70 ? '#34d399' : pct >= 40 ? '#fbbf24' : '#f87171',
                }}
              >
                {pct}%
              </span>
            </div>

            {/* Confidence bar */}
            <div
              className="h-1.5 rounded-full overflow-hidden mt-2"
              style={{ background: 'rgba(255,255,255,0.08)' }}
            >
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${pct}%`,
                  background: barGradient(pct),
                  boxShadow: pct >= 70 ? '0 0 8px rgba(16,185,129,0.5)' : 'none',
                }}
              />
            </div>
          </div>
        </div>

        {hasEvidence && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="mt-3.5 ml-[52px] inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full transition-all"
            style={{
              background: expanded ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.06)',
              color: expanded ? '#34d399' : 'rgba(255,255,255,0.45)',
              border: expanded ? '1px solid rgba(16,185,129,0.3)' : '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <svg
              className={`w-3 h-3 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            {expanded ? 'Hide evidence' : `View evidence (${condition.evidence.length})`}
          </button>
        )}
      </div>

      {expanded && hasEvidence && (
        <div
          className="mx-5 mb-5 rounded-xl p-4 space-y-3"
          style={{
            background: 'rgba(16,185,129,0.05)',
            border: '1px solid rgba(16,185,129,0.15)',
          }}
        >
          <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Supporting Evidence
          </p>
          <ul className="space-y-3">
            {condition.evidence.map((ev, i) => {
              const pmidMatch = ev.match(/PMID[:\s]+(\d+)/i);
              const pmid = pmidMatch ? pmidMatch[1] : null;
              return (
                <li
                  key={i}
                  className="pl-3 py-1.5 text-sm italic leading-relaxed rounded-r-lg"
                  style={{
                    borderLeft: '2px solid rgba(16,185,129,0.5)',
                    color: 'rgba(255,255,255,0.6)',
                  }}
                >
                  "{ev}"
                  {pmid && (
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="not-italic ml-2 text-xs font-bold hover:underline transition-colors"
                      style={{ color: '#34d399' }}
                    >
                      PubMed →
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
