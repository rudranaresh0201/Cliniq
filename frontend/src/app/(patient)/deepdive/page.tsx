import { useState, useRef, useEffect, useId } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ValueDisplay } from '../../../components/primitives';
import { AmbientBackground } from '../../../components/AmbientBackground';
import { EASE_OUT } from '../../../lib/motion';
import { uploadLabReport } from '../../../lib/api/deepdive';
import type { LabUploadResponse, AbnormalFlag, PatternDetected } from '../../../lib/api/deepdive';

// ── Case ID resolution ─────────────────────────────────────────────────────────

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function getCaseId(): string | null {
  const params    = new URLSearchParams(window.location.search);
  const urlCaseId = params.get('case_id');
  if (urlCaseId && UUID_RE.test(urlCaseId)) return urlCaseId;

  const stored = localStorage.getItem('cliniq_active_case_id');
  if (stored && UUID_RE.test(stored)) return stored;

  return null;
}

// ── Types ──────────────────────────────────────────────────────────────────────

type Phase     = 'idle' | 'processing' | 'complete' | 'error';
type LabStatus = 'normal' | 'low' | 'high' | 'critical';

interface BiomarkerItem { key: string; val: string; unit: string; status: LabStatus }
interface PatternItem   { confirmed: boolean; label: string; confidence: number }

// ── Pipeline config ────────────────────────────────────────────────────────────

const STAGES = [
  { label: 'OCR & File Reading',    sub: 'Extracting text from document',          duration: 1500 },
  { label: 'Report Classification', sub: 'Identifying report type and structure',   duration: 800  },
  { label: 'Biomarker Detection',   sub: 'Parsing lab values and reference ranges', duration: 2200 },
  { label: 'Pattern Recognition',   sub: 'Matching clinical disease signatures',    duration: 1800 },
  { label: 'Risk Assessment',       sub: 'Computing recovery score',                duration: 1000 },
  { label: 'Intelligence Complete', sub: 'Synthesis ready',                         duration: 300  },
];

// ── Data-transform helpers ─────────────────────────────────────────────────────

const RISK_TO_SCORE: Record<string, number> = {
  low: 82, moderate: 58, high: 36, critical: 18,
};

const SPECIALIST_MAP: Record<string, string> = {
  CBC: 'Haematology', LFT: 'Hepatology', RFT: 'Nephrology',
  ECG: 'Cardiology',  Xray: 'Radiology',
};

function riskToScore(level: string): number {
  return RISK_TO_SCORE[level] ?? 50;
}

function riskToStatus(level: string): LabStatus {
  if (level === 'critical') return 'critical';
  if (level === 'high')     return 'high';
  if (level === 'moderate') return 'low';
  return 'normal';
}

// Confidence from cbc_interpreter is a 0–1 float; normalise to 0–100.
function normConf(c: number): number {
  return c > 0 && c <= 1.0 ? Math.round(c * 100) : Math.round(c);
}

function flagsToMarkers(flags: AbnormalFlag[]): BiomarkerItem[] {
  return flags.map((f) => ({
    key:    f.marker,
    val:    f.value,
    unit:   '',   // unit not included in abnormal_flags response
    status: f.severity === 'critical' ? 'critical'
          : f.direction === 'low'     ? 'low'
          :                             'high',
  }));
}

function patternsToItems(patterns: PatternDetected[]): PatternItem[] {
  return patterns.map((p) => {
    const conf = normConf(p.confidence);
    return { confirmed: conf >= 50, label: p.pattern, confidence: conf };
  });
}

