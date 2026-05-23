import { useState, useRef, type FormEvent, type KeyboardEvent } from 'react';
import type { AnalyzeRequest } from '../types';

interface Props {
  onSubmit: (request: AnalyzeRequest) => void;
  loading: boolean;
}

const VOICE_LANGS = [
  { code: 'en-IN', label: 'EN' },
  { code: 'hi-IN', label: 'हिं' },
  { code: 'mr-IN', label: 'मर' },
  { code: 'ta-IN', label: 'தமி' },
  { code: 'te-IN', label: 'తెలు' },
  { code: 'bn-IN', label: 'বাং' },
];

export default function SymptomForm({ onSubmit, loading }: Props) {
  const [patientId, setPatientId]     = useState('');
  const [query, setQuery]             = useState('');
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
      {/* Premium card */}
      <div className="bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden">
        {/* Gradient top border */}
        <div className="h-1 w-full" style={{ background: 'linear-gradient(90deg,#16a34a,#0d9488,#2563eb)' }} />

        <form onSubmit={handleSubmit} className="p-7 space-y-5">
          <div className="mb-1">
            <h2 className="text-xl font-extrabold text-slate-800 tracking-tight">
              What's bothering you today?
            </h2>
            <p className="text-slate-400 text-sm mt-0.5">
              Describe your symptoms — ClinIQ will analyze them with PubMed-backed AI.
            </p>
          </div>

          {/* Patient ID */}
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
              Patient ID <span className="normal-case font-normal text-slate-400">(optional)</span>
            </label>
            <input
              type="text"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              placeholder="For longitudinal tracking"
              className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
            />
          </div>

          {/* Symptom textarea */}
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
              Symptoms <span className="text-red-400">*</span>
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
                      ? 'linear-gradient(135deg,#16a34a,#0d9488)'
                      : '#f1f5f9',
                    color: voiceLang === lang.code ? '#fff' : '#64748b',
                    border: voiceLang === lang.code ? '1.5px solid transparent' : '1.5px solid #e2e8f0',
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
                className={`w-full rounded-xl border-2 px-4 py-3 pr-14 text-slate-800 placeholder-slate-400 text-sm resize-none focus:outline-none transition-all duration-200 ${
                  shake
                    ? 'border-red-400 animate-pulse'
                    : isListening
                    ? 'border-green-400 shadow-[0_0_0_3px_rgba(22,163,74,0.15)]'
                    : 'border-slate-200 focus:border-green-400'
                }`}
                style={{ fontFamily: 'Inter, sans-serif' }}
              />
              <button
                type="button"
                onClick={isListening ? stopVoice : startVoice}
                title={isListening ? 'Click to stop' : 'Click to speak'}
                className="absolute bottom-3 right-3 w-9 h-9 rounded-full flex items-center justify-center transition-all"
                style={{
                  background: isListening ? '#fee2e2' : '#f1f5f9',
                  border: isListening ? '2px solid #16a34a' : '2px solid #e2e8f0',
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
                <span
                  className="w-2 h-2 rounded-full bg-green-500 animate-pulse-dot"
                />
                <span className="text-xs text-green-600 font-semibold">Listening…</span>
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
                    className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
                  />
                ),
              },
              {
                label: 'Gender',
                el: (
                  <select
                    value={gender} onChange={(e) => setGender(e.target.value)}
                    className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-700 text-sm focus:outline-none focus:border-green-400 transition-colors bg-white appearance-none"
                  >
                    <option value="">Select…</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                ),
              },
              {
                label: 'State',
                el: (
                  <select
                    value={state} onChange={(e) => setState(e.target.value)}
                    className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-700 text-sm focus:outline-none focus:border-green-400 transition-colors bg-white appearance-none"
                  >
                    <option>Maharashtra</option>
                    <option>Kerala</option>
                    <option>Delhi</option>
                    <option>West Bengal</option>
                    <option>Rajasthan</option>
                    <option>Tamil Nadu</option>
                    <option>Karnataka</option>
                    <option>Gujarat</option>
                    <option>Other</option>
                  </select>
                ),
              },
            ].map(({ label, el }) => (
              <div key={label}>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
                  {label}
                </label>
                {el}
              </div>
            ))}
          </div>

          {/* Medications */}
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
              Current Medications
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {medications.map((med, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
                  style={{ background: '#fef9e7', color: '#b8860b', border: '1px solid #f5c518' }}
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
              className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
            />
          </div>

          {/* Existing conditions */}
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
              Existing Conditions
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {conditions.map((cond, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
                  style={{ background: '#e8f5e9', color: '#2e7d32', border: '1px solid #4caf50' }}
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
              className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-4 rounded-xl text-white font-extrabold text-base transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed disabled:scale-100 shadow-lg hover:shadow-xl"
            style={{
              background: loading
                ? 'linear-gradient(135deg,#15803d,#0f766e)'
                : 'linear-gradient(135deg,#16a34a,#0d9488)',
              animation: loading ? 'pulse-dot 1.5s ease-in-out infinite' : 'none',
            }}
          >
            {loading ? 'Analyzing…' : 'Analyze Symptoms →'}
          </button>
        </form>
      </div>
    </div>
  );
}
