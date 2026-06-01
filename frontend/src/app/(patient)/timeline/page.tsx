import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  staggerContainer,
  staggerItem,
  EASE_OUT,
  CSS_ANIM,
  fadeIn,
} from '../../../lib/motion';
import { AmbientBackground } from '../../../components/AmbientBackground';

// ── Types ──────────────────────────────────────────────────────────────────────

type EventType   = 'symptom' | 'lab' | 'deepdive' | 'escalation' | 'milestone' | 'monitoring';
type FilterType  = 'all' | 'labs' | 'deepdive' | 'escalations' | 'symptoms' | 'monitoring';
type LabStatus   = 'normal' | 'warning' | 'critical';

interface BaseEvent    { id: string; time: string; day: string; dayLabel: string }
interface SymptomEvent extends BaseEvent { type: 'symptom';    symptoms: string[] }
interface LabEvent     extends BaseEvent { type: 'lab';        reportType: string; values: { key: string; val: string; status: LabStatus }[] }
interface DeepDiveEvent extends BaseEvent { type: 'deepdive'; specialist: string; findings: string[]; patterns: string[] }
interface EscalationEvent extends BaseEvent { type: 'escalation'; reason: string; action: string }
interface MilestoneEvent extends BaseEvent { type: 'milestone'; description: string }
interface MonitoringEvent extends BaseEvent { type: 'monitoring'; note: string; vitals: { key: string; val: string }[] }

type TimelineEvent =
  | SymptomEvent | LabEvent | DeepDiveEvent
  | EscalationEvent | MilestoneEvent | MonitoringEvent;

interface DayGroup { day: string; dayLabel: string; events: TimelineEvent[] }

// ── API ────────────────────────────────────────────────────────────────────────

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

// ── API → internal type adapters ──────────────────────────────────────────────
// Real response field names: id, event_type, payload, created_at, agent_name

function _fmtTime(iso: string): string {
  try { return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }); }
  catch { return '—'; }
}

function _fmtDay(iso: string): string {
  try { return new Date(iso).toDateString(); }
  catch { return 'Unknown'; }
}

function _fmtDayLabel(iso: string): string {
  try { return new Date(iso).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }); }
  catch { return '—'; }
}

function adaptEvent(raw: any): TimelineEvent | null {
  const base = {
    id:       String(raw.id ?? ''),
    time:     _fmtTime(raw.created_at ?? ''),
    day:      _fmtDay(raw.created_at ?? ''),
    dayLabel: _fmtDayLabel(raw.created_at ?? ''),
  };
  const p: any = raw.payload ?? {};

  switch (raw.event_type) {
    case 'symptom_report': {
      const extracted: string[] = Array.isArray(p.symptoms_extracted) ? p.symptoms_extracted : [];
      const symptoms = extracted.length > 0
        ? extracted
        : p.top_diagnosis
          ? [`Hypothesis: ${p.top_diagnosis} (${Math.round((p.top_confidence ?? 0) * 100)}%)`]
          : ['Symptoms recorded'];
      return { ...base, type: 'symptom', symptoms };
    }

    case 'lab_upload': {
      const riskStatus: LabStatus =
        p.risk_level === 'critical' ? 'critical' :
        p.risk_level === 'high'     ? 'warning'  : 'normal';
      const values: LabEvent['values'] = [
        p.report_type                  && { key: 'Type',     val: String(p.report_type),    status: 'normal' as LabStatus },
        p.abnormal_count != null       && { key: 'Abnormal', val: String(p.abnormal_count), status: p.abnormal_count > 0 ? 'warning' as LabStatus : 'normal' as LabStatus },
        p.risk_level                   && { key: 'Risk',     val: String(p.risk_level),     status: riskStatus },
        p.primary_finding              && { key: 'Finding',  val: String(p.primary_finding).substring(0, 30), status: riskStatus },
      ].filter(Boolean) as LabEvent['values'];
      return { ...base, type: 'lab', reportType: String(p.report_type ?? 'Report'), values };
    }

    case 'agent_synthesis': {
      const preview: string = String(p.synthesis_preview ?? p.primary_finding ?? '');
      const cleaned = preview.replace(/\*\*/g, '').trim();
      const findings = cleaned ? [cleaned.substring(0, 280)] : ['Analysis complete'];
      const tools: string[] = Array.isArray(p.tools_executed) ? p.tools_executed : [];
      const patterns = tools.slice(0, 3).map((t: string) => t.replace(/_/g, ' '));
      return { ...base, type: 'deepdive', specialist: String(raw.agent_name || 'Agent'), findings, patterns };
    }

    case 'escalation': {
      return {
        ...base, type: 'escalation',
        reason: String(p.trigger_reason ?? p.reason ?? 'Escalation triggered'),
        action: String(p.severity      ?? p.action ?? 'Medical review required'),
      };
    }

    case 'whatsapp_checkin':
    case 'medication_start': {
      return {
        ...base, type: 'monitoring',
        note:   String(p.note ?? p.summary ?? (raw.event_type as string).replace(/_/g, ' ')),
        vitals: [],
      };
    }

    case 'resolution': {
      return {
        ...base, type: 'milestone',
        description: String(p.description ?? p.reason ?? 'Case resolved'),
      };
    }

    default:
      return null;
  }
}

