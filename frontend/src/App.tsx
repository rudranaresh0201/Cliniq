import { useState, useEffect } from 'react';
import Lottie from 'lottie-react';
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

const STATS = [
  { value: '35M+', label: 'Medical Papers'    },
  { value: '10',   label: 'Indian Languages'  },
  { value: 'Live', label: 'PubMed Citations'  },
  { value: '< 5s', label: 'Response Time'     },
];

const FEATURES = [
  { icon: '🔬', label: 'PubMed Citations' },
  { icon: '🇮🇳', label: 'India-Aware'     },
  { icon: '⚡', label: 'Instant Analysis' },
  { icon: '📚', label: '35M+ Papers'      },
];

const MEDICAL_ANIMATION_URL = 'https://assets2.lottiefiles.com/packages/lf20_5njp3vgg.json';

const HEADLINES = [
  'Medical Intelligence You Can Trust',
  "India's Clinical AI Assistant",
  'Powered by 35M+ Medical Papers',
  'Built for 1.4 Billion Indians',
];

const SAMPLE_QUERIES = [
  { label: '🤒 Fever + Rash',     query: 'I have fever, body pain and rash for 3 days, Mumbai'        },
  { label: '💊 Drug Interaction', query: 'Can I take ibuprofen with warfarin?'                         },
  { label: '🧒 Child Fever',      query: 'My 6 year old child has fever and vomiting for 2 days'       },
  { label: '🫁 TB Symptoms',      query: 'Cough for 3 weeks, weight loss, night sweats, low grade fever'},
  { label: '🦟 Malaria Check',    query: 'Fever with chills every alternate day, body ache, West Bengal'},
];

function AnimatedBackground() {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 0, background: '#080B14', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: '20%', left: '10%', width: 400, height: 400, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(255,149,0,0.15) 0%, transparent 70%)',
        animation: 'floatUp 8s ease-in-out infinite',
      }} />
      <div style={{
        position: 'absolute', top: '60%', right: '10%', width: 300, height: 300, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(6,214,160,0.12) 0%, transparent 70%)',
        animation: 'floatUp 10s ease-in-out infinite reverse',
      }} />
      <div style={{
        position: 'absolute', top: '40%', left: '50%', width: 500, height: 500, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(124,58,237,0.08) 0%, transparent 70%)',
        animation: 'floatUp 12s ease-in-out infinite',
      }} />
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'linear-gradient(rgba(245,158,11,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(245,158,11,0.03) 1px, transparent 1px)',
        backgroundSize: '60px 60px',
      }} />
    </div>
  );
}

