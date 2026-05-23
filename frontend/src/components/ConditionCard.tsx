import { useState } from 'react';
import type { Condition } from '../types';

interface Props {
  condition: Condition;
  index: number;
}

function barGradient(pct: number) {
  if (pct >= 70) return 'linear-gradient(90deg, #16a34a, #0d9488)';
  if (pct >= 40) return 'linear-gradient(90deg, #d97706, #f59e0b)';
  return 'linear-gradient(90deg, #dc2626, #ef4444)';
}

function badgeColor(index: number) {
  const colors = [
    { bg: 'linear-gradient(135deg,#16a34a,#0d9488)', text: '#fff' },
    { bg: 'linear-gradient(135deg,#2563eb,#4f46e5)', text: '#fff' },
    { bg: 'linear-gradient(135deg,#7c3aed,#6d28d9)', text: '#fff' },
    { bg: 'linear-gradient(135deg,#64748b,#475569)', text: '#fff' },
  ];
  return colors[index] || colors[3];
}

export default function ConditionCard({ condition, index }: Props) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(condition.confidence);
  const hasEvidence = condition.evidence && condition.evidence.length > 0;
  const badge = badgeColor(index);

  return (
    <div
      className="bg-white rounded-2xl shadow-md border border-slate-100 overflow-hidden transition-all duration-200 hover:shadow-xl hover:-translate-y-0.5 animate-fade-in-up"
      style={{ animationDelay: `${index * 0.08}s` }}
    >
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start gap-4">
          {/* Rank badge */}
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-sm text-sm font-extrabold"
            style={{ background: badge.bg, color: badge.text }}
          >
            {index + 1}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="font-bold text-slate-800 text-base truncate">
                {condition.name}
              </span>
              <span
                className="text-sm font-extrabold shrink-0 tabular-nums"
                style={{ color: pct >= 70 ? '#16a34a' : pct >= 40 ? '#d97706' : '#dc2626' }}
              >
                {pct}%
              </span>
            </div>

            {/* Animated confidence bar */}
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden mt-2">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${pct}%`,
                  background: barGradient(pct),
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
              background: expanded ? '#dcfce7' : '#f1f5f9',
              color: expanded ? '#15803d' : '#64748b',
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
          style={{ background: '#f8fafc', border: '1.5px solid #e2e8f0' }}
        >
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">
            Supporting Evidence
          </p>
          <ul className="space-y-3">
            {condition.evidence.map((ev, i) => {
              const pmidMatch = ev.match(/PMID[:\s]+(\d+)/i);
              const pmid = pmidMatch ? pmidMatch[1] : null;
              return (
                <li
                  key={i}
                  className="pl-3 py-1.5 text-sm text-slate-600 italic leading-relaxed rounded-r-lg"
                  style={{ borderLeft: '3px solid #16a34a', background: 'rgba(22,163,74,0.04)' }}
                >
                  "{ev}"
                  {pmid && (
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="not-italic ml-2 text-xs font-bold text-green-600 hover:text-green-800 hover:underline transition-colors"
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
