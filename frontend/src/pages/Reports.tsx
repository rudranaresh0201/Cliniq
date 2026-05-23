import React, { useState, useRef, type DragEvent, type ChangeEvent } from 'react';

interface ParsedValue {
  value: number;
  unit: string;
  normal_low: number;
  normal_high: number;
  flag: 'NORMAL' | 'HIGH' | 'LOW' | 'CRITICAL_HIGH' | 'CRITICAL_LOW';
}

interface AbnormalExplanation {
  test: string;
  value: string;
  flag: string;
  meaning: string;
  possible_causes: string[];
  action: string;
}

interface Medicine {
  name: string;
  purpose: string;
  how_to_take: string;
  side_effects: string[];
  duration: string;
}

interface ParsedReport {
  report_type: string;
  values: Record<string, ParsedValue>;
  abnormal_count: number;
  critical_count: number;
  abnormal_values: Record<string, ParsedValue>;
  is_imaging_report: boolean;
  is_prescription: boolean;
}

interface ReportInterpretation {
  interpretation: string;
  overall_urgency: string;
  recommended_followup: string;
  abnormal_explanations?: AbnormalExplanation[];
  findings?: string[];
  what_it_means?: string;
  questions_to_ask?: string[];
  medicines?: Medicine[];
  important_warnings?: string[];
  error?: string;
}

interface ReportResult {
  filename: string;
  content_type: string;
  parsed: ParsedReport;
  interpretation: ReportInterpretation;
}

// ---------------------------------------------------------------------------
// Style maps — dark palette
// ---------------------------------------------------------------------------

const FLAG_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  NORMAL:        { bg: 'rgba(6,214,160,0.12)',   text: '#6ee7b7', label: 'Normal'     },
  HIGH:          { bg: 'rgba(255,149,0,0.12)',    text: '#FFD580', label: 'High'       },
  LOW:           { bg: 'rgba(99,102,241,0.12)',   text: '#a5b4fc', label: 'Low'        },
  CRITICAL_HIGH: { bg: 'rgba(239,68,68,0.15)',    text: '#fca5a5', label: 'Critical ↑' },
  CRITICAL_LOW:  { bg: 'rgba(239,68,68,0.15)',    text: '#fca5a5', label: 'Critical ↓' },
};

const URGENCY_STYLE: Record<string, { bg: string; text: string }> = {
  routine:   { bg: 'rgba(6,214,160,0.12)',  text: '#6ee7b7' },
  urgent:    { bg: 'rgba(255,149,0,0.12)',  text: '#FFD580' },
  immediate: { bg: 'rgba(239,68,68,0.12)', text: '#fca5a5' },
};

const REPORT_TYPE_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  cbc:             { label: 'CBC Report',      bg: 'rgba(6,214,160,0.12)',  text: '#6ee7b7' },
  lft:             { label: 'LFT Report',      bg: 'rgba(99,102,241,0.12)', text: '#a5b4fc' },
  kft:             { label: 'KFT Report',      bg: 'rgba(99,102,241,0.12)', text: '#a5b4fc' },
  lipid:           { label: 'Lipid Profile',   bg: 'rgba(99,102,241,0.12)', text: '#a5b4fc' },
  diabetes:        { label: 'Diabetes Report', bg: 'rgba(255,149,0,0.12)',  text: '#FFD580' },
  thyroid:         { label: 'Thyroid Report',  bg: 'rgba(99,102,241,0.12)', text: '#a5b4fc' },
  xray_report:     { label: 'X-Ray Report',    bg: 'rgba(124,58,237,0.12)', text: '#c4b5fd' },
  mri_report:      { label: 'MRI Report',      bg: 'rgba(124,58,237,0.12)', text: '#c4b5fd' },
  ct_report:       { label: 'CT Scan Report',  bg: 'rgba(124,58,237,0.12)', text: '#c4b5fd' },
  ecg_report:      { label: 'ECG Report',      bg: 'rgba(124,58,237,0.12)', text: '#c4b5fd' },
  urine:           { label: 'Urine Report',    bg: 'rgba(6,214,160,0.12)',  text: '#6ee7b7' },
  prescription:    { label: 'Prescription',    bg: 'rgba(255,149,0,0.12)',  text: '#FFD580' },
  general_medical: { label: 'Medical Report',  bg: 'rgba(255,255,255,0.06)', text: '#94A3B8' },
  unknown:         { label: 'Unknown',         bg: 'rgba(255,255,255,0.06)', text: '#94A3B8' },
};