function buildFindings(r: LabUploadResponse): string[] {
  const summary = r.interpretation.clinical_summary?.trim();
  if (summary) {
    const sentences = summary
      .split(/\.\s+|\.\n|\n/)
      .map((s) => s.replace(/^[-•*]\s*/, '').trim())
      .filter((s) => s.length > 15);
    if (sentences.length > 0) return sentences.slice(0, 4);
  }
  if (r.interpretation.primary_finding) return [r.interpretation.primary_finding];
  return r.interpretation.immediate_actions.slice(0, 3);
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function bioColor(s: LabStatus): string {
  if (s === 'critical') return 'var(--critical, #FF4444)';
  if (s === 'low' || s === 'high') return 'var(--warning, #F59E0B)';
  return 'rgba(255,255,255,0.7)';
}

function fmtDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

// ── Animated dashed SVG border for upload zone ────────────────────────────────

const UZ_W = 480;
const UZ_H = 360;

function UploadBorder({ isDragOver }: { isDragOver: boolean }) {
  return (
    <svg
      width={UZ_W} height={UZ_H}
      viewBox={`0 0 ${UZ_W} ${UZ_H}`}
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
      fill="none"
    >
      {isDragOver ? (
        <rect
          x="1" y="1" width={UZ_W - 2} height={UZ_H - 2} rx="23"
          stroke="var(--accent, #7C65F6)" strokeWidth="1.5"
        />
      ) : (
        <motion.rect
          x="1" y="1" width={UZ_W - 2} height={UZ_H - 2} rx="23"
          stroke="rgba(124,101,246,0.4)" strokeWidth="1"
          strokeDasharray="10 6"
          animate={{ strokeDashoffset: [0, -16] }}
          transition={{ duration: 1, ease: 'linear', repeat: Infinity }}
        />
      )}
    </svg>
  );
}

// ── Upload SVG icon ────────────────────────────────────────────────────────────

function UploadIcon() {
  return (
    <svg width={40} height={40} viewBox="0 0 24 24" fill="none" stroke="var(--text-muted, #4A4A5A)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

// ── Idle — upload zone ─────────────────────────────────────────────────────────

function IdleView({
  onFile,
  caseId,
  onCaseIdChange,
}: {
  onFile: (file: File) => void;
  caseId: string;
  onCaseIdChange: (id: string) => void;
}) {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasCase = UUID_RE.test(caseId.trim());

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (!hasCase) return;
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  };

  const handleClick = () => {
    if (!hasCase) return;
    inputRef.current?.click();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: EASE_OUT }}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: '0 16px' }}
    >
      <motion.div
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={handleClick}
        animate={{ backgroundColor: isDragOver && hasCase ? 'rgba(124,101,246,0.07)' : 'rgba(124,101,246,0.03)' }}
        transition={{ duration: 0.15 }}
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: UZ_W,
          minHeight: UZ_H,
          borderRadius: 24,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 20,
          cursor: hasCase ? 'pointer' : 'default',
          userSelect: 'none',
          boxShadow: isDragOver && hasCase ? '0 0 40px rgba(124,101,246,0.12)' : 'none',
          transition: 'box-shadow 150ms ease',
        }}
      >
        <UploadBorder isDragOver={isDragOver && hasCase} />

        {/* Floating upload icon */}
        <motion.div
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 2, ease: 'easeInOut', repeat: Infinity }}
          style={{ opacity: hasCase ? 1 : 0.4 }}
        >
          <UploadIcon />
        </motion.div>

        {/* Text */}
        <div style={{ textAlign: 'center', zIndex: 1 }}>
          <p style={{ margin: '0 0 6px', fontSize: 18, fontWeight: 500, color: 'var(--text-primary, #F0F0F4)', letterSpacing: '-0.3px' }}>
            Drop your lab report
          </p>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted, #4A4A5A)' }}>
            PDF · JPG · PNG
          </p>
        </div>

        {/* Supported type pills */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center', zIndex: 1 }}>
          {['CBC', 'LFT', 'RFT', 'ECG', 'X-Ray'].map((t) => (
            <span key={t} style={{
              padding: '4px 12px', borderRadius: 999,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.07)',
              fontSize: 11, color: 'var(--text-muted, #4A4A5A)',
              fontWeight: 500,
            }}>
              {t}
            </span>
          ))}
        </div>

        {/* Case ID input */}
        <div
          style={{ width: '100%', maxWidth: 320, zIndex: 1 }}
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="text"
            value={caseId}
            onChange={(e) => onCaseIdChange(e.target.value)}
            placeholder="Case ID (required to upload)"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '9px 14px',
              borderRadius: 10,
              background: 'rgba(255,255,255,0.04)',
              border: hasCase
                ? '1px solid rgba(124,101,246,0.4)'
                : '1px solid rgba(255,255,255,0.1)',
              color: hasCase ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.35)',
              fontSize: 12,
              fontFamily: 'JetBrains Mono, monospace',
              outline: 'none',
              transition: 'border-color 150ms ease',
            }}
          />
          {!hasCase && caseId.trim().length === 0 && (
            <p style={{ margin: '6px 0 0', fontSize: 11, color: 'rgba(255,149,0,0.6)', textAlign: 'center' }}>
              No active case found. Please start from the Analyze screen.
            </p>
          )}
          {!hasCase && caseId.trim().length > 0 && (
            <p style={{ margin: '6px 0 0', fontSize: 11, color: 'rgba(239,68,68,0.7)', textAlign: 'center' }}>
              Invalid Case ID — must be a valid UUID.
            </p>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          style={{ display: 'none' }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f && hasCase) onFile(f); }}
        />
      </motion.div>
    </motion.div>
  );
}