// ── Filter config ─────────────────────────────────────────────────────────────

const FILTERS: { id: FilterType; label: string }[] = [
  { id: 'all',         label: 'All'        },
  { id: 'labs',        label: 'Labs'       },
  { id: 'deepdive',    label: 'DeepDive'   },
  { id: 'escalations', label: 'Escalations'},
  { id: 'symptoms',    label: 'Symptoms'   },
  { id: 'monitoring',  label: 'Monitoring' },
];

const FILTER_TYPES: Record<FilterType, EventType[]> = {
  all:         ['symptom', 'lab', 'deepdive', 'escalation', 'milestone', 'monitoring'],
  labs:        ['lab'],
  deepdive:    ['deepdive'],
  escalations: ['escalation'],
  symptoms:    ['symptom'],
  monitoring:  ['monitoring', 'milestone'],
};

// ── Shared inline SVG icons ────────────────────────────────────────────────────

const ChevronIcon = ({ open }: { open: boolean }) => (
  <motion.svg
    width={14} height={14} viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth={2}
    strokeLinecap="round" strokeLinejoin="round"
    animate={{ rotate: open ? 180 : 0 }}
    transition={{ duration: 0.22, ease: EASE_OUT }}
  >
    <polyline points="6 9 12 15 18 9" />
  </motion.svg>
);

const CheckIcon = () => (
  <svg width={8} height={8} viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <polyline points="1.5 5 4 7.5 8.5 2.5" />
  </svg>
);

const SparkIcon = () => (
  <motion.svg
    width={16} height={16} viewBox="0 0 24 24"
    fill="none" stroke="var(--stable, #22C55E)" strokeWidth={1.75}
    strokeLinecap="round" strokeLinejoin="round"
    animate={{ rotate: [0, 12, -12, 0], scale: [1, 1.15, 1] }}
    transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
  >
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
    <path d="M19 3l.7 2L21 6l-1.3.7L19 8.5l-.7-1.8L17 6l1.3-.7L19 3z" />
  </motion.svg>
);

// ── Helpers ────────────────────────────────────────────────────────────────────

function labColor(s: LabStatus): string {
  if (s === 'critical') return 'var(--critical, #FF4444)';
  if (s === 'warning')  return 'var(--warning, #F59E0B)';
  return 'rgba(255,255,255,0.7)';
}

function groupByDay(events: TimelineEvent[]): DayGroup[] {
  const map = new Map<string, DayGroup>();
  for (const e of events) {
    if (!map.has(e.day)) map.set(e.day, { day: e.day, dayLabel: e.dayLabel, events: [] });
    map.get(e.day)!.events.push(e);
  }
  return Array.from(map.values());
}

// ── Spine node ─────────────────────────────────────────────────────────────────

