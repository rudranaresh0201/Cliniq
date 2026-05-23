import { useState } from 'react';

interface Episode {
  id?: string;
  patient_id: string;
  query: string;
  triage: string;
  conditions: string[];
  response_summary?: string;
  timestamp?: string;
}

interface TimelineAnalysis {
  patterns_detected: string[];
  trend: 'worsening' | 'stable' | 'improving';
  chronic_risk_flags: string[];
  proactive_recommendation: string;
  urgency: 'routine' | 'urgent' | 'immediate';
  error?: string;
}

const TRIAGE_META: Record<string, { dot: string; pillBg: string; pillText: string; pillBorder: string }> = {
  EMERGENCY:     { dot: '#ef4444', pillBg: 'rgba(239,68,68,0.15)',    pillText: '#fca5a5', pillBorder: 'rgba(239,68,68,0.3)'    },
  URGENT:        { dot: '#FF9500', pillBg: 'rgba(255,149,0,0.15)',    pillText: '#FFD580', pillBorder: 'rgba(255,149,0,0.3)'    },
  ROUTINE:       { dot: '#06D6A0', pillBg: 'rgba(6,214,160,0.15)',    pillText: '#6ee7b7', pillBorder: 'rgba(6,214,160,0.3)'    },
  INFORMATIONAL: { dot: '#7C3AED', pillBg: 'rgba(124,58,237,0.15)',   pillText: '#c4b5fd', pillBorder: 'rgba(124,58,237,0.3)'   },
};

const TREND_ICON: Record<string, string> = {
  worsening: '📉',
  stable:    '➡️',
  improving: '📈',
};

const CONDITION_COLORS = [
  { bg: 'rgba(16,185,129,0.15)',  text: '#6ee7b7', border: 'rgba(16,185,129,0.25)'  },
  { bg: 'rgba(99,102,241,0.15)', text: '#a5b4fc', border: 'rgba(99,102,241,0.25)'  },
  { bg: 'rgba(236,72,153,0.15)', text: '#f9a8d4', border: 'rgba(236,72,153,0.25)'  },
  { bg: 'rgba(234,179,8,0.15)',  text: '#fde68a', border: 'rgba(234,179,8,0.25)'   },
  { bg: 'rgba(139,92,246,0.15)', text: '#c4b5fd', border: 'rgba(139,92,246,0.25)'  },
];

const GLASS: React.CSSProperties = {
  background: '#0F1623',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '16px',
};