// ── Stage indicator circle ─────────────────────────────────────────────────────

function StageIndicator({ index, status }: { index: number; status: 'inactive' | 'active' | 'complete' }) {
  return (
    <motion.div
      animate={status === 'active'
        ? { boxShadow: ['0 0 0 0 rgba(124,101,246,0)', '0 0 16px 4px rgba(124,101,246,0.35)', '0 0 0 0 rgba(124,101,246,0)'] }
        : { boxShadow: '0 0 0 0 rgba(0,0,0,0)' }
      }
      transition={status === 'active' ? { duration: 2, repeat: Infinity, ease: 'easeInOut' } : {}}
      style={{
        width: 28, height: 28,
        borderRadius: '50%',
        flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: status === 'active' ? 'var(--accent, #7C65F6)'
                  : status === 'complete' ? 'var(--stable, #22C55E)'
                  : 'transparent',
        border: status === 'inactive' ? '1px dashed rgba(255,255,255,0.12)' : 'none',
        transition: 'background 300ms ease, border 300ms ease',
      }}
    >
      {status === 'complete' ? (
        <motion.svg
          initial={{ scale: 0 }} animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          width={14} height={14} viewBox="0 0 14 14" fill="none"
          stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
        >
          <polyline points="2 7 5.5 10.5 12 3.5" />
        </motion.svg>
      ) : (
        <span style={{
          fontSize: 11, fontWeight: 600,
          color: status === 'active' ? 'white' : 'rgba(255,255,255,0.2)',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {index + 1}
        </span>
      )}
    </motion.div>
  );
}

// ── Stage 3 content — biomarker values ────────────────────────────────────────

function BiomarkerContent({ items, loading }: { items: BiomarkerItem[]; loading: boolean }) {
  if (loading) {
    return (
      <div style={{ marginTop: 10, fontSize: 12, color: 'rgba(255,255,255,0.25)', fontStyle: 'italic' }}>
        Parsing values…
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div style={{ marginTop: 10, fontSize: 12, color: 'rgba(255,255,255,0.25)' }}>
        No abnormal values detected.
      </div>
    );
  }
  return (
    <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '5px 24px' }}>
      {items.map((b, i) => (
        <motion.div
          key={b.key}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.18, duration: 0.22, ease: EASE_OUT }}
          style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}
        >
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', minWidth: 80, flexShrink: 0 }}>{b.key}</span>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 12, fontWeight: 500,
            fontVariantNumeric: 'tabular-nums',
            color: bioColor(b.status),
          }}>
            {b.val}{b.unit ? <span style={{ fontSize: 10, opacity: 0.7 }}> {b.unit}</span> : null}
          </span>
        </motion.div>
      ))}
    </div>
  );
}

// ── Stage 4 content — pattern checks ──────────────────────────────────────────