function SpineNode({ type }: { type: EventType }) {
  const large = type === 'escalation' || type === 'milestone';
  const size  = large ? 12 : 8;
  const offset = 10 - size / 2; // center on 10px spine axis

  const bg =
    type === 'escalation' ? 'var(--critical, #FF4444)' :
    type === 'milestone'  ? 'var(--stable, #22C55E)'   :
    'var(--bg-elevated, #14141A)';

  return (
    <div
      className={type === 'escalation' ? CSS_ANIM.glowPulse.className : undefined}
      style={{
        position: 'absolute',
        left: offset,
        top: 18,
        width: size,
        height: size,
        borderRadius: '50%',
        background: bg,
        border: large ? 'none' : '1px solid var(--border-default, rgba(255,255,255,0.08))',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 3,
        boxShadow: type === 'escalation' ? '0 0 10px rgba(255,68,68,0.5)' : 'none',
      }}
    >
      {type === 'milestone' && <CheckIcon />}
    </div>
  );
}

// ── Date separator ─────────────────────────────────────────────────────────────

function DateSeparator({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '20px 0 10px', paddingLeft: 36 }}>
      <div style={{ flex: 1, height: 1, background: 'var(--border-subtle, rgba(255,255,255,0.04))' }} />
      <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted, #4A4A5A)', fontWeight: 600, whiteSpace: 'nowrap' }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 1, background: 'var(--border-subtle, rgba(255,255,255,0.04))' }} />
    </div>
  );
}

// ── Card base styles (shared) ──────────────────────────────────────────────────

const CARD_BASE: React.CSSProperties = {
  background:           'var(--bg-glass, rgba(15,15,20,0.6))',
  backdropFilter:       'blur(20px) saturate(180%)',
  WebkitBackdropFilter: 'blur(20px) saturate(180%)',
  border:               '1px solid var(--border-subtle, rgba(255,255,255,0.04))',
  borderRadius:         14,
  overflow:             'hidden',
};

function CardTimestamp({ time }: { time: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 999,
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.06)',
      fontSize: 11,
      color: 'var(--text-muted, #4A4A5A)',
      fontWeight: 500,
      letterSpacing: '0.05em',
      flexShrink: 0,
    }}>
      {time}
    </span>
  );
}

function CardLabel({ text }: { text: string }) {
  return (
    <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted, #4A4A5A)' }}>
      {text}
    </span>
  );
}

// ── SymptomCard ────────────────────────────────────────────────────────────────

