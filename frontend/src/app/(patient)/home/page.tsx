import { useState, useEffect, useMemo } from 'react';
import {
  motion,
  useMotionValue,
  useMotionValueEvent,
  animate,
} from 'framer-motion';
import { RiskPill, StatusOrb } from '../../../components/primitives';
import type { RiskStatus } from '../../../components/primitives';
import { AmbientBackground } from '../../../components/AmbientBackground';

// ── Types ──────────────────────────────────────────────────────────────────────

type RiskState = 'critical' | 'warning' | 'stable';
type LabStatus = 'normal' | 'warning' | 'critical';
type NavTab    = 'home' | 'timeline' | 'deepdive' | 'monitoring';

// ── Design tokens ─────────────────────────────────────────────────────────────

const RISK_COLOR: Record<RiskState, string> = {
  critical: '#FF4444',
  warning:  '#F59E0B',
  stable:   '#22C55E',
};

const RISK_HALO: Record<RiskState, string> = {
  critical: 'radial-gradient(circle, rgba(255,68,68,0.18) 0%, transparent 70%)',
  warning:  'radial-gradient(circle, rgba(245,158,11,0.18) 0%, transparent 70%)',
  stable:   'radial-gradient(circle, rgba(34,197,94,0.18) 0%, transparent 70%)',
};

const CIRC = 2 * Math.PI * 80;
const EASE_APPLE: [number, number, number, number] = [0.16, 1, 0.3, 1];

// ── API config ────────────────────────────────────────────────────────────────

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

// ── Event label mapping ───────────────────────────────────────────────────────

const EVENT_LABELS: Record<string, string> = {
  symptom_report:   'Symptoms analyzed',
  agent_synthesis:  'DeepDive complete',
  lab_upload:       'Lab report uploaded',
  escalation:       'Escalation triggered',
  whatsapp_checkin: 'Checkpoint sent',
  resolution:       'Case resolved',
  medication_start: 'Medication started',
};

const AGENT_COLORS = ['#F87171', '#60A5FA', '#A78BFA', '#34D399', '#FBBF24'];

// ── Session + time helpers ────────────────────────────────────────────────────

function getActiveSession() {
  const params = new URLSearchParams(window.location.search);
  return {
    patientId: params.get('patient_id') || localStorage.getItem('cliniq_patient_id'),
    caseId:    params.get('case_id')    || localStorage.getItem('cliniq_active_case_id'),
  };
}

function relativeTime(iso: string): string {
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const h  = Math.floor(ms / 3_600_000);
    if (h < 1)  return `${Math.floor(ms / 60_000)}m ago`;
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  } catch {
    return '—';
  }
}

// ── Inline SVG icons ──────────────────────────────────────────────────────────

type IconProps = { color?: string; size?: number };

