import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from 'react';
import type { AnalyzeRequest } from '../types';

interface Props {
  onSubmit: (request: AnalyzeRequest) => void;
  loading: boolean;
  prefillQuery?: string;
}

const VOICE_LANGS = [
  { code: 'en-IN', label: 'EN' },
  { code: 'hi-IN', label: 'हिं' },
  { code: 'mr-IN', label: 'मर' },
  { code: 'ta-IN', label: 'தமி' },
  { code: 'te-IN', label: 'తెలు' },
  { code: 'bn-IN', label: 'বাং' },
];

const GLASS_INPUT: React.CSSProperties = {
  width: '100%',
  borderRadius: '12px',
  border: '1px solid rgba(255,255,255,0.1)',
  background: 'rgba(255,255,255,0.05)',
  color: '#f1f5f9',
  padding: '10px 16px',
  fontSize: '0.875rem',
  outline: 'none',
  fontFamily: 'Sora, Inter, sans-serif',
  transition: 'border-color 0.2s, box-shadow 0.2s',
};

export default function SymptomForm({ onSubmit, loading, prefillQuery }: Props) {
  const [patientId, setPatientId]     = useState('');
  const [query, setQuery]             = useState('');

  useEffect(() => {
    if (prefillQuery) setQuery(prefillQuery);
  }, [prefillQuery]);
  const [age, setAge]                 = useState('');
  const [gender, setGender]           = useState('');
  const [state, setState]             = useState('Maharashtra');
  const [medications, setMedications] = useState<string[]>([]);
  const [medInput, setMedInput]       = useState('');
  const [conditions, setConditions]   = useState<string[]>([]);
  const [condInput, setCondInput]     = useState('');
  const [shake, setShake]             = useState(false);

  const [isListening, setIsListening] = useState(false);
  const [voiceLang, setVoiceLang]     = useState('en-IN');
  const recognitionRef                = useRef<any>(null);

  const startVoice = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Voice input not supported in this browser. Use Chrome.');
      return;
    }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SR();
    recognitionRef.current = recognition;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = voiceLang;
    recognition.onstart  = () => setIsListening(true);
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((r: any) => r[0].transcript)
        .join('');
      setQuery(transcript);
    };
    recognition.onend   = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.start();
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
  };

  const addTag = (value: string, list: string[], setList: (v: string[]) => void, setInput: (v: string) => void) => {
    const trimmed = value.trim();
    if (trimmed && !list.includes(trimmed)) setList([...list, trimmed]);
    setInput('');
  };

  const removeTag = (index: number, list: string[], setList: (v: string[]) => void) =>
    setList(list.filter((_, i) => i !== index));

  const handleTagKeyDown = (
    e: KeyboardEvent<HTMLInputElement>,
    value: string,
    list: string[],
    setList: (v: string[]) => void,
    setInput: (v: string) => void
  ) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(value, list, setList, setInput); }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) { setShake(true); setTimeout(() => setShake(false), 500); return; }
    onSubmit({
      query: query.trim(),
      age: age ? parseInt(age) : null,
      gender,
      medications,
      existing_conditions: conditions,
      patient_id: patientId.trim() || undefined,
      state,
    });
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          background: '#0F1623',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
        }}
      >
        {/* Gradient top border */}
        <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, #FF9500, #06D6A0, #7C3AED)' }} />

        <form onSubmit={handleSubmit} className="p-7 space-y-5">
          <div className="mb-1">
            <h2
              className="text-xl font-extrabold tracking-tight"
              style={{ color: '#f1f5f9', fontFamily: 'Sora, sans-serif' }}
            >
              What's bothering you today?
            </h2>
            <p className="text-sm mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
              Describe your symptoms — ClinIQ will analyze them with PubMed-backed AI.
            </p>
          </div>

          {/* Patient ID */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Patient ID <span className="normal-case font-normal" style={{ color: 'rgba(255,255,255,0.25)' }}>(optional)</span>
            </label>
            <input
              type="text"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              placeholder="For longitudinal tracking"
              style={GLASS_INPUT}
              onFocus={(e) => {
                e.target.style.borderColor = 'rgba(255,149,0,0.5)';
                e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'rgba(255,255,255,0.1)';
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Symptom textarea */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Symptoms <span style={{ color: '#f87171' }}>*</span>
            </label>

            {/* Language pills */}
            <div className="flex gap-1.5 mb-2 flex-wrap">
              {VOICE_LANGS.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => setVoiceLang(lang.code)}
                  className="px-2.5 py-1 rounded-full text-xs font-bold transition-all"
                  style={{
                    background: voiceLang === lang.code
                      ? 'linear-gradient(135deg,#FF9500,#FF6B00)'
                      : 'rgba(255,255,255,0.06)',
                    color: voiceLang === lang.code ? '#fff' : 'rgba(255,255,255,0.45)',
                    border: voiceLang === lang.code
                      ? '1px solid transparent'
                      : '1px solid rgba(255,255,255,0.1)',
                  }}
                >
                  {lang.label}
                </button>
              ))}
            </div>

            <div className="relative">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Severe headache for 2 days, fever 102°F, neck stiffness, sensitivity to light..."
                rows={5}
                style={{
                  ...GLASS_INPUT,
                  padding: '12px 56px 12px 16px',
                  resize: 'none',
                  borderColor: shake
                    ? 'rgba(239,68,68,0.6)'
                    : isListening
                    ? 'rgba(255,149,0,0.6)'
                    : 'rgba(255,255,255,0.1)',
                  boxShadow: isListening ? '0 0 0 3px rgba(255,149,0,0.1)' : 'none',
                }}
                onFocus={(e) => {
                  if (!shake && !isListening) {
                    e.target.style.borderColor = 'rgba(255,149,0,0.5)';
                    e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
                  }
                }}
                onBlur={(e) => {
                  if (!isListening) {
                    e.target.style.borderColor = 'rgba(255,255,255,0.1)';
                    e.target.style.boxShadow = 'none';
                  }
                }}
              />
              <button
                type="button"
                onClick={isListening ? stopVoice : startVoice}
                title={isListening ? 'Click to stop' : 'Click to speak'}
                className="absolute bottom-3 right-3 w-9 h-9 rounded-full flex items-center justify-center transition-all"
                style={{
                  background: isListening ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.08)',
                  border: isListening ? '1.5px solid rgba(255,149,0,0.5)' : '1.5px solid rgba(255,255,255,0.12)',
                }}
              >
                {isListening ? (
                  <span
                    className="w-3.5 h-3.5 rounded-full bg-red-500"
                    style={{ animation: 'pulse-dot 1s ease-in-out infinite' }}
                  />
                ) : (
                  <span className="text-base leading-none">🎤</span>
                )}
              </button>
            </div>

            {isListening && (
              <div className="flex items-center gap-2 mt-1.5">
                <span className="w-2 h-2 rounded-full animate-pulse-dot" style={{ background: '#FF9500' }} />
                <span className="text-xs font-semibold" style={{ color: '#FF9500' }}>Listening…</span>
              </div>
            )}
          </div>

          {/* Age / Gender / State */}
          <div className="grid grid-cols-3 gap-4">
            {[
              {
                label: 'Age',
                el: (
                  <input
                    type="number" value={age}
                    onChange={(e) => setAge(e.target.value)}
                    placeholder="e.g. 34" min={1} max={120}
                    style={GLASS_INPUT}
                    onFocus={(e) => {
                      e.target.style.borderColor = 'rgba(255,149,0,0.5)';
                      e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = 'rgba(255,255,255,0.1)';
                      e.target.style.boxShadow = 'none';
                    }}
                  />
                ),
              },
              {
                label: 'Gender',
                el: (
                  <select
                    value={gender} onChange={(e) => setGender(e.target.value)}
                    style={{ ...GLASS_INPUT, appearance: 'none' as const, WebkitAppearance: 'none' as const }}
                    onFocus={(e) => {
                      e.target.style.borderColor = 'rgba(255,149,0,0.5)';
                      e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = 'rgba(255,255,255,0.1)';
                      e.target.style.boxShadow = 'none';
                    }}
                  >
                    <option value="" style={{ background: '#0F1623' }}>Select…</option>
                    <option value="male" style={{ background: '#0F1623' }}>Male</option>
                    <option value="female" style={{ background: '#0F1623' }}>Female</option>
                    <option value="other" style={{ background: '#0F1623' }}>Other</option>
                  </select>
                ),
              },
              {
                label: 'State',
                el: (
                  <select
                    value={state} onChange={(e) => setState(e.target.value)}
                    style={{ ...GLASS_INPUT, appearance: 'none' as const, WebkitAppearance: 'none' as const }}
                    onFocus={(e) => {
                      e.target.style.borderColor = 'rgba(255,149,0,0.5)';
                      e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = 'rgba(255,255,255,0.1)';
                      e.target.style.boxShadow = 'none';
                    }}
                  >
                    <option style={{ background: '#0F1623' }}>Maharashtra</option>
                    <option style={{ background: '#0F1623' }}>Kerala</option>
                    <option style={{ background: '#0F1623' }}>Delhi</option>
                    <option style={{ background: '#0F1623' }}>West Bengal</option>
                    <option style={{ background: '#0F1623' }}>Rajasthan</option>
                    <option style={{ background: '#0F1623' }}>Tamil Nadu</option>
                    <option style={{ background: '#0F1623' }}>Karnataka</option>
                    <option style={{ background: '#0F1623' }}>Gujarat</option>
                    <option style={{ background: '#0F1623' }}>Other</option>
                  </select>
                ),
              },
            ].map(({ label, el }) => (
              <div key={label}>
                <label className="block text-xs font-bold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
                  {label}
                </label>
                {el}
              </div>
            ))}
          </div>

          {/* Medications */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Current Medications
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {medications.map((med, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
                  style={{
                    background: 'rgba(255,149,0,0.12)',
                    color: '#FFD580',
                    border: '1px solid rgba(255,149,0,0.25)',
                  }}
                >
                  {med}
                  <button type="button" onClick={() => removeTag(i, medications, setMedications)} className="hover:opacity-70 ml-0.5">×</button>
                </span>
              ))}
            </div>
            <input
              type="text" value={medInput}
              onChange={(e) => setMedInput(e.target.value)}
              onKeyDown={(e) => handleTagKeyDown(e, medInput, medications, setMedications, setMedInput)}
              onBlur={() => addTag(medInput, medications, setMedications, setMedInput)}
              placeholder="Type medication and press Enter…"
              style={GLASS_INPUT}
              onFocus={(e) => {
                e.target.style.borderColor = 'rgba(255,149,0,0.5)';
                e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
              }}
            />
          </div>

          {/* Existing conditions */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Existing Conditions
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {conditions.map((cond, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
                  style={{
                    background: 'rgba(6,214,160,0.12)',
                    color: '#6ee7b7',
                    border: '1px solid rgba(6,214,160,0.25)',
                  }}
                >
                  {cond}
                  <button type="button" onClick={() => removeTag(i, conditions, setConditions)} className="hover:opacity-70 ml-0.5">×</button>
                </span>
              ))}
            </div>
            <input
              type="text" value={condInput}
              onChange={(e) => setCondInput(e.target.value)}
              onKeyDown={(e) => handleTagKeyDown(e, condInput, conditions, setConditions, setCondInput)}
              onBlur={() => addTag(condInput, conditions, setConditions, setCondInput)}
              placeholder="e.g. diabetes, hypertension…"
              style={GLASS_INPUT}
              onFocus={(e) => {
                e.target.style.borderColor = 'rgba(255,149,0,0.5)';
                e.target.style.boxShadow = '0 0 0 3px rgba(255,149,0,0.1)';
              }}
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-4 rounded-xl text-white font-extrabold text-base transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed disabled:scale-100"
            style={{
              background: 'linear-gradient(135deg, #FF9500, #FF6B00)',
              boxShadow: loading ? 'none' : '0 0 30px rgba(255,149,0,0.35)',
              animation: loading ? 'pulse-dot 1.5s ease-in-out infinite' : 'none',
              fontFamily: 'Sora, sans-serif',
            }}
            onMouseEnter={(e) => {
              if (!loading) (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 50px rgba(255,149,0,0.55)';
            }}
            onMouseLeave={(e) => {
              if (!loading) (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 30px rgba(255,149,0,0.35)';
            }}
          >
            {loading ? 'Analyzing…' : 'Analyze Symptoms →'}
          </button>
        </form>
      </div>
    </div>
  );
}
