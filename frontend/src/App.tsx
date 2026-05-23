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
import DangerousDifferentials from './components/DangerousDifferentials';
import Dashboard from './pages/Dashboard';
import Reports from './pages/Reports';
import { useAnalyze } from './hooks/useAnalyze';
import { useAnalyzeStream } from './hooks/useAnalyzeStream';
import type { AnalyzeResponse } from './types';

type Tab = 'analyze' | 'dashboard' | 'reports';

const TABS: { id: Tab; label: string }[] = [
  { id: 'analyze',   label: 'Analyze'     },
  { id: 'dashboard', label: 'Dashboard'   },
  { id: 'reports',   label: 'Lab Reports' },
];

const FLOAT_ICONS = [
  { icon: '+', top: '10%', left: '5%',  delay: '0s',   size: 28 },
  { icon: '+', top: '20%', left: '90%', delay: '1.2s', size: 22 },
  { icon: '+', top: '55%', left: '3%',  delay: '0.6s', size: 20 },
  { icon: '+', top: '70%', left: '92%', delay: '2s',   size: 18 },
  { icon: '+', top: '80%', left: '8%',  delay: '1.5s', size: 24 },
  { icon: '+', top: '40%', left: '95%', delay: '0.3s', size: 18 },
  { icon: '+', top: '90%', left: '50%', delay: '2.5s', size: 20 },
];

const STATS = [
  { value: '35M+',   label: 'Medical Papers' },
  { value: '10',     label: 'Indian Languages' },
  { value: 'Live',   label: 'PubMed Citations' },
  { value: '< 5s',   label: 'Response Time' },
];

function FloatingBackground() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 0 }}>
      {FLOAT_ICONS.map((item, i) => (
        <span
          key={i}
          className="absolute select-none animate-float"
          style={{
            top: item.top,
            left: item.left,
            fontSize: item.size,
            opacity: 0.03,
            animationDelay: item.delay,
            animationDuration: `${4 + i * 0.7}s`,
          }}
        >
          {item.icon}
        </span>
      ))}
    </div>
  );
}