function EpisodeCard({ ep, index }: { ep: Episode; index: number }) {
  const [open, setOpen] = useState(false);
  const meta = TRIAGE_META[ep.triage?.toUpperCase()] || TRIAGE_META.INFORMATIONAL;
  const date = ep.timestamp
    ? new Date(ep.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : 'Unknown date';
  const time = ep.timestamp
    ? new Date(ep.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className="flex gap-0 animate-fade-in-up" style={{ animationDelay: `${index * 0.07}s`, opacity: 0 }}>
      {/* Timeline spine */}
      <div className="flex flex-col items-center mr-5 shrink-0">
        <div
          className="w-3.5 h-3.5 rounded-full shrink-0 mt-5"
          style={{
            background: meta.dot,
            boxShadow: `0 0 10px ${meta.dot}80`,
            border: `2px solid rgba(10,15,26,0.8)`,
          }}
        />
        <div
          className="w-px flex-1 mt-1"
          style={{ background: 'linear-gradient(to bottom, rgba(255,255,255,0.08), transparent)' }}
        />
      </div>

      {/* Card */}
      <div className="flex-1 mb-5">
        <div
          className="overflow-hidden transition-all duration-200 hover:shadow-lg"
          style={{
            ...GLASS,
            boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
          }}
        >
          <button className="w-full text-left px-5 py-4" onClick={() => setOpen((o) => !o)}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm leading-snug line-clamp-2" style={{ color: '#e2e8f0' }}>
                  {ep.query}
                </p>

                {ep.conditions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2.5">
                    {ep.conditions.slice(0, 4).map((c, i) => {
                      const col = CONDITION_COLORS[i % CONDITION_COLORS.length];
                      return (
                        <span
                          key={i}
                          className="text-xs font-semibold px-2.5 py-0.5 rounded-full"
                          style={{ background: col.bg, color: col.text, border: `1px solid ${col.border}` }}
                        >
                          {c}
                        </span>
                      );
                    })}
                    {ep.conditions.length > 4 && (
                      <span className="text-xs self-center" style={{ color: 'rgba(255,255,255,0.3)' }}>
                        +{ep.conditions.length - 4} more
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="flex flex-col items-end gap-2 shrink-0">
                <span
                  className="text-xs font-bold px-2.5 py-1 rounded-full"
                  style={{ background: meta.pillBg, color: meta.pillText, border: `1px solid ${meta.pillBorder}` }}
                >
                  {ep.triage}
                </span>
                <div className="text-right">
                  <p className="text-xs font-semibold" style={{ color: 'rgba(255,255,255,0.4)' }}>{date}</p>
                  {time && <p className="text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>{time}</p>}
                </div>
              </div>
            </div>
          </button>

          {open && ep.response_summary && (
            <div
              className="px-5 pb-4 pt-1"
              style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
            >
              <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.55)' }}>
                {ep.response_summary}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [userId, setUserId]     = useState('');
  const [inputVal, setInputVal] = useState('');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [timeline, setTimeline] = useState<TimelineAnalysis | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const load = async (id: string) => {
    setLoading(true);
    setError(null);
    setEpisodes([]);
    setTimeline(null);

    try {
      const [histRes, tlRes] = await Promise.allSettled([
        fetch(`http://127.0.0.1:8000/api/patient/${id}/history`),
        fetch(`http://127.0.0.1:8000/api/patient/${id}/timeline`),
      ]);

      if (histRes.status === 'fulfilled' && histRes.value.ok) {
        const data = await histRes.value.json();
        setEpisodes(data.episodes || []);
      } else {
        setError('Could not load patient history. Make sure the patient ID is correct.');
      }

      if (tlRes.status === 'fulfilled' && tlRes.value.ok) {
        const data = await tlRes.value.json();
        setTimeline(data.timeline_analysis);
      }
    } catch {
      setError('Backend unreachable. Make sure the server is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const id = inputVal.trim();
    if (!id) return;
    setUserId(id);
    load(id);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-7">
      {/* Page header */}
      <div className="animate-fade-in-up">
        <h1
          className="text-2xl font-extrabold tracking-tight"
          style={{ color: '#f1f5f9', fontFamily: 'Sora, sans-serif' }}
        >
          Patient Dashboard
        </h1>
        <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.35)' }}>
          Your longitudinal health timeline, AI-analyzed.
        </p>
      </div>

      {/* Search card */}
      <form onSubmit={handleSearch} className="p-5 animate-fade-in-up stagger-1" style={GLASS}>
        <label className="block text-sm font-bold mb-2" style={{ color: 'rgba(255,255,255,0.6)' }}>
          Patient ID
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Enter your patient ID..."
            className="flex-1 text-sm focus:outline-none"
            style={{
              borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.05)',
              color: '#f1f5f9',
              padding: '10px 16px',
              fontFamily: 'Sora, Inter, sans-serif',
            }}
            onFocus={(e) => {
              e.target.style.borderColor = 'rgba(255,149,0,0.5)';
              e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = 'rgba(255,255,255,0.1)';
              e.target.style.boxShadow = 'none';
            }}
          />
          <button
            type="submit"
            disabled={loading || !inputVal.trim()}
            className="px-6 py-2.5 rounded-xl text-white text-sm font-bold transition-all disabled:opacity-50"
            style={{
              background: 'linear-gradient(135deg, #FF9500, #FF6B00)',
              boxShadow: '0 0 20px rgba(255,149,0,0.3)',
              fontFamily: 'Sora, sans-serif',
            }}
          >
            {loading ? 'Loading…' : 'Load'}
          </button>
        </div>
      </form>

      {error && (
        <div
          className="rounded-xl px-4 py-3 text-sm animate-fade-in-up"
          style={{
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.25)',
            color: '#fca5a5',
          }}
        >
          {error}
        </div>
      )}

      {/* AI Timeline Analysis */}
      {timeline && (
        <div className="overflow-hidden animate-fade-in-up stagger-2" style={GLASS}>
          <div
            className="px-5 py-4 flex items-center gap-3"
            style={{ background: 'linear-gradient(135deg, rgba(255,149,0,0.12), rgba(255,107,0,0.08))' }}
          >
            <h2 className="font-bold" style={{ color: '#f1f5f9', fontFamily: 'Sora, sans-serif' }}>
              AI Timeline Analysis
            </h2>
            <div className="ml-auto flex items-center gap-2">
              <span className="text-lg">{TREND_ICON[timeline.trend] || '➡️'}</span>
              <span className="text-sm font-bold capitalize" style={{ color: 'rgba(255,255,255,0.8)' }}>
                {timeline.trend}
              </span>
            </div>
          </div>

          <div className="p-5 space-y-4">
            {timeline.patterns_detected.length > 0 && (
              <div>
                <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  Patterns Detected
                </p>
                <ul className="space-y-1.5">
                  {timeline.patterns_detected.map((p, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>
                      <span className="text-amber-400 shrink-0 mt-0.5">◆</span>{p}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {timeline.chronic_risk_flags.length > 0 && (
              <div
                className="rounded-xl px-4 py-3"
                style={{
                  background: 'rgba(249,115,22,0.1)',
                  border: '1px solid rgba(249,115,22,0.2)',
                }}
              >
                <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: '#fdba74' }}>
                  Chronic Risk Flags
                </p>
                <ul className="space-y-1">
                  {timeline.chronic_risk_flags.map((f, i) => (
                    <li key={i} className="text-sm" style={{ color: 'rgba(253,186,116,0.8)' }}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            <div
              className="rounded-xl px-4 py-3"
              style={{
                background: 'rgba(6,214,160,0.08)',
                border: '1px solid rgba(6,214,160,0.2)',
              }}
            >
              <p className="text-xs font-bold uppercase tracking-widest mb-1" style={{ color: '#06D6A0' }}>
                Recommendation
              </p>
              <p className="text-sm" style={{ color: 'rgba(167,243,208,0.85)' }}>
                {timeline.proactive_recommendation}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {userId && !loading && episodes.length === 0 && !error && (
        <div className="text-center py-16 animate-fade-in-up">
          <p className="font-bold text-lg" style={{ color: 'rgba(255,255,255,0.5)' }}>No episodes found</p>
          <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Start by analyzing some symptoms on the Analyze tab.
          </p>
        </div>
      )}

      {/* Timeline */}
      {episodes.length > 0 && (
        <div className="animate-fade-in-up stagger-3">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>
              Episode History
            </h2>
            <span
              className="text-xs font-bold px-2.5 py-1 rounded-full"
              style={{
                background: 'rgba(6,214,160,0.12)',
                color: '#6ee7b7',
                border: '1px solid rgba(6,214,160,0.25)',
              }}
            >
              {episodes.length} episodes
            </span>
          </div>

          <div>
            {episodes.map((ep, i) => (
              <EpisodeCard key={ep.id || i} ep={ep} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