function PatternContent({ items, loading }: { items: PatternItem[]; loading: boolean }) {
  if (loading) {
    return (
      <div style={{ marginTop: 10, fontSize: 12, color: 'rgba(255,255,255,0.25)', fontStyle: 'italic' }}>
        Matching patterns…
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div style={{ marginTop: 10, fontSize: 12, color: 'rgba(255,255,255,0.25)' }}>
        No clinical patterns matched.
      </div>
    );
  }
  return (
    <div style={{ marginTop: 10 }}>
      {items.map((p, i) => (
        <motion.div
          key={p.label}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.3, duration: 0.22, ease: EASE_OUT }}
          style={{ marginBottom: 10 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 13, color: p.confirmed ? 'var(--stable, #22C55E)' : 'rgba(255,255,255,0.2)', flexShrink: 0 }}>
              {p.confirmed ? '✓' : '○'}
            </span>
            <span style={{ fontSize: 13, color: p.confirmed ? 'var(--text-secondary, #8B8B99)' : 'rgba(255,255,255,0.2)', flex: 1 }}>
              {p.label}
            </span>
            <span style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 11, fontVariantNumeric: 'tabular-nums',
              color: p.confirmed ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)',
            }}>
              {p.confidence}%
            </span>
          </div>
          <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden' }}>
            <motion.div
              initial={{ width: '0%' }}
              animate={{ width: `${p.confidence}%` }}
              transition={{ delay: i * 0.3 + 0.1, duration: 0.3, ease: EASE_OUT }}
              style={{
                height: '100%', borderRadius: 1,
                background: p.confirmed ? 'var(--stable, #22C55E)' : 'rgba(107,114,128,0.4)',
              }}
            />
          </div>
        </motion.div>
      ))}
    </div>
  );
}

// ── Stage 5 content — risk score + mini ring ──────────────────────────────────

const MINI_R    = 32;
const MINI_CIRC = 2 * Math.PI * MINI_R;

function RiskContent({
  score,
  status,
  gradientId,
  loading,
}: {
  score: number;
  status: LabStatus;
  gradientId: string;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div style={{ marginTop: 14, fontSize: 12, color: 'rgba(255,255,255,0.25)', fontStyle: 'italic' }}>
        Computing score…
      </div>
    );
  }
  const offset = MINI_CIRC * (1 - score / 100);
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{ display: 'flex', alignItems: 'center', gap: 24, marginTop: 14 }}
    >
      {/* Mini ring */}
      <svg width={80} height={80} viewBox="0 0 80 80" style={{ flexShrink: 0 }}>
        <defs>
          <linearGradient id={gradientId} gradientUnits="userSpaceOnUse" x1="8" y1="40" x2="72" y2="40">
            <stop offset="0%" stopColor="#9B87FF" />
            <stop offset="100%" stopColor="#F59E0B" />
          </linearGradient>
        </defs>
        <circle cx="40" cy="40" r={MINI_R} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
        <motion.circle
          cx="40" cy="40" r={MINI_R}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={MINI_CIRC}
          initial={{ strokeDashoffset: MINI_CIRC }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.0, ease: EASE_OUT }}
          transform="rotate(-90 40 40)"
        />
      </svg>

      {/* Score */}
      <div>
        <span style={{ display: 'block', fontSize: 11, color: 'var(--text-muted, #4A4A5A)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 4 }}>
          Recovery Score
        </span>
        <ValueDisplay value={score} size="hero" status={status} />
      </div>
    </motion.div>
  );
}

// ── Stage progress bar ─────────────────────────────────────────────────────────