function HeroSection() {
  return (
    <div className="text-center mb-10 space-y-6 animate-fade-in-up">
      {/* Headline */}
      <div>
        <h2
          className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight"
          style={{
            background: 'linear-gradient(135deg,#0f172a 0%,#16a34a 60%,#0d9488 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          Medical answers<br />you can trust
        </h2>
        <p className="text-slate-500 text-lg mt-3 font-medium">
          India's first AI that thinks like a clinician
        </p>
      </div>

      {/* Feature pills */}
      <div className="flex flex-wrap justify-center gap-3">
        {[
          { icon: '🇮🇳', label: 'India-Aware',      delay: '0.1s' },
          { icon: null,   label: 'PubMed Citations', delay: '0.2s' },
          { icon: null,   label: 'Instant Analysis', delay: '0.3s' },
        ].map(({ icon, label, delay }) => (
          <span
            key={label}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold animate-float"
            style={{
              background: 'white',
              border: '1.5px solid #e2e8f0',
              color: '#334155',
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
              animationDelay: delay,
              animationDuration: '3.5s',
            }}
          >
            {icon && <span>{icon}</span>}
            {label}
          </span>
        ))}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 max-w-xl mx-auto">
        {STATS.map(({ value, label }, i) => (
          <div
            key={label}
            className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100 animate-fade-in-up"
            style={{ animationDelay: `${0.15 + i * 0.1}s` }}
          >
            <p
              className="text-xl font-extrabold"
              style={{
                background: 'linear-gradient(135deg,#16a34a,#0d9488)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              {value}
            </p>
            <p className="text-xs text-slate-400 font-medium mt-0.5 leading-tight">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('analyze');
  const [streamMode, setStreamMode] = useState(false);

  const plain  = useAnalyze();
  const stream = useAnalyzeStream();

  const loading = streamMode ? stream.loading  : plain.loading;
  const error   = streamMode ? stream.error    : plain.error;
  const result: AnalyzeResponse | null = streamMode ? stream.result : plain.result;

  const reset = () => { plain.reset(); stream.reset(); };
  const { analyze } = plain;

  return (
    <div className="min-h-screen flex flex-col relative" style={{ fontFamily: 'Inter, sans-serif' }}>
      <FloatingBackground />
      <Header />

      {/* Tabs */}
      <nav className="bg-white border-b border-slate-100 shadow-sm relative z-10">
        <div className="max-w-3xl mx-auto px-4">
          <div className="flex gap-1">
            {TABS.map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center px-4 py-3.5 text-sm font-bold transition-all border-b-2 -mb-px"
                  style={{
                    borderColor: active ? '#16a34a' : 'transparent',
                    color: active ? '#16a34a' : '#64748b',
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      <main className="flex-1 bg-slate-50 relative z-10">
        {/* ── Analyze tab ── */}
        {activeTab === 'analyze' && (
          <div className="max-w-3xl mx-auto w-full px-4 py-10">
            {!loading && !result && (
              <div className="space-y-6">
                <HeroSection />

                {/* Stream mode toggle */}
                <div className="flex justify-end">
                  <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                    <span className="text-xs font-bold text-slate-500">Stream mode</span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={streamMode}
                      onClick={() => setStreamMode((v) => !v)}
                      className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none"
                      style={{ background: streamMode ? '#16a34a' : '#cbd5e1' }}
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
                  <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 flex items-start gap-3 animate-fade-in-up">
                    <span className="text-red-500 text-lg shrink-0">✕</span>
                    <div>
                      <p className="font-bold text-red-800 text-sm">Something went wrong</p>
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
                  className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-900 transition-colors group animate-fade-in-up"
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
                  <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 text-sm text-yellow-800 animate-fade-in-up">
                    {result.error}
                  </div>
                )}

                {streamMode && (
                  <StreamingProgress
                    stage={stream.stage}
                    completedStages={stream.completedStages}
                    stageMessage={stream.stageMessage}
                  />
                )}

                <div className="animate-fade-in-up stagger-1">
                  <TriageCard
                    triage={result.triage}
                    message={result.triage_message}
                    cached={result.cached}
                  />
                </div>

                {result.india_context && (
                  <div className="animate-fade-in-up stagger-2">
                    <IndiaContext
                      season={result.india_context.season}
                      high_risk_diseases={result.india_context.high_risk_diseases}
                      regional_alerts={result.india_context.regional_alerts}
                      epidemiological_note={result.india_context.epidemiological_note}
                    />
                  </div>
                )}

                <div className="animate-fade-in-up stagger-2">
                  <PatientSummary summary={result.patient_summary} />
                </div>

                {result.conditions && result.conditions.length > 0 && (
                  <div className="animate-fade-in-up stagger-3">
                    <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
                      Possible Conditions
                    </h2>
                    <div className="space-y-3">
                      {result.conditions.map((cond, i) => (
                        <ConditionCard key={i} condition={cond} index={i} />
                      ))}
                    </div>
                  </div>
                )}

                <div className="animate-fade-in-up stagger-4">
                  <ActionsList
                    immediateActions={result.immediate_actions || []}
                    recommendedTests={result.recommended_tests || []}
                  />
                </div>

                <div className="animate-fade-in-up stagger-4">
                  <RedFlags redFlags={result.red_flags || []} />
                </div>

                {result.dangerous_differentials &&
                  result.dangerous_differentials.length > 0 && (
                    <div className="animate-fade-in-up stagger-5">
                      <DangerousDifferentials
                        differentials={result.dangerous_differentials}
                      />
                    </div>
                  )}

                <div className="animate-fade-in-up stagger-5">
                  <DrugSafety drugSafety={result.drug_safety} />
                </div>

                {result.follow_up_questions && result.follow_up_questions.length > 0 && (
                  <div className="bg-white rounded-2xl shadow-md border border-slate-100 p-5 animate-fade-in-up stagger-6">
                    <div className="flex items-center gap-2 mb-3">
                      <h3 className="font-bold text-slate-800">Follow-up Questions</h3>
                    </div>
                    <ul className="space-y-2">
                      {result.follow_up_questions.map((q, i) => (
                        <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                          <span className="text-slate-300 shrink-0 font-bold">{i + 1}.</span>
                          {q}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="animate-fade-in-up stagger-6">
                  <Disclaimer text={result.disclaimer} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Dashboard tab ── */}
        {activeTab === 'dashboard' && <Dashboard />}

        {/* ── Reports tab ── */}
        {activeTab === 'reports' && <Reports />}
      </main>

      <footer className="py-6 text-center text-xs text-slate-400 border-t border-slate-100 bg-white relative z-10">
        ClinIQ © {new Date().getFullYear()} — For informational purposes only. Not a substitute for professional medical advice.
      </footer>
    </div>
  );
}
