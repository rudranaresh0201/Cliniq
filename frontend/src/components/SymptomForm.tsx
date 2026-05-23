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
  const [patientId, setPatientId] = useState('');
  const [query, setQuery] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('');
  const [state, setState] = useState('Maharashtra');
  const [medications, setMedications] = useState<string[]>([]);
  const [medInput, setMedInput] = useState('');
  const [conditions, setConditions] = useState<string[]>([]);
  const [condInput, setCondInput] = useState('');
  const [shake, setShake] = useState(false);

  const [isListening, setIsListening] = useState(false);
  const [voiceLang, setVoiceLang] = useState('en-IN');
  const recognitionRef = useRef<any>(null);

  const startVoice = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Voice input not supported in this browser. Use Chrome.');
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = voiceLang;

    recognition.onstart = () => setIsListening(true);

    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((result: any) => result[0].transcript)
        .join('');
      setQuery(transcript);
    };

    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);

    recognition.start();
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
  };

  const addTag = (
    value: string,
    list: string[],
    setList: (v: string[]) => void,
    setInput: (v: string) => void
  ) => {
    const trimmed = value.trim();
    if (trimmed && !list.includes(trimmed)) {
      setList([...list, trimmed]);
    }
    setInput('');
  };

  const removeTag = (index: number, list: string[], setList: (v: string[]) => void) => {
    setList(list.filter((_, i) => i !== index));
  };

  const handleTagKeyDown = (
    e: KeyboardEvent<HTMLInputElement>,
    value: string,
    list: string[],
    setList: (v: string[]) => void,
    setInput: (v: string) => void
  ) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(value, list, setList, setInput);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) {
      setShake(true);
      setTimeout(() => setShake(false), 500);
      return;
    }
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
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-slate-800 mb-2">What's bothering you?</h2>
        <p className="text-slate-500 text-base">Describe your symptoms in plain language — ClinIQ will analyze them for you.</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg border border-slate-100 p-6 space-y-5">
        {/* Patient ID */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">
            Patient ID <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            placeholder="Enter patient ID for longitudinal tracking"
            className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
          />
          <p className="mt-1.5 text-xs text-slate-400">
            Using a patient ID enables timeline memory and longitudinal health tracking.
          </p>
        </div>

        {/* Symptom textarea */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">
            Describe your symptoms <span className="text-red-400">*</span>
          </label>

          {/* Language selector pills */}
          <div className="flex gap-1.5 mb-2 flex-wrap">
            {VOICE_LANGS.map((lang) => (
              <button
                key={lang.code}
                type="button"
                onClick={() => setVoiceLang(lang.code)}
                className="px-2.5 py-1 rounded-full text-xs font-semibold transition-all"
                style={{
                  background: voiceLang === lang.code ? '#4CAF50' : '#F1F5F9',
                  color: voiceLang === lang.code ? '#fff' : '#64748b',
                  border: voiceLang === lang.code ? '1.5px solid #4CAF50' : '1.5px solid #e2e8f0',
                }}
              >
                {lang.label}
              </button>
            ))}
          </div>

          {/* Textarea + mic button */}
          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. I've had a severe headache for 2 days, some fever, and my neck feels stiff..."
              rows={4}
              className={`w-full rounded-xl border-2 px-4 py-3 pr-14 text-slate-800 placeholder-slate-400 text-sm resize-none focus:outline-none transition-all duration-200 ${
                shake ? 'border-red-400 animate-pulse' : isListening ? 'border-green-400' : 'border-slate-200 focus:border-green-400'
              }`}
              style={{ fontFamily: 'Inter, sans-serif' }}
            />
            <button
              type="button"
              onClick={isListening ? stopVoice : startVoice}
              title={isListening ? 'Click to stop' : 'Click to speak'}
              className="absolute bottom-3 right-3 w-9 h-9 rounded-full flex items-center justify-center transition-all"
              style={{
                background: isListening ? '#FEF2F2' : '#F1F5F9',
                border: isListening ? '2px solid #4CAF50' : '2px solid #e2e8f0',
              }}
            >
              {isListening ? (
                <span
                  className="w-4 h-4 rounded-full bg-red-500"
                  style={{ animation: 'pulse 1s ease-in-out infinite' }}
                />
              ) : (
                <span className="text-base leading-none">🎤</span>
              )}
            </button>
          </div>

          {/* Listening status */}
          {isListening && (
            <div className="flex items-center gap-2 mt-1.5">
              <span
                className="w-2 h-2 rounded-full bg-green-500"
                style={{ animation: 'pulse 1s ease-in-out infinite' }}
              />
              <span className="text-xs text-green-600 font-medium">Listening...</span>
            </div>
          )}
        </div>

        {/* Age, Gender, State row */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Age</label>
            <input
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="e.g. 34"
              min={1}
              max={120}
              className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Gender</label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-700 text-sm focus:outline-none focus:border-green-400 transition-colors bg-white appearance-none"
            >
              <option value="">Select...</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Your State</label>
            <select
              value={state}
              onChange={(e) => setState(e.target.value)}
              className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-700 text-sm focus:outline-none focus:border-green-400 transition-colors bg-white appearance-none"
            >
              <option value="Maharashtra">Maharashtra</option>
              <option value="Kerala">Kerala</option>
              <option value="Delhi">Delhi</option>
              <option value="West Bengal">West Bengal</option>
              <option value="Rajasthan">Rajasthan</option>
              <option value="Tamil Nadu">Tamil Nadu</option>
              <option value="Karnataka">Karnataka</option>
              <option value="Gujarat">Gujarat</option>
              <option value="Other">Other</option>
            </select>
          </div>
        </div>

        {/* Medications tags */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">Current medications</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {medications.map((med, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium"
                style={{ background: '#FEF9E7', color: '#B8860B', border: '1px solid #F5C518' }}
              >
                {med}
                <button
                  type="button"
                  onClick={() => removeTag(i, medications, setMedications)}
                  className="hover:opacity-70 transition-opacity ml-0.5"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <input
            type="text"
            value={medInput}
            onChange={(e) => setMedInput(e.target.value)}
            onKeyDown={(e) => handleTagKeyDown(e, medInput, medications, setMedications, setMedInput)}
            onBlur={() => addTag(medInput, medications, setMedications, setMedInput)}
            placeholder="Type medication and press Enter..."
            className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
          />
        </div>

        {/* Existing conditions tags */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">Existing conditions</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {conditions.map((cond, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium"
                style={{ background: '#E8F5E9', color: '#2E7D32', border: '1px solid #4CAF50' }}
              >
                {cond}
                <button
                  type="button"
                  onClick={() => removeTag(i, conditions, setConditions)}
                  className="hover:opacity-70 transition-opacity ml-0.5"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <input
            type="text"
            value={condInput}
            onChange={(e) => setCondInput(e.target.value)}
            onKeyDown={(e) => handleTagKeyDown(e, condInput, conditions, setConditions, setCondInput)}
            onBlur={() => addTag(condInput, conditions, setConditions, setCondInput)}
            placeholder="e.g. diabetes, hypertension..."
            className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:border-green-400 transition-colors"
          />
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3.5 rounded-xl text-slate-900 font-bold text-base transition-all duration-200 active:scale-98 disabled:opacity-60 disabled:cursor-not-allowed shadow-md hover:shadow-lg"
          style={{ background: loading ? '#e5b510' : '#F5C518' }}
        >
          {loading ? 'Analyzing...' : 'Analyze Symptoms'}
        </button>
      </form>
    </div>
  );
}