function StageProgressBar({ duration, stageKey }: { duration: number; stageKey: number }) {
  return (
    <div key={stageKey} style={{ marginTop: 6, height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
      <motion.div
        initial={{ width: '0%' }}
        animate={{ width: '100%' }}
        transition={{ duration: duration / 1000, ease: 'linear' }}
        style={{ height: '100%', borderRadius: 2, background: 'var(--accent, #7C65F6)' }}
      />
    </div>
  );
}

// ── Processing — pipeline view ─────────────────────────────────────────────────

function ProcessingView({
  fileName,
  reportTypeLabel,
  activeStage,
  completedStages,
  riskGradientId,
  result,
}: {
  fileName: string;
  reportTypeLabel: string;
  activeStage: number;
  completedStages: Set<number>;
  riskGradientId: string;
  result: LabUploadResponse | null;
}) {
  const hasResult = result !== null;

  const bioItems   = hasResult ? flagsToMarkers(result.interpretation.abnormal_flags) : [];
  const patItems   = hasResult ? patternsToItems(result.interpretation.patterns_detected) : [];
  const riskScore  = hasResult ? riskToScore(result.interpretation.risk_level) : 0;
  const riskStatus = hasResult ? riskToStatus(result.interpretation.risk_level) : 'normal';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: EASE_OUT }}
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 24px 40px',
      }}
    >
      {/* File chip */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1, ease: EASE_OUT }}
        style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 32 }}
      >
        <span style={{ fontSize: 13, color: 'var(--text-secondary, #8B8B99)', fontWeight: 500, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {fileName}
        </span>
        <span style={{
          padding: '3px 10px', borderRadius: 999,
          background: 'rgba(124,101,246,0.12)',
          border: '1px solid rgba(124,101,246,0.3)',
          fontSize: 11, fontWeight: 600, color: 'var(--accent-bright, #9B87FF)',
        }}>
          {reportTypeLabel}
        </span>
      </motion.div>

      {/* Pipeline */}
      <div style={{ width: '100%', maxWidth: 480 }}>
        {STAGES.map((stage, i) => {
          const isDone   = completedStages.has(i);
          const isActive = activeStage === i && !isDone;
          const status: 'inactive' | 'active' | 'complete' = isDone ? 'complete' : isActive ? 'active' : 'inactive';

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: isActive || isDone ? 1 : 0.4, x: 0 }}
              transition={{ duration: 0.3, delay: i * 0.06, ease: EASE_OUT }}
              style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 6 }}
            >
              <div style={{ paddingTop: 2 }}>
                <StageIndicator index={i} status={status} />
              </div>

              <div style={{ flex: 1 }}>
                {/* Label row */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', minHeight: 28 }}>
                  <div>
                    <span style={{
                      fontSize: 14, fontWeight: isActive ? 600 : 400,
                      color: isActive ? 'var(--text-primary, #F0F0F4)' : isDone ? 'var(--text-secondary, #8B8B99)' : 'rgba(255,255,255,0.2)',
                      transition: 'color 300ms ease',
                    }}>
                      {stage.label}
                    </span>
                    {isActive && (
                      <motion.span
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        style={{ display: 'block', fontSize: 11, color: 'var(--text-muted, #4A4A5A)', marginTop: 1 }}
                      >
                        {stage.sub}
                      </motion.span>
                    )}
                  </div>
                  {isDone && (
                    <motion.span
                      initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
                      style={{
                        padding: '2px 8px', borderRadius: 999,
                        background: 'rgba(34,197,94,0.08)',
                        border: '1px solid rgba(34,197,94,0.2)',
                        fontSize: 11, color: 'var(--stable, #22C55E)',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontVariantNumeric: 'tabular-nums',
                        flexShrink: 0,
                      }}
                    >
                      {fmtDuration(stage.duration)}
                    </motion.span>
                  )}
                </div>

                {/* Progress bar — only while active */}
                {isActive && <StageProgressBar duration={stage.duration} stageKey={i} />}

                {/* Stage-specific content reveals */}
                <AnimatePresence>
                  {(isActive || isDone) && i === 2 && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: EASE_OUT }}
                      style={{ overflow: 'hidden' }}
                    >
                      <BiomarkerContent items={bioItems} loading={!hasResult} />
                    </motion.div>
                  )}
                  {(isActive || isDone) && i === 3 && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: EASE_OUT }}
                      style={{ overflow: 'hidden' }}
                    >
                      <PatternContent items={patItems} loading={!hasResult} />
                    </motion.div>
                  )}
                  {(isActive || isDone) && i === 4 && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: EASE_OUT }}
                      style={{ overflow: 'hidden' }}
                    >
                      <RiskContent
                        score={riskScore}
                        status={riskStatus}
                        gradientId={riskGradientId}
                        loading={!hasResult}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}

// ── Complete — findings card ───────────────────────────────────────────────────