function HeroSection() {
  const [animationData, setAnimationData] = useState<any>(null);
  const [headlineIndex, setHeadlineIndex] = useState(0);
  const [displayed, setDisplayed]         = useState('');
  const [typing, setTyping]               = useState(true);

  useEffect(() => {
    fetch(MEDICAL_ANIMATION_URL)
      .then(r => r.json())
      .then(setAnimationData)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const full = HEADLINES[headlineIndex];
    if (typing) {
      if (displayed.length < full.length) {
        const t = setTimeout(() => setDisplayed(full.slice(0, displayed.length + 1)), 50);
        return () => clearTimeout(t);
      } else {
        const t = setTimeout(() => setTyping(false), 2000);
        return () => clearTimeout(t);
      }
    } else {
      if (displayed.length > 0) {
        const t = setTimeout(() => setDisplayed(displayed.slice(0, -1)), 30);
        return () => clearTimeout(t);
      } else {
        setHeadlineIndex((i) => (i + 1) % HEADLINES.length);
        setTyping(true);
      }
    }
  }, [displayed, typing, headlineIndex]);

  return (
    <div className="mb-10 animate-fade-in-up">
      <div className="flex items-center gap-8">
        {/* Left side */}
        <div className="flex-1 space-y-7">
          {/* Pill badge */}
          <div className="flex">
            <span
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold"
              style={{
                background: 'rgba(255,149,0,0.08)',
                border: '1px solid rgba(255,149,0,0.4)',
                color: '#FF9500',
                backdropFilter: 'blur(10px)',
                boxShadow: '0 0 20px rgba(255,149,0,0.2)',
              }}
            >
              🇮🇳 Built for India
            </span>
          </div>

          {/* Typing headline */}
          <div className="space-y-3">
            <h2
              style={{
                fontFamily: 'Sora, sans-serif',
                fontWeight: 800,
                fontSize: 'clamp(2rem, 5vw, 3.5rem)',
                lineHeight: 1.1,
                letterSpacing: '-0.02em',
                color: '#ffffff',
                margin: 0,
                minHeight: '1.2em',
              }}
            >
              {displayed}
              <span className="animate-pulse" style={{ color: '#FF9500' }}>|</span>
            </h2>
            <p style={{ color: '#94A3B8', fontSize: '1.125rem', fontWeight: 400 }}>
              AI-powered clinical reasoning for 1.4 billion Indians
            </p>
          </div>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-3">
            {FEATURES.map(({ icon, label }, i) => (
              <span
                key={label}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold animate-fade-in-up"
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,149,0,0.25)',
                  backdropFilter: 'blur(10px)',
                  color: '#ffffff',
                  animationDelay: `${i * 0.1 + 0.2}s`,
                  opacity: 0,
                }}
              >
                <span>{icon}</span>
                {label}
              </span>
            ))}
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-4 gap-3 max-w-xl">
            {STATS.map(({ value, label }, i) => (
              <div
                key={label}
                className="rounded-2xl p-4 text-center animate-fade-in-up"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  backdropFilter: 'blur(20px)',
                  animationDelay: `${0.3 + i * 0.08}s`,
                  opacity: 0,
                }}
              >
                <p style={{ fontFamily: 'Sora, sans-serif', fontWeight: 700, fontSize: '1.25rem', color: '#FF9500', margin: 0 }}>
                  {value}
                </p>
                <p style={{ fontSize: '0.7rem', color: '#94A3B8', fontWeight: 500, marginTop: '2px', lineHeight: 1.3 }}>
                  {label}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Right side: Lottie animation */}
        <div className="hidden md:flex items-center justify-center w-80">
          {animationData && (
            <Lottie animationData={animationData} loop={true} style={{ width: 300, height: 300 }} />
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab]     = useState<Tab>('analyze');
  const [streamMode, setStreamMode]   = useState(false);
  const [prefillQuery, setPrefillQuery] = useState('');

  const plain  = useAnalyze();
  const stream = useAnalyzeStream();

  const loading = streamMode ? stream.loading : plain.loading;
  const error   = streamMode ? stream.error   : plain.error;
  const result: AnalyzeResponse | null = streamMode ? stream.result : plain.result;

  const reset = () => { plain.reset(); stream.reset(); };
  const { analyze } = plain;

  return (
    <div className="min-h-screen flex flex-col relative" style={{ fontFamily: 'Sora, Inter, sans-serif' }}>
      <AnimatedBackground />
      <Header />

      {/* Tabs */}
      <nav
        className="relative z-10"
        style={{ background: '#080B14', borderBottom: '1px solid rgba(255,149,0,0.15)', backdropFilter: 'blur(20px)' }}
      >
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
                    borderColor: active ? '#FF9500' : 'transparent',
                    color: active ? '#FF9500' : '#94A3B8',
                    boxShadow: active ? '0 2px 16px rgba(255,149,0,0.25)' : 'none',
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      <main className="flex-1 relative z-10">
        {activeTab === 'analyze' && (
          <div className="max-w-3xl mx-auto w-full px-4 py-10">
            {!loading && !result && (
              <div className="space-y-6">
                <HeroSection />

                {/* Sample Queries */}
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                  {SAMPLE_QUERIES.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => setPrefillQuery(s.query)}
                      className="shrink-0 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors"
                      style={{
                        border: '1px solid rgba(255,149,0,0.3)',
                        color: '#FFD580',
                        background: 'transparent',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,149,0,0.1)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>

                {/* Stream mode toggle */}
                <div className="flex justify-end">
                  <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                    <span className="text-xs font-bold" style={{ color: 'rgba(255,255,255,0.4)' }}>Stream mode</span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={streamMode}
                      onClick={() => setStreamMode((v) => !v)}
                      className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none"
                      style={{ background: streamMode ? '#FF9500' : 'rgba(255,255,255,0.15)' }}
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
                  prefillQuery={prefillQuery}
                />

                {error && (
                  <div
                    className="rounded-xl px-5 py-4 flex items-start gap-3 animate-fade-in-up"
                    style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}
                  >
                    <span className="text-red-400 text-lg shrink-0">✕</span>
                    <div>
                      <p className="font-bold text-red-400 text-sm">Something went wrong</p>
                      <p className="text-red-300 text-sm mt-0.5">{error}</p>
                      <p className="text-xs mt-1" style={{ color: 'rgba(239,68,68,0.6)' }}>
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
                {/* New search + Share */}
                <div className="flex items-center gap-3 animate-fade-in-up">
                  <button
                    onClick={reset}
                    className="inline-flex items-center gap-2 text-sm font-semibold transition-colors group"
                    style={{ color: 'rgba(255,255,255,0.4)' }}
                  >
                    <svg className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                    </svg>
                    New search
                  </button>
                  <button
                    onClick={() => {
                      const text = `ClinIQ Analysis:\nTriage: ${result.triage}\nTop condition: ${result.conditions[0]?.name} (${result.conditions[0]?.confidence}%)\n\nGet your analysis: https://cliniq-opal.vercel.app`;
                      navigator.clipboard.writeText(text);
                      alert('Copied to clipboard!');
                    }}
                    className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold transition-colors"
                    style={{
                      border: '1px solid rgba(255,149,0,0.3)',
                      color: '#FFD580',
                      background: 'transparent',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,149,0,0.1)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    📤 Share Result
                  </button>
                </div>

                {result.error && (
                  <div
                    className="rounded-xl px-4 py-3 text-sm animate-fade-in-up"
                    style={{ background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.25)', color: '#fde68a' }}
                  >
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
                    <h2 className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'rgba(255,255,255,0.3)' }}>
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

                {result.dangerous_differentials && result.dangerous_differentials.length > 0 && (
                  <div className="animate-fade-in-up stagger-5">
                    <DangerousDifferentials differentials={result.dangerous_differentials} />
                  </div>
                )}

                <div className="animate-fade-in-up stagger-5">
                  <DrugSafety drugSafety={result.drug_safety} />
                </div>

                {result.follow_up_questions && result.follow_up_questions.length > 0 && (
                  <div
                    className="rounded-2xl p-5 animate-fade-in-up stagger-6"
                    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', backdropFilter: 'blur(20px)' }}
                  >
                    <h3 className="font-bold mb-3" style={{ color: '#f1f5f9' }}>Follow-up Questions</h3>
                    <ul className="space-y-2">
                      {result.follow_up_questions.map((q, i) => (
                        <li key={i} className="text-sm flex items-start gap-2" style={{ color: '#94a3b8' }}>
                          <span className="shrink-0 font-bold" style={{ color: 'rgba(255,255,255,0.2)' }}>{i + 1}.</span>
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

        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'reports' && <Reports />}
      </main>

      <footer className="py-8 relative z-10" style={{ borderTop: '1px solid rgba(255,255,255,0.05)', background: '#080B14' }}>
        <div className="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold" style={{ color: '#FF9500' }}>ClinIQ</span>
            <span className="text-sm" style={{ color: '#475569' }}>© 2026 — Medical Intelligence for India</span>
          </div>
          <div className="flex items-center gap-4 text-sm" style={{ color: '#475569' }}>
            <a href="https://github.com/rudranaresh0201/Cliniq" target="_blank" rel="noopener noreferrer"
              className="hover:text-white transition-colors">GitHub</a>
            <span>•</span>
            <span>Not a substitute for medical advice</span>
            <span>•</span>
            <a href="https://rudra201-cliniq-backend.hf.space/docs" target="_blank" rel="noopener noreferrer"
              className="hover:text-white transition-colors">API Docs</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
