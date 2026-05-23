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

const TRIAGE_META: Record<string, { dot: string; pill_bg: string; pill_text: string; label_color: string }> = {
  EMERGENCY:     { dot: '#dc2626', pill_bg: '#fef2f2', pill_text: '#991b1b', label_color: '#dc2626' },
  URGENT:        { dot: '#ea580c', pill_bg: '#fff7ed', pill_text: '#9a3412', label_color: '#ea580c' },
  ROUTINE:       { dot: '#16a34a', pill_bg: '#f0fdf4', pill_text: '#166534', label_color: '#16a34a' },
  INFORMATIONAL: { dot: '#2563eb', pill_bg: '#eff6ff', pill_text: '#1e40af', label_color: '#2563eb' },
};

const TREND_ICON: Record<string, string> = {
  worsening: '📉',
  stable:    '➡️',
  improving: '📈',
};

const CONDITION_COLORS = [
  { bg: '#dcfce7', text: '#15803d' },
  { bg: '#dbeafe', text: '#1d4ed8' },
  { bg: '#fce7f3', text: '#9d174d' },
  { bg: '#fef3c7', text: '#92400e' },
  { bg: '#ede9fe', text: '#5b21b6' },
];

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
    <div className="flex gap-0 animate-fade-in-up" style={{ animationDelay: `${index * 0.07}s` }}>
      {/* Timeline spine */}
      <div className="flex flex-col items-center mr-5 shrink-0">
        <div
          className="w-4 h-4 rounded-full border-4 border-white shadow-md shrink-0 mt-5"
          style={{ background: meta.dot }}
        />
        <div className="w-0.5 flex-1 mt-1" style={{ background: 'linear-gradient(to bottom, #e2e8f0, transparent)' }} />
      </div>

      {/* Card */}
      <div className="flex-1 mb-5">
        <div className="bg-white rounded-2xl border border-slate-100 shadow-md overflow-hidden hover:shadow-lg transition-shadow">
          <button
            className="w-full text-left px-5 py-4"
            onClick={() => setOpen((o) => !o)}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-800 text-sm leading-snug line-clamp-2">
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
                          style={{ background: col.bg, color: col.text }}
                        >
                          {c}
                        </span>
                      );
                    })}
                    {ep.conditions.length > 4 && (
                      <span className="text-xs text-slate-400 self-center">+{ep.conditions.length - 4} more</span>
                    )}
                  </div>
                )}
              </div>

              <div className="flex flex-col items-end gap-2 shrink-0">
                <span
                  className="text-xs font-bold px-2.5 py-1 rounded-full"
                  style={{ background: meta.pill_bg, color: meta.pill_text }}
                >
                  {ep.triage}
                </span>
                <div className="text-right">
                  <p className="text-xs font-semibold text-slate-500">{date}</p>
                  {time && <p className="text-xs text-slate-400">{time}</p>}
                </div>
              </div>
            </div>
          </button>

          {open && ep.response_summary && (
            <div className="px-5 pb-4 pt-1 border-t border-slate-50">
              <p className="text-sm text-slate-600 leading-relaxed">{ep.response_summary}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [userId, setUserId]   = useState('');
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
        <h1 className="text-2xl font-extrabold text-slate-800 tracking-tight">Patient Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">Your longitudinal health timeline, AI-analyzed.</p>
      </div>

      {/* Search card */}
      <form
        onSubmit={handleSearch}
        className="bg-white rounded-2xl border border-slate-100 shadow-md p-5 animate-fade-in-up stagger-1"
      >
        <label className="block text-sm font-bold text-slate-700 mb-2">Patient ID</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Enter your patient ID..."
            className="flex-1 rounded-xl border-2 border-slate-200 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-green-400 transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !inputVal.trim()}
            className="px-6 py-2.5 rounded-xl text-white text-sm font-bold transition-all disabled:opacity-50 shadow-sm hover:shadow-md"
            style={{ background: 'linear-gradient(135deg,#16a34a,#0d9488)' }}
          >
            {loading ? 'Loading…' : 'Load'}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 animate-fade-in-up">
          {error}
        </div>
      )}

      {/* AI Timeline Analysis */}
      {timeline && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-md overflow-hidden animate-fade-in-up stagger-2">
          <div
            className="px-5 py-4 flex items-center gap-3"
            style={{ background: 'linear-gradient(135deg,#16a34a,#0d9488)' }}
          >
            <span className="text-xl">🧠</span>
            <h2 className="font-bold text-white">AI Timeline Analysis</h2>
            <div className="ml-auto flex items-center gap-2">
              <span className="text-lg">{TREND_ICON[timeline.trend] || '➡️'}</span>
              <span className="text-sm font-bold text-white/90 capitalize">{timeline.trend}</span>
            </div>
          </div>

          <div className="p-5 space-y-4">
            {timeline.patterns_detected.length > 0 && (
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                  Patterns Detected
                </p>
                <ul className="space-y-1.5">
                  {timeline.patterns_detected.map((p, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                      <span className="text-amber-400 shrink-0 mt-0.5">◆</span>{p}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {timeline.chronic_risk_flags.length > 0 && (
              <div className="bg-orange-50 rounded-xl px-4 py-3 border border-orange-100">
                <p className="text-xs font-bold text-orange-600 uppercase tracking-widest mb-2">
                  Chronic Risk Flags
                </p>
                <ul className="space-y-1">
                  {timeline.chronic_risk_flags.map((f, i) => (
                    <li key={i} className="text-sm text-orange-800">⚠️ {f}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="rounded-xl px-4 py-3 border border-green-100" style={{ background: '#f0fdf4' }}>
              <p className="text-xs font-bold text-green-600 uppercase tracking-widest mb-1">
                Recommendation
              </p>
              <p className="text-sm text-green-900">{timeline.proactive_recommendation}</p>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {userId && !loading && episodes.length === 0 && !error && (
        <div className="text-center py-16 animate-fade-in-up">
          <p className="text-5xl mb-4">📋</p>
          <p className="font-bold text-slate-600 text-lg">No episodes found</p>
          <p className="text-sm text-slate-400 mt-1">Start by analyzing some symptoms on the Analyze tab.</p>
        </div>
      )}

      {/* Timeline */}
      {episodes.length > 0 && (
        <div className="animate-fade-in-up stagger-3">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              Episode History
            </h2>
            <span
              className="text-xs font-bold px-2.5 py-1 rounded-full"
              style={{ background: '#dcfce7', color: '#15803d' }}
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