const CARD: React.CSSProperties = {
  background: '#0F1623',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '16px',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ReportTypeBadge({ reportType }: { reportType: string }) {
  const cfg = REPORT_TYPE_BADGE[reportType] ?? REPORT_TYPE_BADGE.unknown;
  return (
    <span
      className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide"
      style={{ background: cfg.bg, color: cfg.text }}
    >
      {cfg.label}
    </span>
  );
}

function ImagingSection({ interpretation }: { interpretation: ReportInterpretation }) {
  return (
    <div className="space-y-4">
      {interpretation.findings && interpretation.findings.length > 0 && (
        <div style={CARD} className="p-5">
          <h3 className="font-bold mb-3" style={{ color: '#f1f5f9' }}>Findings Summary</h3>
          <ul className="space-y-2">
            {interpretation.findings.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>
                <span style={{ color: '#FF9500' }} className="shrink-0 mt-0.5">•</span>
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {interpretation.what_it_means && (
        <div style={CARD} className="p-5">
          <h3 className="font-bold mb-2" style={{ color: '#f1f5f9' }}>What This Means For You</h3>
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.65)' }}>{interpretation.what_it_means}</p>
        </div>
      )}

      {interpretation.questions_to_ask && interpretation.questions_to_ask.length > 0 && (
        <div style={CARD} className="p-5">
          <h3 className="font-bold mb-3" style={{ color: '#f1f5f9' }}>Questions To Ask Your Doctor</h3>
          <ol className="space-y-2">
            {interpretation.questions_to_ask.map((q, i) => (
              <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>
                <span className="shrink-0 font-semibold" style={{ color: 'rgba(255,255,255,0.3)' }}>{i + 1}.</span>
                {q}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function PrescriptionSection({ interpretation }: { interpretation: ReportInterpretation }) {
  return (
    <div className="space-y-4">
      {interpretation.important_warnings && interpretation.important_warnings.length > 0 && (
        <div
          className="rounded-xl p-4"
          style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)' }}
        >
          <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: '#fca5a5' }}>
            Important Warnings
          </p>
          <ul className="space-y-1">
            {interpretation.important_warnings.map((w, i) => (
              <li key={i} className="text-sm flex items-start gap-2" style={{ color: 'rgba(252,165,165,0.85)' }}>
                <span className="shrink-0">⚠️</span>
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {interpretation.medicines && interpretation.medicines.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Your Medicines
          </h3>
          {interpretation.medicines.map((med, i) => (
            <div key={i} style={CARD} className="p-5">
              <div className="flex items-start justify-between gap-3 mb-3">
                <h4 className="font-bold" style={{ color: '#f1f5f9' }}>{med.name}</h4>
                {med.duration && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full shrink-0"
                    style={{ background: 'rgba(255,255,255,0.06)', color: '#94A3B8' }}
                  >
                    {med.duration}
                  </span>
                )}
              </div>
              <p className="text-sm mb-2" style={{ color: 'rgba(255,255,255,0.6)' }}>
                <span className="font-semibold" style={{ color: 'rgba(255,255,255,0.8)' }}>Purpose: </span>{med.purpose}
              </p>
              <p className="text-sm mb-3" style={{ color: 'rgba(255,255,255,0.6)' }}>
                <span className="font-semibold" style={{ color: 'rgba(255,255,255,0.8)' }}>How to take: </span>{med.how_to_take}
              </p>
              {med.side_effects && med.side_effects.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                    Watch for
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {med.side_effects.map((s, j) => (
                      <span
                        key={j}
                        className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: 'rgba(255,149,0,0.1)', color: '#FFD580', border: '1px solid rgba(255,149,0,0.2)' }}
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LabSection({ parsed, interpretation }: { parsed: ParsedReport; interpretation: ReportInterpretation }) {
  return (
    <div className="space-y-4">
      {Object.keys(parsed.values).length > 0 && (
        <div style={{ ...CARD, overflow: 'hidden' }}>
          <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <h3 className="font-bold" style={{ color: '#f1f5f9' }}>Parsed Values</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-xs font-semibold uppercase tracking-wider"
                  style={{ background: 'rgba(255,255,255,0.03)', color: 'rgba(255,255,255,0.4)' }}
                >
                  <th className="text-left px-5 py-3">Test</th>
                  <th className="text-right px-5 py-3">Result</th>
                  <th className="text-right px-5 py-3">Normal Range</th>
                  <th className="text-center px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                {Object.entries(parsed.values).map(([name, val], idx) => {
                  const style = FLAG_STYLE[val.flag] ?? FLAG_STYLE.NORMAL;
                  return (
                    <tr
                      key={name}
                      style={{
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                        borderTop: '1px solid rgba(255,255,255,0.04)',
                      }}
                    >
                      <td className="px-5 py-3 font-medium uppercase" style={{ color: '#e2e8f0' }}>{name.replace(/_/g, ' ')}</td>
                      <td className="px-5 py-3 text-right font-mono" style={{ color: '#f1f5f9' }}>{val.value} {val.unit}</td>
                      <td className="px-5 py-3 text-right" style={{ color: 'rgba(255,255,255,0.4)' }}>{val.normal_low}–{val.normal_high}</td>
                      <td className="px-5 py-3 text-center">
                        <span
                          className="inline-block text-xs font-bold px-2 py-0.5 rounded-full"
                          style={{ background: style.bg, color: style.text }}
                        >
                          {style.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {interpretation.abnormal_explanations && interpretation.abnormal_explanations.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Abnormal Value Explanations
          </h3>
          {interpretation.abnormal_explanations.map((exp, i) => {
            const style = FLAG_STYLE[exp.flag] ?? FLAG_STYLE.NORMAL;
            return (
              <div key={i} style={CARD} className="p-5">
                <div className="flex items-center gap-3 mb-3">
                  <span className="font-bold uppercase" style={{ color: '#f1f5f9' }}>{exp.test.replace(/_/g, ' ')}</span>
                  <span className="text-sm font-mono" style={{ color: 'rgba(255,255,255,0.55)' }}>{exp.value}</span>
                  <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: style.bg, color: style.text }}>
                    {style.label}
                  </span>
                </div>
                <p className="text-sm mb-3" style={{ color: 'rgba(255,255,255,0.65)' }}>{exp.meaning}</p>
                {exp.possible_causes.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                      Possible Causes
                    </p>
                    <ul className="flex flex-wrap gap-1.5">
                      {exp.possible_causes.map((c, j) => (
                        <li
                          key={j}
                          className="text-xs px-2.5 py-1 rounded-full"
                          style={{ background: 'rgba(255,255,255,0.06)', color: '#94A3B8' }}
                        >
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div
                  className="flex items-start gap-2 text-sm rounded-lg px-3 py-2"
                  style={{ background: 'rgba(6,214,160,0.08)', border: '1px solid rgba(6,214,160,0.15)' }}
                >
                  <span style={{ color: '#06D6A0' }} className="shrink-0">→</span>
                  <span style={{ color: 'rgba(167,243,208,0.85)' }}>{exp.action}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

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
};

const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export default function Reports() {
  const [dragging, setDragging] = useState(false);
  const [file, setFile]         = useState<File | null>(null);
  const [userId, setUserId]     = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [result, setResult]     = useState<ReportResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptFile = (f: File) => {
    const ok = [
      'application/pdf',
      'image/png',
      'image/jpeg',
      'image/jpg',
      'image/webp',
      'text/plain',
      'text/csv',
    ];
    if (!ok.includes(f.type)) { setError('Please upload a PDF, image, .txt, or .csv file.'); return; }
    setFile(f); setError(null); setResult(null);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) acceptFile(f);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) acceptFile(f);
  };

  const upload = async () => {
    if (!file) return;
    setLoading(true); setError(null); setResult(null);
    const form = new FormData();
    form.append('file', file);
    if (userId.trim()) form.append('user_id', userId.trim());
    try {
      const res = await fetch(`${BASE_URL}/api/reports/upload`, { method: 'POST', body: form });
      if (!res.ok) { const data = await res.json().catch(() => ({})); throw new Error(data.detail || `Server error ${res.status}`); }
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setFile(null); setResult(null); setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <div className="animate-fade-in-up">
        <h1
          className="text-2xl font-extrabold tracking-tight"
          style={{ color: '#f1f5f9', fontFamily: 'Sora, sans-serif' }}
        >
          Medical Report Analysis
        </h1>
        <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.35)' }}>
          Upload any medical report for AI-powered interpretation.
        </p>
      </div>

      {/* Upload area */}
      {!result && (
        <div style={CARD} className="p-6 space-y-5 animate-fade-in-up stagger-1">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className="cursor-pointer rounded-xl border-2 border-dashed transition-all flex flex-col items-center justify-center py-12 gap-3"
            style={{
              borderColor: dragging
                ? '#06D6A0'
                : file
                ? '#FF9500'
                : 'rgba(255,255,255,0.15)',
              background: dragging
                ? 'rgba(6,214,160,0.06)'
                : file
                ? 'rgba(255,149,0,0.06)'
                : 'rgba(255,255,255,0.02)',
            }}
          >
            <input ref={inputRef} type="file" accept=".pdf,.txt,.csv,image/*" className="hidden" onChange={onChange} />
            {file ? (
              <>
                <span className="text-3xl">📄</span>
                <p className="font-semibold" style={{ color: '#f1f5f9' }}>{file.name}</p>
                <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
                  {(file.size / 1024).toFixed(0)} KB · Click to change
                </p>
              </>
            ) : (
              <>
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-1"
                  style={{ background: 'rgba(255,149,0,0.1)', border: '1px solid rgba(255,149,0,0.25)' }}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FF9500" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <p className="font-semibold" style={{ color: '#f1f5f9' }}>Drop any medical report here</p>
                <p className="text-xs text-center" style={{ color: 'rgba(255,255,255,0.35)' }}>
                  Blood reports, X-Ray, MRI, CT scans, ECG, prescriptions<br />
                  PDF, PNG, JPG · Max 10 MB
                </p>
              </>
            )}
          </div>

          {/* Patient ID */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest mb-1.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Patient ID <span className="normal-case font-normal" style={{ color: 'rgba(255,255,255,0.25)' }}>(optional — saves to history)</span>
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter your patient ID..."
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

          {/* Buttons */}
          <div className="flex gap-3">
            <button
              onClick={upload}
              disabled={!file || loading}
              className="flex-1 py-3 rounded-xl text-white font-bold text-sm transition-all disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: 'linear-gradient(135deg, #FF9500, #FF6B00)',
                boxShadow: file && !loading ? '0 0 24px rgba(255,149,0,0.3)' : 'none',
                fontFamily: 'Sora, sans-serif',
              }}
            >
              {loading ? 'Analyzing…' : 'Analyze Report'}
            </button>
            {file && (
              <button
                onClick={clear}
                className="px-4 py-3 rounded-xl text-sm font-medium transition-colors"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: 'rgba(255,255,255,0.55)',
                }}
              >
                Clear
              </button>
            )}
          </div>

          {error && (
            <div
              className="rounded-xl px-4 py-3 text-sm"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5' }}
            >
              {error}
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-5">
          <button
            onClick={clear}
            className="inline-flex items-center gap-2 text-sm font-semibold transition-colors group animate-fade-in-up"
            style={{ color: 'rgba(255,255,255,0.4)' }}
          >
            <svg className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Upload another report
          </button>

          {/* Summary banner */}
          <div style={CARD} className="p-5 animate-fade-in-up stagger-1">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div className="space-y-2">
                <h2 className="font-bold" style={{ color: '#f1f5f9' }}>{result.filename}</h2>
                <ReportTypeBadge reportType={result.parsed.report_type} />
                {!result.parsed.is_imaging_report && !result.parsed.is_prescription && (
                  <p className="text-sm" style={{ color: 'rgba(255,255,255,0.5)' }}>
                    {Object.keys(result.parsed.values).length} values parsed ·{' '}
                    <span style={{ color: result.parsed.abnormal_count > 0 ? '#FFD580' : '#6ee7b7', fontWeight: 600 }}>
                      {result.parsed.abnormal_count} abnormal
                    </span>
                    {result.parsed.critical_count > 0 && (
                      <span style={{ color: '#fca5a5', fontWeight: 600 }}> · {result.parsed.critical_count} critical</span>
                    )}
                  </p>
                )}
              </div>
              {result.interpretation.overall_urgency && (
                <span
                  className="text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wide"
                  style={(URGENCY_STYLE[result.interpretation.overall_urgency] ?? URGENCY_STYLE.routine) as React.CSSProperties}
                >
                  {result.interpretation.overall_urgency}
                </span>
              )}
            </div>

            {result.interpretation.interpretation && (
              <p
                className="mt-4 text-sm leading-relaxed pt-4"
                style={{ color: 'rgba(255,255,255,0.65)', borderTop: '1px solid rgba(255,255,255,0.06)' }}
              >
                {result.interpretation.interpretation}
              </p>
            )}
          </div>

          {/* Type-specific content */}
          {result.parsed.is_imaging_report && <ImagingSection interpretation={result.interpretation} />}
          {result.parsed.is_prescription && <PrescriptionSection interpretation={result.interpretation} />}
          {!result.parsed.is_imaging_report && !result.parsed.is_prescription && (
            <LabSection parsed={result.parsed} interpretation={result.interpretation} />
          )}

          {/* Follow-up */}
          {result.interpretation.recommended_followup && (
            <div
              style={{ ...CARD }}
              className="p-5 flex items-start gap-3 animate-fade-in-up"
            >
              <span className="text-xl shrink-0">🩺</span>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  Recommended Follow-up
                </p>
                <p className="text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>
                  {result.interpretation.recommended_followup}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
