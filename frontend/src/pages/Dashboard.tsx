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

const TRIAGE_STYLE: Record<string, { bg: string; text: string; dot: string }> = {
  EMERGENCY:     { bg: '#FEF2F2', text: '#991B1B', dot: '#DC2626' },
  URGENT:        { bg: '#FFF7ED', text: '#9A3412', dot: '#EA580C' },
  ROUTINE:       { bg: '#F0FDF4', text: '#166534', dot: '#4CAF50' },
  INFORMATIONAL: { bg: '#EFF6FF', text: '#1E40AF', dot: '#2563EB' },
};

const TREND_ICON: Record<string, string> = {
  worsening: '📉',
  stable: '➡️',
  improving: '📈',
};

function TriageDot({ level }: { level: string }) {
  const style = TRIAGE_STYLE[level] || TRIAGE_STYLE.INFORMATIONAL;
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full shrink-0 mt-1"
      style={{ background: style.dot }}
    />
  );
}

function EpisodeRow({ ep }: { ep: Episode }) {
  const [open, setOpen] = useState(false);
  const style = TRIAGE_STYLE[ep.triage] || TRIAGE_STYLE.INFORMATIONAL;
  const date = ep.timestamp ? ep.timestamp.slice(0, 10) : 'Unknown date';

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
      <button
        className="w-full text-left px-5 py-4 flex items-start gap-3"
        onClick={() => setOpen((o) => !o)}
      >
        <TriageDot level={ep.triage} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-800 truncate">{ep.query}</p>
            <div className="flex items-center gap-2 shrink-0">
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ background: style.bg, color: style.text }}
              >
                {ep.triage}
              </span>
              <span className="text-xs text-slate-400">{date}</span>
            </div>
          </div>
          {ep.conditions.length > 0 && (
            <p className="text-xs text-slate-500 mt-1 truncate">
              {ep.conditions.join(', ')}
            </p>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform duration-200 shrink-0 mt-0.5 ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && ep.response_summary && (
        <div className="px-5 pb-4 pt-1 border-t border-slate-50">
          <p className="text-sm text-slate-600 leading-relaxed">{ep.response_summary}</p>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [userId, setUserId] = useState('');
  const [inputVal, setInputVal] = useState('');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [timeline, setTimeline] = useState<TimelineAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Patient Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">View your health timeline and longitudinal patterns.</p>
      </div>

      {/* User ID search */}
      <form onSubmit={handleSearch} className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
        <label className="block text-sm font-semibold text-slate-700 mb-2">Patient ID</label>
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
            className="px-5 py-2.5 rounded-xl text-sm font-bold text-slate-900 transition-all disabled:opacity-50"
            style={{ background: '#F5C518' }}
          >
            {loading ? 'Loading…' : 'Load'}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Timeline analysis */}
      {timeline && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-md p-5 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🧠</span>
            <h2 className="font-bold text-slate-800">AI Timeline Analysis</h2>
            <span className="ml-auto text-lg">{TREND_ICON[timeline.trend] || '➡️'}</span>
            <span className="text-sm font-semibold text-slate-600 capitalize">{timeline.trend}</span>
          </div>

          {timeline.patterns_detected.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Patterns Detected</p>
              <ul className="space-y-1.5">
                {timeline.patterns_detected.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="text-yellow-500 shrink-0">•</span>{p}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {timeline.chronic_risk_flags.length > 0 && (
            <div className="bg-orange-50 rounded-lg px-4 py-3 border border-orange-100">
              <p className="text-xs font-semibold text-orange-700 uppercase tracking-wider mb-2">Chronic Risk Flags</p>
              <ul className="space-y-1">
                {timeline.chronic_risk_flags.map((f, i) => (
                  <li key={i} className="text-sm text-orange-800">⚠️ {f}</li>
                ))}
              </ul>
            </div>
          )}

          <div
            className="rounded-lg px-4 py-3 border"
            style={{ background: '#F0FDF4', borderColor: '#BBF7D0' }}
          >
            <p className="text-xs font-semibold text-green-700 uppercase tracking-wider mb-1">Recommendation</p>
            <p className="text-sm text-green-900">{timeline.proactive_recommendation}</p>
          </div>
        </div>
      )}

      {/* Episode list */}
      {userId && !loading && episodes.length === 0 && !error && (
        <div className="text-center py-12 text-slate-400">
          <p className="text-4xl mb-3">📋</p>
          <p className="font-medium">No episodes found for this patient ID.</p>
          <p className="text-sm mt-1">Start by analyzing some symptoms.</p>
        </div>
      )}

      {episodes.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-widest">
              Episode History
            </h2>
            <span className="text-xs text-slate-400">{episodes.length} episodes</span>
          </div>
          {episodes.map((ep, i) => (
            <EpisodeRow key={ep.id || i} ep={ep} />
          ))}
        </div>
      )}
    </div>
  );
}