function FindingsCard({ result, onReset }: { result: LabUploadResponse; onReset: () => void }) {
  const specialist = SPECIALIST_MAP[result.report_type] ?? result.report_type;
  const findings   = buildFindings(result);
  const patternTags = result.interpretation.patterns_detected
    .slice(0, 5)
    .map((p) => p.pattern);
  const riskScore  = riskToScore(result.interpretation.risk_level);
  const riskStatus = riskToStatus(result.interpretation.risk_level);

  return (
    <motion.div
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 100, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 280, damping: 28, delay: 0.5 }}
      style={{ padding: '0 16px 40px', maxWidth: 520, margin: '0 auto', width: '100%' }}
    >
      <div style={{
        background: 'var(--bg-glass, rgba(15,15,20,0.6))',
        backdropFilter: 'blur(24px) saturate(180%)',
        WebkitBackdropFilter: 'blur(24px) saturate(180%)',
        border: '1px solid rgba(124,101,246,0.25)',
        borderRadius: 18,
        padding: '22px 22px 20px',
        boxShadow: '0 0 60px rgba(124,101,246,0.12), inset 0 1px 0 rgba(124,101,246,0.1)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted, #4A4A5A)' }}>
              Intelligence Report
            </span>
            <span style={{
              padding: '3px 10px', borderRadius: 999,
              background: 'rgba(124,101,246,0.12)',
              border: '1px solid rgba(124,101,246,0.3)',
              fontSize: 11, fontWeight: 600, color: 'var(--accent-bright, #9B87FF)',
            }}>
              {specialist}
            </span>
          </div>
          <ValueDisplay value={riskScore} size="lg" status={riskStatus} />
        </div>

        {/* Findings list */}
        <div style={{ marginBottom: 16 }}>
          {findings.length > 0 ? findings.map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.7 + i * 0.12, duration: 0.25, ease: EASE_OUT }}
              style={{ display: 'flex', gap: 10, marginBottom: 10, alignItems: 'flex-start' }}
            >
              <span style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11, fontWeight: 700, color: 'rgba(124,101,246,0.6)',
                flexShrink: 0, marginTop: 2,
              }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary, #8B8B99)', lineHeight: 1.55 }}>{f}</p>
            </motion.div>
          )) : (
            <p style={{ margin: 0, fontSize: 13, color: 'rgba(255,255,255,0.25)' }}>
              {result.interpretation.primary_finding || 'Analysis complete. See doctor for interpretation.'}
            </p>
          )}
        </div>

        {/* Pattern tags */}
        {patternTags.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 20 }}>
            {patternTags.map((p) => (
              <span key={p} style={{
                padding: '4px 12px', borderRadius: 999,
                background: 'rgba(124,101,246,0.1)',
                border: '1px solid rgba(124,101,246,0.25)',
                fontSize: 11, fontWeight: 500, color: 'var(--accent-bright, #9B87FF)',
              }}>
                {p}
              </span>
            ))}
          </div>
        )}

        {/* CTAs */}
        <div style={{ display: 'flex', gap: 10 }}>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            style={{
              flex: 1, padding: '10px 0',
              borderRadius: 10,
              background: 'var(--accent, #7C65F6)',
              border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: 600, color: 'white',
              boxShadow: '0 0 20px rgba(124,101,246,0.3)',
            }}
          >
            Add to Timeline
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onReset}
            style={{
              flex: 1, padding: '10px 0',
              borderRadius: 10,
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.1)',
              cursor: 'pointer',
              fontSize: 13, fontWeight: 500,
              color: 'var(--text-secondary, #8B8B99)',
            }}
          >
            Upload Another
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
}

// ── Error view ─────────────────────────────────────────────────────────────────