const HomeIcon   = ({ color = 'currentColor', size = 20 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <polyline points="9 22 9 12 15 12 15 22" />
  </svg>
);
const TimelineIcon = ({ color = 'currentColor', size = 20 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);
const DeepDiveIcon = ({ color = 'currentColor', size = 20 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="6" height="6" /><path d="M3 9h2M3 15h2M19 9h2M19 15h2M9 3v2M15 3v2M9 19v2M15 19v2" />
  </svg>
);
const MonitorIcon  = ({ color = 'currentColor', size = 20 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);
const ClockIcon    = ({ color = 'currentColor', size = 16 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
  </svg>
);
const ActivityIcon = ({ color = 'currentColor', size = 16 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);
const ShieldIcon   = ({ color = 'currentColor', size = 16 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);
const SparkleIcon  = ({ color = 'currentColor', size = 16 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
  </svg>
);

// ── Helper ────────────────────────────────────────────────────────────────────

function labColor(s: LabStatus): string {
  if (s === 'critical') return '#FF4444';
  if (s === 'warning')  return '#F59E0B';
  return 'rgba(255,255,255,0.7)';
}

// ── Right-column card ─────────────────────────────────────────────────────────

function RCard({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const [hov, setHov] = useState(false);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: EASE_APPLE, delay }}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background:            'rgba(255,255,255,0.025)',
        backdropFilter:        'blur(20px) saturate(140%)',
        WebkitBackdropFilter:  'blur(20px) saturate(140%)',
        border:                `1px solid ${hov ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.07)'}`,
        borderRadius:          14,
        padding:               '16px 18px',
        marginBottom:          12,
        boxShadow:             'inset 0 1px 0 rgba(255,255,255,0.06), 0 1px 3px rgba(0,0,0,0.3)',
        transition:            'border-color 150ms ease',
      }}
    >
      {children}
    </motion.div>
  );
}

// ── Card section heading row ──────────────────────────────────────────────────

function CardHeader({ icon, label, right }: { icon: React.ReactNode; label: string; right?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
      {icon}
      <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, flex: 1 }}>
        {label}
      </span>
      {right && <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', marginLeft: 'auto' }}>{right}</span>}
    </div>
  );
}

function CardDivider() {
  return <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', margin: '10px 0' }} />;
}

// ── Main page component ───────────────────────────────────────────────────────

interface PatientHomeProps {
  onNavigate?: (tab: string) => void;
}

export default function PatientHomePage({ onNavigate }: PatientHomeProps) {
  // ── Session ─────────────────────────────────────────────────────────────────
  const { patientId, caseId } = useMemo(() => getActiveSession(), []);
  const hasSession = Boolean(patientId && caseId);

  // ── Remote data ─────────────────────────────────────────────────────────────
  const [data, setData]       = useState<any>(null);
  const [loading, setLoading] = useState(hasSession); // true only when session exists

  useEffect(() => {
    if (!patientId || !caseId) return;
    Promise.all([
      fetch(`${BASE_URL}/api/patients/${patientId}/recovery-score`).then(r => r.json()),
      fetch(`${BASE_URL}/api/cases/${caseId}/monitoring-status`).then(r => r.json()),
      fetch(`${BASE_URL}/api/cases/${caseId}/timeline`).then(r => r.json()),
      fetch(`${BASE_URL}/api/v2/case/${caseId}`).then(r => r.json()),
    ])
      .then(([recovery, monitoring, timeline, caseData]) => {
        setData({ recovery, monitoring, timeline, caseData });
        setLoading(false);
      })
      .catch(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Nav ──────────────────────────────────────────────────────────────────────
  const [activeNav, setActiveNav] = useState<NavTab>('home');

  function handleNav(tab: NavTab) {
    setActiveNav(tab);
    if (tab === 'timeline' && onNavigate) onNavigate('timeline');
  }

  // ── Derive live values ───────────────────────────────────────────────────────
  const recovery   = data?.recovery;
  const monitoring = data?.monitoring;
  const timeline   = data?.timeline;
  const caseDetail = data?.caseData;

  const riskState: RiskState = (recovery?.risk_state as RiskState)  ?? 'warning';
  const riskPill:  RiskStatus = (recovery?.risk_state as RiskStatus) ?? 'warning';
  const score      = (recovery?.score as number) ?? 0;
  const ringOffset = CIRC * (1 - score / 100);
  const riskColor  = RISK_COLOR[riskState];

  const patientName = localStorage.getItem('cliniq_patient_name') ?? 'Patient';

  const hypotheses = ((caseDetail?.case?.diagnosis_hypotheses ?? []) as any[]);
  const topHypName = (hypotheses[0]?.name as string) ?? (caseDetail?.case?.chief_complaint as string) ?? '—';
  const topHypConf = hypotheses[0]?.confidence != null
    ? Math.round((hypotheses[0].confidence as number) * 100)
    : 0;

  const labReports   = (caseDetail?.lab_reports ?? []) as any[];
  const latestReport = labReports.length > 0 ? labReports[labReports.length - 1] : null;
  const labFlags     = (latestReport?.abnormal_flags ?? []) as any[];
  const labRows      = labFlags.slice(0, 4).map((f: any) => ({
    key:    String(f.marker ?? '').slice(0, 6),
    display:`${f.value ?? '—'}${f.direction === 'low' ? ' ↓' : f.direction === 'high' ? ' ↑' : ''}`,
    status: (f.severity === 'critical' ? 'critical' : 'warning') as LabStatus,
  }));
  const deepdiveRight = latestReport
    ? `${latestReport.report_type ?? 'Report'} · ${relativeTime(latestReport.uploaded_at ?? '')}`
    : '—';
  const primaryPattern = (latestReport?.deep_dive_output?.primary_finding
    ?? latestReport?.deep_dive_output?.primary_pattern
    ?? null) as string | null;

  const totalCP     = (monitoring?.total_checkpoints    ?? 0) as number;
  const completedCP = (monitoring?.completed_checkpoints ?? 0) as number;
  const checkpoints = Array.from({ length: totalCP }, (_: unknown, i: number) => i < completedCP);
  const currentCP   = completedCP < totalCP ? completedCP : Math.max(0, totalCP - 1);
  const nextCheckAt = monitoring?.next_checkpoint_at
    ? new Date(monitoring.next_checkpoint_at as string).toLocaleString('en-IN', {
        weekday: 'short', hour: '2-digit', minute: '2-digit',
      })
    : '—';

  const riskLabel  = riskState === 'stable' ? 'Low risk' : riskState === 'critical' ? 'Critical' : 'Moderate risk';
  const statusLine = monitoring?.active
    ? `${riskLabel} · Day ${monitoring.day_current} of ${monitoring.day_total}`
    : riskLabel;

  const agentLog = ((timeline?.events ?? []) as any[]).slice(0, 4).map((e: any, i: number) => ({
    name:   (e.agent_name as string) || 'Agent',
    color:  AGENT_COLORS[i % AGENT_COLORS.length],
    action: EVENT_LABELS[e.event_type as string] ?? (e.event_type as string)?.replace(/_/g, ' ') ?? '—',
    time:   relativeTime((e.created_at as string) ?? ''),
  }));

  // ── Score ring counter — fires when score becomes non-zero ──────────────────
  const scoreMotion = useMotionValue(0);
  const [displayScore, setDisplayScore] = useState(0);
  useMotionValueEvent(scoreMotion, 'change', (v) => setDisplayScore(Math.round(v)));

  useEffect(() => {
    if (score === 0) return;
    const t = setTimeout(() => {
      const ctrl = animate(scoreMotion, score, { duration: 1.4, ease: EASE_APPLE });
      return ctrl.stop;
    }, 600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [score]);

  const NAV_ITEMS: { id: NavTab; label: string; icon: (active: boolean) => React.ReactNode }[] = [
    { id: 'home',       label: 'Home',       icon: (a) => <HomeIcon   color={a ? 'var(--accent, #7C65F6)' : 'rgba(255,255,255,0.3)'} /> },
    { id: 'timeline',   label: 'Timeline',   icon: (a) => <TimelineIcon color={a ? 'var(--accent, #7C65F6)' : 'rgba(255,255,255,0.3)'} /> },
    { id: 'deepdive',   label: 'DeepDive',   icon: (a) => <DeepDiveIcon color={a ? 'var(--accent, #7C65F6)' : 'rgba(255,255,255,0.3)'} /> },
    { id: 'monitoring', label: 'Monitoring', icon: (a) => <MonitorIcon  color={a ? 'var(--accent, #7C65F6)' : 'rgba(255,255,255,0.3)'} /> },
  ];

  // ── No session ───────────────────────────────────────────────────────────────
  if (!hasSession && !loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#050507', position: 'relative', isolation: 'isolate' }}>
        <AmbientBackground glow="warning" />
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', gap: 8 }}>
          <p style={{ fontSize: 15, color: 'rgba(255,255,255,0.5)', fontWeight: 500, margin: 0 }}>
            No active patient session.
          </p>
          <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.25)', margin: 0 }}>
            Please start from the Analyze screen.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#050507', position: 'relative', isolation: 'isolate' }}>

      {/* ── Layers 2 + 3 — shared ambient background ──────────────────────── */}
      <AmbientBackground glow={riskState} />

      {/* ── All content sits above background ────────────────────────────── */}
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>

        {/* ── Topbar ───────────────────────────────────────────────────────── */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: EASE_APPLE, delay: 0.2 }}
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 50,
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            background: 'rgba(5,5,7,0.8)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
          }}
        >
          {/* Wordmark */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <motion.span
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              style={{ width: 5, height: 5, borderRadius: '50%', background: 'rgba(124,101,246,0.6)', display: 'inline-block', flexShrink: 0 }}
            />
            <span style={{ fontFamily: 'Inter Variable, Inter, sans-serif', fontWeight: 600, fontSize: 15, color: '#9B87FF', letterSpacing: '-0.3px' }}>
              ClinIQ
            </span>
          </div>
          {/* Patient + risk state */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', fontWeight: 500 }}>
              {loading ? 'Loading…' : patientName}
            </span>
            <RiskPill status={riskPill} />
          </div>
        </motion.header>

        {/* ── Two-column content ────────────────────────────────────────────── */}
        <main style={{ flex: 1, display: 'flex', flexWrap: 'wrap', paddingBottom: 80 }}>

          {/* ── LEFT COLUMN — Recovery ring ──────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: EASE_APPLE, delay: 0.4 }}
            style={{
              flex: '0 0 55%',
              minWidth: 300,
              padding: '32px 24px 32px 40px',
            }}
          >
            {/* Ring container */}
            <div style={{ position: 'relative', width: 200, height: 200, marginBottom: 28 }}>

              {/* Halo */}
              <motion.div
                animate={{ opacity: [0.7, 1.0], scale: [1, 1.04] }}
                transition={{ duration: 4, ease: 'easeInOut', repeat: Infinity, repeatType: 'mirror' }}
                style={{
                  position: 'absolute',
                  width: 260,
                  height: 260,
                  top: -30,
                  left: -30,
                  borderRadius: '50%',
                  background: RISK_HALO[riskState],
                  pointerEvents: 'none',
                }}
              />

              {/* SVG Ring */}
              <motion.svg
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, delay: 0.4 }}
                width="200" height="200"
                viewBox="0 0 200 200"
                style={{ position: 'relative', zIndex: 1 }}
              >
                <defs>
                  <linearGradient id="ring-grad" gradientUnits="userSpaceOnUse" x1="20" y1="100" x2="180" y2="100">
                    <stop offset="0%" stopColor="#9B87FF" />
                    <stop offset="100%" stopColor={riskColor} />
                  </linearGradient>
                </defs>

                {/* Track */}
                <circle
                  cx="100" cy="100" r="80"
                  fill="none"
                  stroke="rgba(255,255,255,0.05)"
                  strokeWidth="12"
                />

                {/* Glow duplicate */}
                <motion.circle
                  cx="100" cy="100" r="80"
                  fill="none"
                  stroke={riskColor}
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeDasharray={CIRC}
                  initial={{ strokeDashoffset: CIRC }}
                  animate={{ strokeDashoffset: ringOffset }}
                  transition={{ duration: 1.4, ease: EASE_APPLE, delay: 0.6 }}
                  transform="rotate(-90 100 100)"
                  style={{ filter: 'blur(6px)', opacity: 0.35 }}
                />

                {/* Progress arc */}
                <motion.circle
                  cx="100" cy="100" r="80"
                  fill="none"
                  stroke="url(#ring-grad)"
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeDasharray={CIRC}
                  initial={{ strokeDashoffset: CIRC }}
                  animate={{ strokeDashoffset: ringOffset }}
                  transition={{ duration: 1.4, ease: EASE_APPLE, delay: 0.6 }}
                  transform="rotate(-90 100 100)"
                />
              </motion.svg>

              {/* Center content */}
              <div style={{
                position: 'absolute', inset: 0, zIndex: 2,
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{
                  fontFamily:          'JetBrains Mono, Fira Code, monospace',
                  fontSize:            52,
                  fontWeight:          700,
                  letterSpacing:       '-2px',
                  lineHeight:          1,
                  fontVariantNumeric:  'tabular-nums',
                  background:          `linear-gradient(135deg, #ffffff 0%, ${riskColor} 100%)`,
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip:      'text',
                  color:               '#ffffff',
                }}>
                  {loading ? '--' : displayScore}
                </span>
                <span style={{
                  fontSize:      11,
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  color:         'rgba(255,255,255,0.3)',
                  marginTop:     4,
                  fontWeight:    500,
                }}>
                  Recovery
                </span>
              </div>
            </div>

            {/* Status line */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
              <RiskPill status={riskPill} />
              <span style={{ fontSize: 14, color: 'var(--text-secondary, #8B8B99)' }}>
                {loading ? 'Loading…' : statusLine}
              </span>
            </div>

            {/* Diagnosis hypothesis */}
            <div style={{ marginBottom: 24 }}>
              <span style={{ display: 'block', fontSize: 11, color: 'var(--text-muted, #4A4A5A)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 5 }}>
                Primary hypothesis
              </span>
              <span style={{ display: 'block', fontSize: 17, color: 'var(--text-primary, #F0F0F4)', fontWeight: 600, letterSpacing: '-0.3px', marginBottom: 8 }}>
                {loading ? 'Loading…' : topHypName}
              </span>
              {/* Confidence bar */}
              <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                <motion.div
                  initial={{ width: '0%' }}
                  animate={{ width: loading ? '0%' : `${topHypConf}%` }}
                  transition={{ duration: 1.0, ease: EASE_APPLE, delay: 0.8 }}
                  style={{ height: '100%', borderRadius: 2, background: riskColor }}
                />
              </div>
              <span style={{ display: 'block', fontSize: 11, color: 'var(--text-muted, #4A4A5A)', marginTop: 4 }}>
                {loading ? '…' : topHypConf > 0 ? `${topHypConf}% confidence` : '—'}
              </span>
            </div>

            {/* Next checkpoint */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ClockIcon color="rgba(255,255,255,0.25)" />
                <span style={{ fontSize: 14, color: 'var(--text-secondary, #8B8B99)' }}>
                  {loading ? 'Loading…' : `Next: ${nextCheckAt}`}
                </span>
              </div>
              <span style={{ fontSize: 14, color: 'var(--text-muted, #4A4A5A)', paddingLeft: 22 }}>
                {loading
                  ? '…'
                  : `${monitoring?.protocol_name ?? '—'} · Day ${monitoring?.day_current ?? '—'}`
                }
              </span>
            </div>
          </motion.div>

          {/* ── RIGHT COLUMN — Intelligence surface ──────────────────────── */}
          <div style={{ flex: '0 0 45%', minWidth: 280, padding: '32px 40px 32px 24px' }}>

            {/* Card 1 — Last DeepDive */}
            <RCard delay={0.8}>
              <CardHeader
                icon={<ActivityIcon color="var(--accent, #7C65F6)" />}
                label="Last DeepDive"
                right={loading ? '…' : deepdiveRight}
              />
              <CardDivider />
              {/* Lab values 2-column grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px' }}>
                {loading ? (
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)', gridColumn: '1/-1' }}>
                    Loading…
                  </span>
                ) : labRows.length > 0 ? labRows.map(({ key, display, status }) => (
                  <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', fontWeight: 500 }}>{key}</span>
                    <span style={{
                      fontFamily:          'JetBrains Mono, monospace',
                      fontSize:            12,
                      fontWeight:          500,
                      fontVariantNumeric:  'tabular-nums',
                      color:               labColor(status),
                    }}>
                      {display}
                    </span>
                  </div>
                )) : (
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)', gridColumn: '1/-1' }}>
                    No lab reports yet
                  </span>
                )}
              </div>
              {!loading && (primaryPattern || labRows.length > 0) && (
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent, #7C65F6)', display: 'inline-block', flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: 'var(--accent-bright, #9B87FF)', fontWeight: 500 }}>
                    {primaryPattern ?? 'Analysis complete'}
                  </span>
                </div>
              )}
            </RCard>

            {/* Card 2 — Monitoring protocol progress */}
            <RCard delay={0.86}>
              <CardHeader
                icon={<ShieldIcon color="var(--stable, #22C55E)" />}
                label="Monitoring"
                right={loading ? '…' : (monitoring?.protocol_name ?? '—')}
              />
              {/* Checkpoint dots */}
              {loading ? (
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)', margin: '12px 0 8px' }}>
                  Loading…
                </div>
              ) : totalCP > 0 ? (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '12px 0 8px' }}>
                  {checkpoints.map((done, i) => {
                    const isCurrent = i === currentCP && !done;
                    return (
                      <div key={i} style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {isCurrent && (
                          <motion.div
                            animate={{ scale: [1, 1.5, 1], opacity: [0.6, 0, 0.6] }}
                            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                            style={{
                              position: 'absolute',
                              width: 14,
                              height: 14,
                              borderRadius: '50%',
                              border: '1px solid var(--accent, #7C65F6)',
                            }}
                          />
                        )}
                        <div style={{
                          width:        isCurrent ? 10 : 8,
                          height:       isCurrent ? 10 : 8,
                          borderRadius: '50%',
                          background:   done
                            ? 'var(--stable, #22C55E)'
                            : isCurrent
                              ? 'var(--accent, #7C65F6)'
                              : 'rgba(255,255,255,0.1)',
                          boxShadow:    isCurrent ? '0 0 8px rgba(124,101,246,0.5)' : 'none',
                          transition:   'background 0.3s',
                        }} />
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)', margin: '12px 0 8px' }}>
                  No active monitoring plan
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)' }}>
                  {loading
                    ? 'Loading…'
                    : totalCP > 0
                      ? `${completedCP} of ${totalCP} checkpoints · ${totalCP - completedCP} remaining`
                      : '—'
                  }
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-secondary, #8B8B99)' }}>
                  {loading ? '…' : `Next: ${nextCheckAt}`}
                </span>
              </div>
            </RCard>

            {/* Card 3 — Agent activity */}
            <RCard delay={0.92}>
              <CardHeader
                icon={<SparkleIcon color="var(--accent-bright, #9B87FF)" />}
                label="Agent Activity"
                right={<StatusOrb live size={8} />}
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {loading ? (
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)' }}>Loading…</span>
                ) : agentLog.length > 0 ? agentLog.map((entry, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: entry.color, flexShrink: 0, minWidth: 90 }}>
                      {entry.name}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary, #8B8B99)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.action}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted, #4A4A5A)', flexShrink: 0 }}>
                      {entry.time}
                    </span>
                  </div>
                )) : (
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)' }}>No recent activity</span>
                )}
              </div>
              <div style={{ marginTop: 10 }}>
                <span style={{
                  fontSize: 12,
                  color: 'var(--accent-bright, #9B87FF)',
                  fontWeight: 500,
                  cursor: 'pointer',
                  letterSpacing: '-0.1px',
                }}>
                  View all activity →
                </span>
              </div>
            </RCard>

          </div>
        </main>

        {/* ── Bottom Nav ────────────────────────────────────────────────────── */}
        <nav style={{
          position:           'fixed',
          bottom:             0,
          left:               0,
          right:              0,
          zIndex:             50,
          height:             64,
          paddingBottom:      'env(safe-area-inset-bottom)',
          background:         'rgba(5,5,7,0.85)',
          backdropFilter:     'blur(24px) saturate(160%)',
          WebkitBackdropFilter: 'blur(24px) saturate(160%)',
          borderTop:          '1px solid rgba(255,255,255,0.05)',
          display:            'flex',
        }}>
          {NAV_ITEMS.map((item) => {
            const active = activeNav === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNav(item.id)}
                style={{
                  flex:           1,
                  display:        'flex',
                  flexDirection:  'column',
                  alignItems:     'center',
                  justifyContent: 'center',
                  gap:            4,
                  background:     'none',
                  border:         'none',
                  cursor:         'pointer',
                  position:       'relative',
                  padding:        '8px 0 0',
                  outline:        'none',
                }}
              >
                {active && (
                  <motion.div
                    layoutId="nav-indicator"
                    style={{
                      position:     'absolute',
                      top:          0,
                      left:         '50%',
                      transform:    'translateX(-50%)',
                      width:        20,
                      height:       2,
                      borderRadius: 1,
                      background:   'var(--accent, #7C65F6)',
                    }}
                    transition={{ duration: 0.22, ease: EASE_APPLE }}
                  />
                )}
                {item.icon(active)}
                {active && (
                  <motion.span
                    initial={{ opacity: 0, y: 2 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ fontSize: 10, color: 'var(--accent, #7C65F6)', fontWeight: 600, letterSpacing: '0.02em' }}
                  >
                    {item.label}
                  </motion.span>
                )}
              </button>
            );
          })}
        </nav>

      </div>
    </div>
  );
}
