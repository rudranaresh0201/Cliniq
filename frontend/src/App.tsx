import { useState } from 'react';
import Header from './components/Header';
import SymptomForm from './components/SymptomForm';
import TriageCard from './components/TriageCard';
import ConditionCard from './components/ConditionCard';
import ActionsList from './components/ActionsList';
import DrugSafety from './components/DrugSafety';
import RedFlags from './components/RedFlags';
import PatientSummary from './components/PatientSummary';
import Disclaimer from './components/Disclaimer';
import LoadingSpinner from './components/LoadingSpinner';
import StreamingProgress from './components/StreamingProgress';
import IndiaContext from './components/IndiaContext';
import Dashboard from './pages/Dashboard';
import Reports from './pages/Reports';
import { useAnalyze } from './hooks/useAnalyze';
import { useAnalyzeStream } from './hooks/useAnalyzeStream';
import type { AnalyzeResponse } from './types';

type Tab = 'analyze' | 'dashboard' | 'reports';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'analyze',   label: 'Analyze',   icon: '🔬' },
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'reports',   label: 'Lab Reports', icon: '📋' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('analyze');
  const [streamMode, setStreamMode] = useState(false);

  const plain  = useAnalyze();
  const stream = useAnalyzeStream();

  // Unified interface regardless of mode
  const loading = streamMode ? stream.loading  : plain.loading;
  const error   = streamMode ? stream.error    : plain.error;
  const result: AnalyzeResponse | null = streamMode ? stream.result : plain.result;

  const reset = () => {
    plain.reset();
    stream.reset();
  };

  // Legacy alias kept so SymptomForm onSubmit stays unchanged
  const { analyze } = plain;

  return (
    <div className="min-h-screen flex flex-col" style={{ fontFamily: 'Inter, sans-serif' }}>
      <Header />

      {/* Navigation tabs */}
      <nav className="bg-white border-b border-slate-100 shadow-sm">
        <div className="max-w-3xl mx-auto px-4">
          <div className="flex gap-1">
            {TABS.map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center gap-1.5 px-4 py-3.5 text-sm font-semibold transition-colors border-b-2 -mb-px"
                  style={{
                    borderColor: active ? '#4CAF50' : 'transparent',
                    color: active ? '#4CAF50' : '#64748b',
                  }}
                >
                  <span>{tab.icon}</span>
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      <main className="flex-1 bg-slate-50">
        {/* ── Analyze tab ── */}
        {activeTab === 'analyze' && (
          <div className="max-w-3xl mx-auto w-full px-4 py-10">
            {!loading && !result && (
              <div className="space-y-6">
                {/* Stream mode toggle */}
                <div className="flex justify-end">
                  <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                    <span className="text-xs font-semibold text-slate-500">Stream mode</span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={streamMode}
                      onClick={() => setStreamMode((v) => !v)}
                      className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none"
                      style={{ background: streamMode ? '#4CAF50' : '#cbd5e1' }}
                    >
                      <span
                        className="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                        style={{ transform: streamMode ? 'translateX(18px)' : 'translateX(2px)' }}
                      />
                    </button>
                  </label>
                </div>

                <SymptomForm
                  onSubmit={(req) => {
                    if (streamMode) {
                      stream.streamAnalyze({
                        query: req.query,
                        age: req.age,
                        gender: req.gender ?? undefined,
                        state: req.state,
                      });
                    } else {
                      analyze(req);
                    }
                  }}
                  loading={loading}
                />

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 flex items-start gap-3">
                    <span className="text-red-500 text-lg shrink-0">✕</span>
                    <div>
                      <p className="font-semibold text-red-800 text-sm">Something went wrong</p>
                      <p className="text-red-600 text-sm mt-0.5">{error}</p>
                      <p className="text-red-500 text-xs mt-1">
                        Make sure the backend is running at http://127.0.0.1:8000
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {loading && (
              streamMode
                ? <StreamingProgress
                    stage={stream.stage}
                    completedStages={stream.completedStages}
                    stageMessage={stream.stageMessage}
                  />
                : <LoadingSpinner />
            )}

            {result && !loading && (
              <div className="space-y-5">
                <button
                  onClick={reset}
                  className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors group"
                >
                  <svg
                    className="w-4 h-4 transition-transform group-hover:-translate-x-0.5"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                  New search
                </button>

                {result.error && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 text-sm text-yellow-800">
                    ⚠️ {result.error}
                  </div>
                )}

                {streamMode && (
                  <StreamingProgress
                    stage={stream.stage}
                    completedStages={stream.completedStages}
                    stageMessage={stream.stageMessage}
                  />
                )}

                <TriageCard
                  triage={result.triage}
                  message={result.triage_message}
                  cached={result.cached}
                />

                {result.india_context && (
                  <IndiaContext
                    season={result.india_context.season}
                    high_risk_diseases={result.india_context.high_risk_diseases}
                    regional_alerts={result.india_context.regional_alerts}
                    epidemiological_note={result.india_context.epidemiological_note}
                  />
                )}

                <PatientSummary summary={result.patient_summary} />

                {result.conditions && result.conditions.length > 0 && (
                  <div>
                    <h2 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">
                      Possible Conditions
                    </h2>
                    <div className="space-y-3">
                      {result.conditions.map((cond, i) => (
                        <ConditionCard key={i} condition={cond} index={i} />
                      ))}
                    </div>
                  </div>
                )}

                <ActionsList
                  immediateActions={result.immediate_actions || []}
                  recommendedTests={result.recommended_tests || []}
                />

                <RedFlags redFlags={result.red_flags || []} />

                <DrugSafety drugSafety={result.drug_safety} />

                {result.follow_up_questions && result.follow_up_questions.length > 0 && (
                  <div className="bg-white rounded-xl shadow-md border border-slate-100 p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-lg">💬</span>
                      <h3 className="font-bold text-slate-800">Follow-up Questions</h3>
                    </div>
                    <ul className="space-y-2">
                      {result.follow_up_questions.map((q, i) => (
                        <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                          <span className="text-slate-400 shrink-0">{i + 1}.</span>
                          {q}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <Disclaimer text={result.disclaimer} />
              </div>
            )}
          </div>
        )}

        {/* ── Dashboard tab ── */}
        {activeTab === 'dashboard' && <Dashboard />}

        {/* ── Reports tab ── */}
        {activeTab === 'reports' && <Reports />}
      </main>

      <footer className="py-6 text-center text-xs text-slate-400 border-t border-slate-100 bg-white">
        ClinIQ © {new Date().getFullYear()} — For informational purposes only
      </footer>
    </div>
  );
}
