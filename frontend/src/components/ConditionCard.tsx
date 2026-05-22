import { useState } from 'react';
import type { Condition } from '../types';

interface Props {
  condition: Condition;
  index: number;
}

function confidenceColor(pct: number) {
  if (pct >= 70) return '#4CAF50';
  if (pct >= 40) return '#F5C518';
  return '#EF4444';
}

export default function ConditionCard({ condition, index }: Props) {
  const [expanded, setExpanded] = useState(false);
  // API sends 0-100 directly — no multiplication needed
  const pct = Math.round(condition.confidence);
  const barColor = confidenceColor(pct);
  const hasEvidence = condition.evidence && condition.evidence.length > 0;

  return (
    <div className="bg-white rounded-xl shadow-md border border-slate-100 overflow-hidden transition-shadow hover:shadow-lg">
      {/* Header row — NOT a button so clicks don't conflict */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <span
              className="w-7 h-7 rounded-full text-white text-xs font-bold flex items-center justify-center shrink-0"
              style={{ background: barColor }}
            >
              {index + 1}
            </span>
            <span className="font-semibold text-slate-800 truncate">{condition.name}</span>
          </div>
          <span className="text-sm font-bold shrink-0" style={{ color: barColor }}>
            {pct}%
          </span>
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%`, background: barColor }}
          />
        </div>

        {/* Show evidence button — only when evidence exists */}
        {hasEvidence && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full transition-colors"
            style={{
              background: expanded ? '#E8F5E9' : '#f1f5f9',
              color: expanded ? '#2E7D32' : '#64748b',
            }}
          >
            <svg
              className={`w-3 h-3 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            {expanded ? 'Hide evidence' : `Show evidence (${condition.evidence.length})`}
          </button>
        )}
      </div>

      {/* Expandable evidence panel */}
      {expanded && hasEvidence && (
        <div className="border-t-2 border-green-100 mx-5 mb-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-3 mb-2">
            Supporting Evidence
          </p>
          <ul className="space-y-2.5">
            {condition.evidence.map((ev, i) => {
              const pmidMatch = ev.match(/PMID[:\s]+(\d+)/i);
              const pmid = pmidMatch ? pmidMatch[1] : null;
              return (
                <li
                  key={i}
                  className="pl-3 py-1.5 text-sm text-slate-600 italic leading-relaxed"
                  style={{ borderLeft: '3px solid #4CAF50' }}
                >
                  "{ev}"
                  {pmid && (
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="not-italic ml-2 text-xs font-semibold text-green-600 hover:underline"
                    >
                      View on PubMed →
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