function SymptomCard({ event }: { event: SymptomEvent }) {
  return (
    <motion.div variants={staggerItem} style={{ ...CARD_BASE, borderLeft: '3px solid var(--warning, #F59E0B)', marginBottom: 10 }}>
      <div style={{ padding: '13px 15px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <CardLabel text="Symptoms Reported" />
          <CardTimestamp time={event.time} />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {event.symptoms.map((s) => (
            <span key={s} style={{
              padding: '4px 10px',
              borderRadius: 999,
              background: 'rgba(245,158,11,0.1)',
              border: '1px solid rgba(245,158,11,0.25)',
              color: 'var(--warning, #F59E0B)',
              fontSize: 12,
              fontWeight: 500,
              backdropFilter: 'blur(8px)',
            }}>
              {s}
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

// ── LabCard ────────────────────────────────────────────────────────────────────

function LabCard({ event }: { event: LabEvent }) {
  return (
    <motion.div variants={staggerItem} style={{ ...CARD_BASE, borderLeft: '3px solid var(--accent, #7C65F6)', marginBottom: 10 }}>
      <div style={{ padding: '13px 15px 14px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <CardLabel text="Lab Uploaded" />
            <span style={{
              padding: '2px 8px', borderRadius: 999,
              background: 'rgba(124,101,246,0.12)',
              border: '1px solid rgba(124,101,246,0.3)',
              color: 'var(--accent-bright, #9B87FF)',
              fontSize: 11, fontWeight: 600,
            }}>
              {event.reportType}
            </span>
          </div>
          <CardTimestamp time={event.time} />
        </div>
        {/* Values grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 24px', marginBottom: 10 }}>
          {event.values.map(({ key, val, status }) => (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', fontWeight: 500 }}>{key}</span>
              <span style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 12, fontWeight: 500,
                fontVariantNumeric: 'tabular-nums',
                color: labColor(status),
              }}>
                {val}
              </span>
            </div>
          ))}
        </div>
        <button style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 13, color: 'var(--text-accent, #9B87FF)', fontWeight: 500 }}>
          View Report →
        </button>
      </div>
    </motion.div>
  );
}

// ── DeepDiveCard (expandable) ──────────────────────────────────────────────────

function DeepDiveCard({ event }: { event: DeepDiveEvent }) {
  const [open, setOpen] = useState(false);

  return (
    <motion.div
      variants={staggerItem}
      layout
      style={{
        ...CARD_BASE,
        borderLeft: '3px solid transparent',
        backgroundImage: 'linear-gradient(var(--bg-glass, rgba(15,15,20,0.6)), var(--bg-glass, rgba(15,15,20,0.6))), linear-gradient(180deg, var(--accent, #7C65F6), var(--accent-bright, #9B87FF))',
        backgroundOrigin: 'border-box',
        backgroundClip: 'padding-box, border-box',
        boxShadow: '0 0 40px var(--accent-glow, rgba(124,101,246,0.15)), inset 0 1px 0 rgba(124,101,246,0.1)',
        marginBottom: 10,
      }}
    >
      <div style={{ padding: '13px 15px 14px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <CardLabel text="DeepDive Complete" />
            <span style={{
              padding: '2px 8px', borderRadius: 999,
              background: 'rgba(124,101,246,0.12)',
              border: '1px solid rgba(124,101,246,0.25)',
              color: 'var(--accent-bright, #9B87FF)',
              fontSize: 11, fontWeight: 600,
            }}>
              {event.specialist}
            </span>
          </div>
          <CardTimestamp time={event.time} />
        </div>

        {/* Top 2 findings (always visible) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
          {event.findings.slice(0, 2).map((f, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent, #7C65F6)', marginTop: 6, flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: 'var(--text-secondary, #8B8B99)', lineHeight: 1.5 }}>{f}</span>
            </div>
          ))}
        </div>

        {/* Pattern chips */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {event.patterns.map((p) => (
            <span key={p} style={{
              padding: '3px 10px', borderRadius: 999,
              background: 'rgba(124,101,246,0.1)',
              border: '1px solid rgba(124,101,246,0.25)',
              color: 'var(--accent-bright, #9B87FF)',
              fontSize: 11, fontWeight: 500,
              backdropFilter: 'blur(8px)',
            }}>
              {p}
            </span>
          ))}
        </div>

        {/* Expand toggle */}
        {event.findings.length > 2 && (
          <button
            onClick={() => setOpen((v) => !v)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'none', border: 'none', padding: 0,
              cursor: 'pointer', color: 'rgba(255,255,255,0.25)',
              fontSize: 12, fontWeight: 500,
            }}
          >
            <ChevronIcon open={open} />
            {open ? 'Collapse' : 'Full analysis'}
          </button>
        )}

        {/* Expanded panel */}
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: open ? 'auto' : 0, opacity: open ? 1 : 0 }}
          transition={{ duration: 0.3, ease: EASE_OUT }}
          style={{ overflow: 'hidden' }}
        >
          <div style={{ paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.05)', marginTop: 12 }}>
            {event.findings.slice(2).map((f, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8 }}>
                <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent, #7C65F6)', marginTop: 6, flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: 'var(--text-secondary, #8B8B99)', lineHeight: 1.5 }}>{f}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

// ── EscalationCard ─────────────────────────────────────────────────────────────

function EscalationCard({ event }: { event: EscalationEvent }) {
  return (
    <motion.div variants={staggerItem} style={{ position: 'relative', marginBottom: 10 }}>
      {/* Ambient red glow behind card */}
      <div style={{
        position: 'absolute', inset: -12, borderRadius: 18,
        background: 'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(255,68,68,0.08) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />

      {/* Urgent bar above card */}
      <div style={{ height: 2, background: 'var(--critical, #FF4444)', borderRadius: '2px 2px 0 0', position: 'relative', zIndex: 1 }} />

      <div style={{
        ...CARD_BASE,
        borderRadius: '0 0 14px 14px',
        border: '1px solid var(--critical, #FF4444)',
        boxShadow: '0 0 40px var(--critical-glow, rgba(255,68,68,0.2)), inset 0 1px 0 rgba(255,68,68,0.1)',
        position: 'relative', zIndex: 1,
      }}>
        <div style={{ padding: '13px 15px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            {/* URGENT badge */}
            <motion.span
              className={CSS_ANIM.glowPulse.className}
              style={{
                padding: '3px 10px', borderRadius: 999,
                background: 'rgba(255,68,68,0.15)',
                border: '1px solid rgba(255,68,68,0.5)',
                color: 'var(--critical, #FF4444)',
                fontSize: 10, fontWeight: 800, letterSpacing: '0.12em',
                textTransform: 'uppercase',
              }}
            >
              URGENT
            </motion.span>
            <CardTimestamp time={event.time} />
          </div>
          <p style={{ margin: '0 0 8px', fontSize: 14, fontWeight: 600, color: 'var(--text-primary, #F0F0F4)', lineHeight: 1.45 }}>
            {event.reason}
          </p>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary, #8B8B99)', lineHeight: 1.5 }}>
            {event.action}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

// ── MilestoneCard ──────────────────────────────────────────────────────────────

function MilestoneCard({ event }: { event: MilestoneEvent }) {
  return (
    <motion.div variants={staggerItem} style={{ ...CARD_BASE, borderLeft: '3px solid var(--stable, #22C55E)', boxShadow: '0 0 40px var(--stable-glow, rgba(34,197,94,0.2)), inset 0 1px 0 rgba(34,197,94,0.1)', marginBottom: 10 }}>
      <div style={{ padding: '13px 15px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SparkIcon />
            <CardLabel text="Milestone" />
          </div>
          <CardTimestamp time={event.time} />
        </div>
        <p style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary, #8B8B99)', lineHeight: 1.55 }}>
          {event.description}
        </p>
      </div>
    </motion.div>
  );
}

// ── MonitoringCard ─────────────────────────────────────────────────────────────

function MonitoringCard({ event }: { event: MonitoringEvent }) {
  return (
    <motion.div variants={staggerItem} style={{ ...CARD_BASE, borderLeft: '3px solid rgba(124,101,246,0.5)', marginBottom: 10 }}>
      <div style={{ padding: '13px 15px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <CardLabel text="Monitoring" />
          <CardTimestamp time={event.time} />
        </div>
        <p style={{ margin: '0 0 10px', fontSize: 13, color: 'var(--text-secondary, #8B8B99)' }}>{event.note}</p>
        {event.vitals.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px' }}>
            {event.vitals.map(({ key, val }) => (
              <span key={key} style={{ fontSize: 12 }}>
                <span style={{ color: 'rgba(255,255,255,0.3)', marginRight: 4 }}>{key}</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontVariantNumeric: 'tabular-nums', color: 'rgba(255,255,255,0.7)', fontWeight: 500 }}>{val}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ── Card dispatch ──────────────────────────────────────────────────────────────

function CardByType({ event }: { event: TimelineEvent }) {
  switch (event.type) {
    case 'symptom':    return <SymptomCard    event={event} />;
    case 'lab':        return <LabCard        event={event} />;
    case 'deepdive':   return <DeepDiveCard   event={event} />;
    case 'escalation': return <EscalationCard event={event} />;
    case 'milestone':  return <MilestoneCard  event={event} />;
    case 'monitoring': return <MonitoringCard event={event} />;
  }
}

// ── Filter bar ─────────────────────────────────────────────────────────────────

function FilterBar({ active, onSelect }: { active: FilterType; onSelect: (f: FilterType) => void }) {
  return (
    <div style={{
      position: 'sticky',
      top: 0,
      zIndex: 40,
      background: 'rgba(5,5,7,0.85)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(255,255,255,0.05)',
      overflowX: 'auto',
      scrollbarWidth: 'none',
    }}>
      <div style={{ display: 'flex', gap: 4, padding: '10px 16px', minWidth: 'max-content' }}>
        {FILTERS.map((f) => {
          const isActive = active === f.id;
          return (
            <button
              key={f.id}
              onClick={() => onSelect(f.id)}
              style={{
                position: 'relative',
                padding: '6px 14px',
                borderRadius: 999,
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                color: isActive ? 'var(--text-primary, #F0F0F4)' : 'var(--text-muted, #4A4A5A)',
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                transition: 'color 150ms ease',
                outline: 'none',
                flexShrink: 0,
              }}
            >
              {isActive && (
                <motion.div
                  layoutId="filter-pill"
                  transition={{ duration: 0.22, ease: EASE_OUT }}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    borderRadius: 999,
                    background: 'rgba(124,101,246,0.1)',
                    border: '1px solid var(--accent, #7C65F6)',
                    boxShadow: '0 0 12px var(--accent-glow, rgba(124,101,246,0.15))',
                  }}
                />
              )}
              <span style={{ position: 'relative', zIndex: 1 }}>{f.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Timeline list (handles grouping, stagger, filter-switch animation) ─────────

const rememberedScrollY = { current: 0 };

function TimelineList({ filter, events, loading }: { filter: FilterType; events: TimelineEvent[]; loading: boolean }) {
  const allowed  = FILTER_TYPES[filter];
  const filtered = events.filter((e) => (allowed as string[]).includes(e.type));
  const groups   = groupByDay(filtered);

  if (loading) {
    return (
      <div style={{ padding: '48px 16px', textAlign: 'center' }}>
        <p style={{ color: 'rgba(255,255,255,0.2)', fontSize: 14, margin: 0 }}>Loading timeline…</p>
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div style={{ padding: '48px 16px', textAlign: 'center' }}>
        <p style={{ color: 'rgba(255,255,255,0.2)', fontSize: 14, margin: 0 }}>No events to show.</p>
      </div>
    );
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      style={{ position: 'relative', padding: '8px 16px 32px' }}
    >
      {/* Spine vertical line */}
      <div style={{
        position: 'absolute',
        left: 25,
        top: 0,
        bottom: 0,
        width: 1,
        background: 'rgba(255,255,255,0.06)',
        pointerEvents: 'none',
        zIndex: 0,
      }} />

      {groups.flatMap((group) => [
        <DateSeparator key={`sep-${group.day}`} label={group.dayLabel} />,
        ...group.events.map((event) => (
          <div key={event.id} style={{ position: 'relative', paddingLeft: 36 }}>
            <SpineNode type={event.type} />
            <CardByType event={event} />
          </div>
        )),
      ])}
    </motion.div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function TimelinePage() {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const scrollRef = useRef<HTMLDivElement>(null);

  // ── Remote data ───────────────────────────────────────────────────────────
  const [events, setEvents]   = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const caseId = new URLSearchParams(window.location.search).get('case_id')
      || localStorage.getItem('cliniq_active_case_id');

    if (!caseId) { setLoading(false); return; }

    fetch(`${BASE_URL}/api/cases/${caseId}/timeline`)
      .then(r => r.json())
      .then((data: any) => {
        const adapted = ((data.events ?? []) as any[])
          .map(adaptEvent)
          .filter((e): e is TimelineEvent => e !== null);
        setEvents(adapted);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Persist scroll position across tab switches (module-level ref survives remount)
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = rememberedScrollY.current;
    const save = () => { rememberedScrollY.current = el.scrollTop; };
    el.addEventListener('scroll', save, { passive: true });
    return () => el.removeEventListener('scroll', save);
  }, []);

  // Reset scroll to top on filter change
  const handleFilter = (f: FilterType) => {
    setActiveFilter(f);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  };

  return (
    <motion.div
      variants={fadeIn}
      initial="hidden"
      animate="visible"
      style={{ minHeight: '100vh', background: '#050507', display: 'flex', flexDirection: 'column', position: 'relative', isolation: 'isolate' }}
    >
      <AmbientBackground glow="warning" />
      <FilterBar active={activeFilter} onSelect={handleFilter} />

      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'none', position: 'relative', zIndex: 1 }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={activeFilter}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12, ease: 'linear' }}
          >
            <TimelineList filter={activeFilter} events={events} loading={loading} />
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