function ErrorView({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      transition={{ duration: 0.3, ease: EASE_OUT }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        padding: '0 24px',
        gap: 20,
      }}
    >
      <div style={{
        maxWidth: 420, width: '100%',
        background: 'rgba(255,68,68,0.06)',
        border: '1px solid rgba(255,68,68,0.2)',
        borderRadius: 18,
        padding: '28px 28px 24px',
        textAlign: 'center',
      }}>
        <span style={{ fontSize: 28, display: 'block', marginBottom: 12 }}>⚠</span>
        <p style={{ margin: '0 0 8px', fontSize: 15, fontWeight: 600, color: '#FF6B6B' }}>
          Upload Failed
        </p>
        <p style={{ margin: '0 0 20px', fontSize: 13, color: 'rgba(255,255,255,0.4)', lineHeight: 1.5 }}>
          {message}
        </p>
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onRetry}
          style={{
            padding: '10px 32px', borderRadius: 10,
            background: 'rgba(255,68,68,0.15)',
            border: '1px solid rgba(255,68,68,0.3)',
            cursor: 'pointer', fontSize: 13, fontWeight: 600,
            color: '#FF6B6B',
          }}
        >
          Try Again
        </motion.button>
      </div>
    </motion.div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function DeepDivePage() {
  const [phase, setPhase]                       = useState<Phase>('idle');
  const [fileName, setFileName]                 = useState('');
  const [activeStage, setActiveStage]           = useState(-1);
  const [completedStages, setCompletedStages]   = useState<Set<number>>(new Set());
  const [result, setResult]                     = useState<LabUploadResponse | null>(null);
  const [uploadError, setUploadError]           = useState<string | null>(null);
  const [caseId, setCaseId]                     = useState<string>(() => getCaseId() ?? '');
  const [animFinished, setAnimFinished]         = useState(false);

  const cancelledRef = useRef(false);
  const riskGradientId = `dd-ring-${useId().replace(/:/g, '')}`;

  // ── Advance to 'complete' when animation AND API both finish ───────────────
  useEffect(() => {
    if (animFinished && result && phase === 'processing') {
      setPhase('complete');
    }
  }, [animFinished, result, phase]);

  // ── Pipeline animation — runs on every 'processing' entry ─────────────────
  useEffect(() => {
    if (phase !== 'processing') return;

    setActiveStage(0);
    setCompletedStages(new Set());
    setAnimFinished(false);

    let elapsed = 0;
    const timers: ReturnType<typeof setTimeout>[] = [];

    STAGES.forEach((stage, i) => {
      const t1 = setTimeout(() => {
        if (!cancelledRef.current) setActiveStage(i);
      }, elapsed);
      elapsed += stage.duration;
      const t2 = setTimeout(() => {
        if (!cancelledRef.current) setCompletedStages((prev) => new Set([...prev, i]));
      }, elapsed);
      timers.push(t1, t2);
    });

    const tDone = setTimeout(() => {
      if (!cancelledRef.current) setAnimFinished(true);
    }, elapsed + 500);
    timers.push(tDone);

    return () => timers.forEach(clearTimeout);
  }, [phase]);

  // ── File picked — start API call and animation simultaneously ──────────────
  async function handleFile(file: File) {
    if (!UUID_RE.test(caseId.trim())) {
      setUploadError('No active case found. Please start from the Analyze screen.');
      setPhase('error');
      return;
    }

    cancelledRef.current = false;
    setResult(null);
    setUploadError(null);
    setAnimFinished(false);
    setFileName(file.name);
    setPhase('processing');

    try {
      const data = await uploadLabReport(file, caseId.trim());
      if (!cancelledRef.current) {
        setResult(data);
        // animFinished effect will fire setPhase('complete') when animation also done
      }
    } catch (err) {
      if (!cancelledRef.current) {
        setUploadError(err instanceof Error ? err.message : 'Upload failed.');
        setPhase('error');
      }
    }
  }

  function handleReset() {
    cancelledRef.current = true;
    setPhase('idle');
    setFileName('');
    setActiveStage(-1);
    setCompletedStages(new Set());
    setResult(null);
    setUploadError(null);
    setAnimFinished(false);
  }

  // Derive the type badge label: real type once known, else file extension
  const reportTypeLabel = result?.report_type
    ?? fileName.split('.').pop()?.toUpperCase()
    ?? 'LAB';

  return (
    <div style={{ minHeight: '100vh', background: '#050507', position: 'relative', isolation: 'isolate' }}>
      <AmbientBackground glow="accent" />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <AnimatePresence mode="wait">
          {phase === 'idle' && (
            <IdleView
              key="idle"
              onFile={handleFile}
              caseId={caseId}
              onCaseIdChange={setCaseId}
            />
          )}

          {phase === 'error' && (
            <ErrorView
              key="error"
              message={uploadError ?? 'Unknown error.'}
              onRetry={handleReset}
            />
          )}

          {(phase === 'processing' || phase === 'complete') && (
            <motion.div
              key="pipeline"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4, ease: EASE_OUT }}
              style={{ minHeight: '100vh', overflowY: 'auto' }}
            >
              <ProcessingView
                fileName={fileName}
                reportTypeLabel={reportTypeLabel}
                activeStage={activeStage}
                completedStages={completedStages}
                riskGradientId={riskGradientId}
                result={result}
              />

              <AnimatePresence>
                {phase === 'complete' && result && (
                  <FindingsCard key="findings" result={result} onReset={handleReset} />
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
