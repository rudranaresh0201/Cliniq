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
  // Lab
  abnormal_explanations?: AbnormalExplanation[];
  // Imaging
  findings?: string[];
  what_it_means?: string;
  questions_to_ask?: string[];
  // Prescription
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
// Style maps
// ---------------------------------------------------------------------------

const FLAG_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  NORMAL:        { bg: '#F0FDF4', text: '#166534', label: 'Normal' },
  HIGH:          { bg: '#FFF7ED', text: '#9A3412', label: 'High' },
  LOW:           { bg: '#EFF6FF', text: '#1E40AF', label: 'Low' },
  CRITICAL_HIGH: { bg: '#FEF2F2', text: '#991B1B', label: 'Critical ↑' },
  CRITICAL_LOW:  { bg: '#FEF2F2', text: '#991B1B', label: 'Critical ↓' },
};

const URGENCY_STYLE: Record<string, { bg: string; text: string }> = {
  routine:   { bg: '#F0FDF4', text: '#166534' },
  urgent:    { bg: '#FFF7ED', text: '#9A3412' },
  immediate: { bg: '#FEF2F2', text: '#991B1B' },
};

const REPORT_TYPE_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  cbc:           { label: 'CBC Report',         bg: '#E8F5E9', text: '#2E7D32' },
  lft:           { label: 'LFT Report',         bg: '#E3F2FD', text: '#1565C0' },
  kft:           { label: 'KFT Report',         bg: '#E3F2FD', text: '#1565C0' },
  lipid:         { label: 'Lipid Profile',      bg: '#E3F2FD', text: '#1565C0' },
  diabetes:      { label: 'Diabetes Report',    bg: '#FFF3E0', text: '#E65100' },
  thyroid:       { label: 'Thyroid Report',     bg: '#E3F2FD', text: '#1565C0' },
  xray_report:   { label: 'X-Ray Report',       bg: '#F3E5F5', text: '#6A1B9A' },
  mri_report:    { label: 'MRI Report',         bg: '#F3E5F5', text: '#6A1B9A' },
  ct_report:     { label: 'CT Scan Report',     bg: '#F3E5F5', text: '#6A1B9A' },
  ecg_report:    { label: 'ECG Report',         bg: '#F3E5F5', text: '#6A1B9A' },
  urine:         { label: 'Urine Report',       bg: '#E8F5E9', text: '#2E7D32' },
  prescription:  { label: 'Prescription',       bg: '#FEF9E7', text: '#B8860B' },
  general_medical: { label: 'Medical Report',   bg: '#F1F5F9', text: '#475569' },
  unknown:       { label: 'Unknown',            bg: '#F1F5F9', text: '#94A3B8' },
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
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
          <h3 className="font-bold text-slate-800 mb-3">Findings Summary</h3>
          <ul className="space-y-2">
            {interpretation.findings.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="text-slate-400 shrink-0 mt-0.5">•</span>
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {interpretation.what_it_means && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
          <h3 className="font-bold text-slate-800 mb-2">What This Means For You</h3>
          <p className="text-sm text-slate-700 leading-relaxed">{interpretation.what_it_means}</p>
        </div>
      )}

      {interpretation.questions_to_ask && interpretation.questions_to_ask.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
          <h3 className="font-bold text-slate-800 mb-3">Questions To Ask Your Doctor</h3>
          <ol className="space-y-2">
            {interpretation.questions_to_ask.map((q, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="shrink-0 font-semibold text-slate-400">{i + 1}.</span>
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
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2">Important Warnings</p>
          <ul className="space-y-1">
            {interpretation.important_warnings.map((w, i) => (
              <li key={i} className="text-sm text-red-800 flex items-start gap-2">
                <span className="shrink-0">⚠️</span>
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {interpretation.medicines && interpretation.medicines.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest">Your Medicines</h3>
          {interpretation.medicines.map((med, i) => (
            <div key={i} className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
              <div className="flex items-start justify-between gap-3 mb-3">
                <h4 className="font-bold text-slate-800">{med.name}</h4>
                {med.duration && (
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full shrink-0">
                    {med.duration}
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-600 mb-2">
                <span className="font-semibold text-slate-700">Purpose: </span>{med.purpose}
              </p>
              <p className="text-sm text-slate-600 mb-3">
                <span className="font-semibold text-slate-700">How to take: </span>{med.how_to_take}
              </p>
              {med.side_effects && med.side_effects.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                    Watch for
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {med.side_effects.map((s, j) => (
                      <span key={j} className="text-xs bg-orange-50 text-orange-700 border border-orange-200 px-2 py-0.5 rounded-full">
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

function LabSection({
  parsed,
  interpretation,
}: {
  parsed: ParsedReport;
  interpretation: ReportInterpretation;
}) {
  return (
    <div className="space-y-4">
      {/* Values table */}
      {Object.keys(parsed.values).length > 0 && (
        <div className="bg-white rounded-xl shadow-md border border-slate-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-50">
            <h3 className="font-bold text-slate-800">Parsed Values</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-5 py-3">Test</th>
                  <th className="text-right px-5 py-3">Result</th>
                  <th className="text-right px-5 py-3">Normal Range</th>
                  <th className="text-center px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {Object.entries(parsed.values).map(([name, val]) => {
                  const style = FLAG_STYLE[val.flag] ?? FLAG_STYLE.NORMAL;
                  return (
                    <tr key={name} className={val.flag !== 'NORMAL' ? 'bg-orange-50/30' : ''}>
                      <td className="px-5 py-3 font-medium text-slate-800 uppercase">{name.replace(/_/g, ' ')}</td>
                      <td className="px-5 py-3 text-right font-mono text-slate-700">{val.value} {val.unit}</td>
                      <td className="px-5 py-3 text-right text-slate-500">{val.normal_low}–{val.normal_high}</td>
                      <td className="px-5 py-3 text-center">
                        <span className="inline-block text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: style.bg, color: style.text }}>
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

      {/* Abnormal explanations */}
      {interpretation.abnormal_explanations && interpretation.abnormal_explanations.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest">Abnormal Value Explanations</h3>
          {interpretation.abnormal_explanations.map((exp, i) => {
            const style = FLAG_STYLE[exp.flag] ?? FLAG_STYLE.NORMAL;
            return (
              <div key={i} className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                <div className="flex items-center gap-3 mb-3">
                  <span className="font-bold text-slate-800 uppercase">{exp.test.replace(/_/g, ' ')}</span>
                  <span className="text-sm font-mono text-slate-600">{exp.value}</span>
                  <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: style.bg, color: style.text }}>
                    {style.label}
                  </span>
                </div>
                <p className="text-sm text-slate-700 mb-3">{exp.meaning}</p>
                {exp.possible_causes.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Possible Causes</p>
                    <ul className="flex flex-wrap gap-1.5">
                      {exp.possible_causes.map((c, j) => (
                        <li key={j} className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full">{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="flex items-start gap-2 text-sm rounded-lg px-3 py-2" style={{ background: '#F0FDF4' }}>
                  <span className="text-green-600 shrink-0">→</span>
                  <span className="text-green-900">{exp.action}</span>
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

export default function Reports() {
  const [dragging, setDragging]   = useState(false);
  const [file, setFile]           = useState<File | null>(null);
  const [userId, setUserId]       = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [result, setResult]       = useState<ReportResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptFile = (f: File) => {
    const ok = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'text/plain'];
    if (!ok.includes(f.type)) {
      setError('Please upload a PDF, image, or text file.');
      return;
    }
    setFile(f);
    setError(null);
    setResult(null);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) acceptFile(f);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) acceptFile(f);
  };

  const upload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const form = new FormData();
    form.append('file', file);
    if (userId.trim()) form.append('user_id', userId.trim());

    try {
      const res = await fetch('http://127.0.0.1:8000/api/reports/upload', {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error ${res.status}`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Medical Report Analysis</h1>
        <p className="text-slate-500 text-sm mt-1">Upload any medical report for AI-powered interpretation.</p>
      </div>

      {/* Upload area */}
      {!result && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-6 space-y-5">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className="cursor-pointer rounded-xl border-2 border-dashed transition-colors flex flex-col items-center justify-center py-12 gap-3"
            style={{
              borderColor: dragging ? '#4CAF50' : file ? '#F5C518' : '#CBD5E1',
              background:  dragging ? '#F0FDF4' : file ? '#FFFBEB' : '#F8FAFC',
            }}
          >
            <input ref={inputRef} type="file" accept=".pdf,image/*,.txt" className="hidden" onChange={onChange} />
            {file ? (
              <>
                <span className="text-3xl">📄</span>
                <p className="font-semibold text-slate-800">{file.name}</p>
                <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(0)} KB · Click to change</p>
              </>
            ) : (
              <>
                <span className="text-4xl">☁️</span>
                <p className="font-semibold text-slate-700">Drop any medical report here</p>
                <p className="text-xs text-slate-500 text-center">
                  Blood reports, X-Ray reports, MRI reports,<br />
                  CT scans, ECG reports, prescriptions<br />
                  PDF, PNG, JPG · Max 10 MB
                </p>
              </>
            )}
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
              Patient ID <span className="font-normal text-slate-400">(optional — saves to your history)</span>
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter your patient ID..."
              className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-green-400 transition-colors"
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={upload}
              disabled={!file || loading}
              className="flex-1 py-3 rounded-xl text-slate-900 font-bold text-sm transition-all disabled:opacity-50 shadow-sm"
              style={{ background: '#F5C518' }}
            >
              {loading ? 'Analyzing…' : 'Analyze Report'}
            </button>
            {file && (
              <button
                onClick={clear}
                className="px-4 py-3 rounded-xl text-slate-600 text-sm font-medium border border-slate-200 hover:bg-slate-50 transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>
          )}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-5">
          <button
            onClick={clear}
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors group"
          >
            <svg className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Upload another report
          </button>

          {/* Summary banner */}
          <div className="bg-white rounded-xl shadow-md border border-slate-100 p-5">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div className="space-y-2">
                <h2 className="font-bold text-slate-800">{result.filename}</h2>
                <ReportTypeBadge reportType={result.parsed.report_type} />
                {!result.parsed.is_imaging_report && !result.parsed.is_prescription && (
                  <p className="text-sm text-slate-500">
                    {Object.keys(result.parsed.values).length} values parsed ·{' '}
                    <span className={result.parsed.abnormal_count > 0 ? 'text-orange-600 font-semibold' : 'text-green-600'}>
                      {result.parsed.abnormal_count} abnormal
                    </span>
                    {result.parsed.critical_count > 0 && (
                      <span className="text-red-600 font-semibold"> · {result.parsed.critical_count} critical</span>
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
              <p className="mt-4 text-sm text-slate-700 leading-relaxed border-t border-slate-50 pt-4">
                {result.interpretation.interpretation}
              </p>
            )}
          </div>

          {/* Type-specific content */}
          {result.parsed.is_imaging_report && (
            <ImagingSection interpretation={result.interpretation} />
          )}
          {result.parsed.is_prescription && (
            <PrescriptionSection interpretation={result.interpretation} />
          )}
          {!result.parsed.is_imaging_report && !result.parsed.is_prescription && (
            <LabSection parsed={result.parsed} interpretation={result.interpretation} />
          )}

          {/* Follow-up (all types) */}
          {result.interpretation.recommended_followup && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 flex items-start gap-3">
              <span className="text-xl shrink-0">🩺</span>
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Recommended Follow-up</p>
                <p className="text-sm text-slate-700">{result.interpretation.recommended_followup}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
