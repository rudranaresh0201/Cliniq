// ClinIQ 2.0 — Console  (desktop-first, min 1280px)
// Mission control: live escalation feed + case workspace + agent activity

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GlassCard, RiskPill, AgentMessage, StatusOrb } from '../../components/primitives';
import type { RiskStatus, AgentType } from '../../components/primitives';
import { AmbientBackground } from '../../components/AmbientBackground';
import {
  EASE_OUT,
  scaleInSpring,
  cardHover,
  buttonTap,
  staggerFast,
  staggerItem,
} from '../../lib/motion';
import { supabase } from '../../lib/supabase-client';

// ── Types ──────────────────────────────────────────────────────────────────────

interface ConsoleTimelineEvent {
  id: string;
  type: 'symptom' | 'lab' | 'deepdive' | 'escalation' | 'milestone' | 'monitoring';
  time: string;
  summary: string;
  severity?: 'critical' | 'warning' | 'stable';
}

interface ConsoleAgent {
  id: string;
  agent: AgentType;
  action: string;
  finding: string;
  timestamp: string;
}

interface ConsoleCase {
  id: string;
  patient: { name: string; age: number; location: string; initials: string };
  escalation: { reason: string; timeAgo: string; severity: 'critical' | 'warning' };
  diagnoses: { label: string; status: RiskStatus }[];
  day: number;
  agents: ConsoleAgent[];
  timeline: ConsoleTimelineEvent[];
}

interface PaletteItem {
  id: string;
  category: string;
  label: string;
  sub: string;
  shortcut: string;
}

// ── API config ─────────────────────────────────────────────────────────────────

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

// Static palette — Actions only (no hardcoded patient names)
const PALETTE_ITEMS: PaletteItem[] = [
  { id: 'a1', category: 'Actions', label: 'Run DeepDive',           sub: '',  shortcut: '⌘D' },
  { id: 'a2', category: 'Actions', label: 'Acknowledge Escalation', sub: '',  shortcut: '⌘A' },
  { id: 'a3', category: 'Actions', label: 'Upload Lab Report',      sub: '',  shortcut: '⌘U' },
];

// ── Adapters — map real API shapes to ConsoleCase / ConsoleAgent types ─────────

function _relTime(iso: string): string {
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const m  = Math.floor(ms / 60_000);
    if (m < 1)  return 'Just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  } catch { return '—'; }
}

function _initials(name: string): string {
  const p = name.trim().split(/\s+/);
  return p.length >= 2
    ? (p[0][0] + p[p.length - 1][0]).toUpperCase()
    : name.substring(0, 2).toUpperCase();
}

// Map free-text agent_name → AgentType enum (fallback: WatchWorker)
function _toAgentType(name: string): AgentType {
  const n = (name ?? '').toLowerCase();
  if (n.includes('deepdive') || n.includes('cbc_interpreter') || n.includes('lft_interpreter') || n.includes('rft_interpreter')) return 'DeepDive';
  if (n.includes('cbc'))       return 'CBC';
  if (n.includes('lft'))       return 'LFT';
  if (n.includes('rft'))       return 'RFT';
  if (n.includes('cross'))     return 'CrossAnalyzer';
  if (n.includes('watch'))     return 'WatchWorker';
  if (n.includes('monitor'))   return 'MonitoringAgent';
  if (n.includes('escalation') || n.includes('alert')) return 'EscalationAgent';
  return 'WatchWorker';
}

// Adapt /api/console/escalations item → ConsoleCase (timeline + agents empty until case selected)
function adaptEscalation(raw: any): ConsoleCase {
  const sex = raw.patient_sex ? String(raw.patient_sex).charAt(0).toUpperCase() + String(raw.patient_sex).slice(1) : '';
  return {
    id:       String(raw.case_id ?? raw.id ?? ''),
    patient:  {
      name:     String(raw.patient_name ?? 'Unknown'),
      age:      Number(raw.patient_age  ?? 0),
      location: sex,
      initials: _initials(String(raw.patient_name ?? 'UN')),
    },
    escalation: {
      reason:  String(raw.trigger_reason ?? ''),
      timeAgo: _relTime(raw.created_at  ?? ''),
      severity: raw.severity === 'critical' ? 'critical' : 'warning',
    },
    diagnoses: [{
      label:  String(raw.trigger_reason ?? raw.severity ?? 'Alert').split('—')[0].trim().substring(0, 30),
      status: (raw.severity === 'critical' ? 'critical' : 'warning') as RiskStatus,
    }],
    day:      Number(raw.case_day ?? 0),
    agents:   [],   // populated on case selection
    timeline: [],   // populated on case selection
  };
}

// Adapt real timeline event → ConsoleTimelineEvent
function adaptTimelineEvent(raw: any): ConsoleTimelineEvent {
  const typeMap: Record<string, ConsoleTimelineEvent['type']> = {
    symptom_report:   'symptom',
    lab_upload:       'lab',
    agent_synthesis:  'deepdive',
    escalation:       'escalation',
    resolution:       'milestone',
    whatsapp_checkin: 'monitoring',
    medication_start: 'monitoring',
  };
  const type = typeMap[raw.event_type as string] ?? 'monitoring';
  const p    = raw.payload ?? {};
  const rawSummary =
    p.primary_finding
    ?? p.trigger_reason
    ?? (p.synthesis_preview ? String(p.synthesis_preview).replace(/\*\*/g, '').trim().substring(0, 80) : null)
    ?? String(raw.event_type ?? '').replace(/_/g, ' ');

  const sev: ConsoleTimelineEvent['severity'] =
    type === 'escalation' ? 'critical' :
    type === 'lab'        ? 'warning'  : undefined;

  return {
    id:       String(raw.id ?? ''),
    type,
    time:     _relTime(raw.created_at ?? ''),
    summary:  String(rawSummary).trim(),
    severity: sev,
  };
}

// Adapt /api/console/agent-activity item → ConsoleAgent
function adaptActivity(raw: any): ConsoleAgent {
  return {
    id:        String(raw.id ?? ''),
    agent:     _toAgentType(String(raw.agent_name ?? '')),
    action:    String(raw.action   ?? ''),
    finding:   String(raw.finding  ?? ''),
    timestamp: _relTime(raw.created_at ?? ''),
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function timelineAccent(e: ConsoleTimelineEvent): string {
  if (e.type === 'escalation') return e.severity === 'critical' ? 'var(--critical, #FF4444)' : 'var(--warning, #F59E0B)';
  if (e.type === 'milestone')  return 'var(--stable, #22C55E)';
  if (e.type === 'deepdive')   return 'var(--accent, #7C65F6)';
  if (e.severity === 'critical') return 'var(--critical, #FF4444)';
  if (e.severity === 'warning')  return 'var(--warning, #F59E0B)';
  return 'rgba(255,255,255,0.12)';
}

// ── Command bar ────────────────────────────────────────────────────────────────

function CommandBar({ onPaletteOpen }: { onPaletteOpen: () => void }) {
  const doctorName = localStorage.getItem('cliniq_doctor_name') ?? 'Doctor';
  const initials   = _initials(doctorName);

  return (
    <div style={{
      height: 52, flexShrink: 0,
      background: 'rgba(15,15,20,0.8)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(255,255,255,0.05)',
      display: 'flex', alignItems: 'center',
      padding: '0 20px', gap: 16,
      position: 'relative', zIndex: 40,
    }}>
      {/* Wordmark */}
      <span style={{
        fontFamily: 'Inter Variable, Inter, sans-serif',
        fontWeight: 700, fontSize: 15, flexShrink: 0,
        background: 'linear-gradient(135deg, #9B87FF, #7C65F6)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
      }}>
        ClinIQ
      </span>

      {/* Search pill (center) */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <motion.button
          onClick={onPaletteOpen}
          whileHover={{ borderColor: 'rgba(124,101,246,0.4)' }}
          style={{
            width: 240, height: 32,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 999,
            display: 'flex', alignItems: 'center',
            padding: '0 10px 0 12px', gap: 8,
            cursor: 'pointer',
            transition: 'border-color 150ms ease',
          }}
        >
          <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span style={{ flex: 1, fontSize: 13, color: 'rgba(255,255,255,0.25)', textAlign: 'left' }}>
            Search patients, cases…
          </span>
          <span style={{ padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.06)', fontSize: 10, color: 'rgba(255,255,255,0.25)', fontWeight: 500, flexShrink: 0 }}>
            ⌘K
          </span>
        </motion.button>
      </div>

      {/* Right: Dr name + orb + avatar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', fontWeight: 500 }}>{doctorName}</span>
        <StatusOrb live size={10} />
        <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'rgba(124,101,246,0.2)', border: '1px solid rgba(124,101,246,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: 'var(--accent-bright, #9B87FF)' }}>
          {initials}
        </div>
      </div>
    </div>
  );
}

// ── Command palette ────────────────────────────────────────────────────────────

function CommandPalette({ onClose }: { onClose: () => void }) {
  const [query, setQuery]   = useState('');
  const [hilite, setHilite] = useState(0);
  const inputRef            = useRef<HTMLInputElement>(null);

  const filtered = PALETTE_ITEMS.filter((item) =>
    !query || item.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape')    { onClose(); return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); setHilite((i) => Math.min(i + 1, filtered.length - 1)); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setHilite((i) => Math.max(i - 1, 0)); }
      if (e.key === 'Enter')     { onClose(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, filtered.length]);

  const categories = Array.from(new Set(filtered.map((i) => i.category)));
  let flatIdx = 0;

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <motion.div
        variants={scaleInSpring}
        initial="hidden"
        animate="visible"
        exit="exit"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 600,
          background: 'rgba(15,15,20,0.92)',
          backdropFilter: 'blur(32px) saturate(180%)',
          WebkitBackdropFilter: 'blur(32px) saturate(180%)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 18,
          boxShadow: '0 32px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06)',
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setHilite(0); }}
            placeholder="Search patients, cases, actions…"
            style={{ flex: 1, background: 'none', border: 'none', outline: 'none', fontSize: 18, color: 'var(--text-primary, #F0F0F4)', fontFamily: 'inherit' }}
          />
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.2)', padding: '2px 6px', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4 }}>esc</span>
        </div>

        <div style={{ maxHeight: 360, overflowY: 'auto', padding: '8px 0' }}>
          {categories.map((cat) => (
            <div key={cat}>
              <div style={{ padding: '6px 18px 3px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'rgba(255,255,255,0.2)' }}>
                {cat}
              </div>
              {filtered.filter((i) => i.category === cat).map((item) => {
                const idx = flatIdx++;
                const isHilite = hilite === idx;
                return (
                  <div
                    key={item.id}
                    onClick={onClose}
                    style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 18px', background: isHilite ? 'var(--bg-hover, #1F1F2C)' : 'transparent', cursor: 'pointer', transition: 'background 80ms ease' }}
                  >
                    <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth={2} strokeLinecap="round">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" />
                      </svg>
                    </div>
                    <div style={{ flex: 1 }}>
                      <span style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text-primary, #F0F0F4)' }}>{item.label}</span>
                      {item.sub && <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>{item.sub}</span>}
                    </div>
                    <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.2)', padding: '2px 6px', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 4, flexShrink: 0 }}>
                      {item.shortcut}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ── Escalation card ────────────────────────────────────────────────────────────

function EscalationCard({
  c, isSelected, isNew, isPulsing, onClick,
}: {
  c: ConsoleCase; isSelected: boolean; isNew: boolean; isPulsing: boolean; onClick: () => void;
}) {
  const isCrit = c.escalation.severity === 'critical';

  return (
    <motion.div
      initial={isNew ? { y: -40, opacity: 0 } : false}
      animate={{ y: 0, opacity: 1 }}
      transition={isNew ? { type: 'spring', stiffness: 320, damping: 26 } : {}}
      onClick={onClick}
      whileHover={isSelected ? {} : cardHover}
      style={{ marginBottom: 8, position: 'relative', cursor: 'pointer' }}
    >
      {isSelected && (
        <motion.div
          layoutId="selected-esc-border"
          transition={{ duration: 0.22, ease: EASE_OUT }}
          style={{ position: 'absolute', inset: -1, borderRadius: 17, border: '1.5px solid var(--accent, #7C65F6)', pointerEvents: 'none', zIndex: 5 }}
        />
      )}
      <GlassCard
        glow={isSelected ? 'accent' : isCrit ? 'critical' : 'warning'}
        style={{
          borderLeft: `3px solid ${isSelected ? 'var(--accent, #7C65F6)' : isCrit ? 'var(--critical, #FF4444)' : 'var(--warning, #F59E0B)'}`,
          padding: '12px 14px',
          transition: 'border-left-color 220ms ease',
          animation: isPulsing ? 'esc-border-pulse 1.5s ease-in-out 2' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary, #F0F0F4)', letterSpacing: '-0.2px' }}>
            {c.patient.name}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted, #4A4A5A)', flexShrink: 0, marginLeft: 8 }}>
            {c.escalation.timeAgo}
          </span>
        </div>
        <p style={{ margin: '0 0 10px', fontSize: 13, color: 'var(--text-secondary, #8B8B99)', lineHeight: 1.45 }}>
          {c.escalation.reason}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <RiskPill status={c.escalation.severity} />
          <span style={{ fontSize: 12, color: 'var(--text-muted, #4A4A5A)' }}>Day {c.day}</span>
        </div>
      </GlassCard>
    </motion.div>
  );
}

// ── Left panel — escalation feed ───────────────────────────────────────────────

function EscalationFeed({
  cases, loading, selectedId, pulsingCards, newCaseIds, onSelect,
}: {
  cases: ConsoleCase[];
  loading: boolean;
  selectedId: string;
  pulsingCards: Set<string>;
  newCaseIds: Set<string>;
  onSelect: (id: string) => void;
}) {
  const critCount = cases.filter((c) => c.escalation.severity === 'critical').length;

  return (
    <div style={{ width: '38%', borderRight: '1px solid var(--border-subtle, rgba(255,255,255,0.04))', display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 16px 12px', flexShrink: 0, borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary, #F0F0F4)' }}>Escalations</span>
          {critCount > 0 && (
            <motion.span
              animate={{ opacity: [1, 0.5, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              style={{ padding: '1px 8px', borderRadius: 999, background: 'rgba(255,68,68,0.15)', border: '1px solid rgba(255,68,68,0.4)', fontSize: 11, fontWeight: 700, color: 'var(--critical, #FF4444)' }}
            >
              {critCount}
            </motion.span>
          )}
          <StatusOrb live size={8} />
        </div>
        <p style={{ margin: '3px 0 0', fontSize: 11, color: 'var(--text-muted, #4A4A5A)' }}>
          Ranked by severity · Live
        </p>
      </div>

      {/* Feed */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px', scrollbarWidth: 'none' }}>
        {loading ? (
          // Loading placeholders — same height as escalation cards
          <>
            {[0, 1].map((i) => (
              <div key={i} style={{ height: 90, borderRadius: 16, background: 'rgba(255,255,255,0.03)', marginBottom: 8 }} />
            ))}
          </>
        ) : cases.length === 0 ? (
          <div style={{ paddingTop: 48, textAlign: 'center' }}>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.3)', fontWeight: 500, margin: 0 }}>No active escalations</p>
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.15)', margin: '6px 0 0' }}>All patients stable</p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {cases.map((c) => (
              <EscalationCard
                key={c.id}
                c={c}
                isSelected={selectedId === c.id}
                isNew={newCaseIds.has(c.id)}
                isPulsing={pulsingCards.has(c.id)}
                onClick={() => onSelect(c.id)}
              />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}

// ── Col 1 — Patient meta ───────────────────────────────────────────────────────

function PatientMetaColumn({ c }: { c: ConsoleCase }) {
  return (
    <div style={{ width: '25%', borderRight: '1px solid rgba(255,255,255,0.04)', padding: '16px 14px', overflowY: 'auto', scrollbarWidth: 'none' }}>
      <GlassCard style={{ padding: '16px', marginBottom: 10 }}>
        {/* Avatar */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'rgba(124,101,246,0.12)', border: '1px solid rgba(124,101,246,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 700, color: 'var(--accent-bright, #9B87FF)', marginBottom: 8 }}>
            {c.patient.initials}
          </div>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary, #F0F0F4)', letterSpacing: '-0.2px' }}>{c.patient.name}</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted, #4A4A5A)' }}>
            {c.patient.age}{c.patient.location ? ` · ${c.patient.location}` : ''}
          </span>
        </div>

        {/* Diagnoses */}
        <div style={{ marginBottom: 12 }}>
          <span style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'rgba(255,255,255,0.2)', marginBottom: 6 }}>Active Diagnoses</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {c.diagnoses.map((d) => <RiskPill key={d.label} status={d.status} />)}
          </div>
        </div>

        {/* Protocol progress */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>Protocol Day</span>
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'rgba(255,255,255,0.5)', fontVariantNumeric: 'tabular-nums' }}>{c.day}/7</span>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
            <motion.div
              key={c.id}
              initial={{ width: 0 }}
              animate={{ width: `${(c.day / 7) * 100}%` }}
              transition={{ duration: 0.6, ease: EASE_OUT }}
              style={{ height: '100%', borderRadius: 2, background: 'var(--accent, #7C65F6)' }}
            />
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          <motion.button
            whileTap={buttonTap}
            style={{ flex: 1, padding: '7px 0', borderRadius: 8, background: 'transparent', border: '1px solid var(--accent, #7C65F6)', cursor: 'pointer', fontSize: 12, fontWeight: 600, color: 'var(--accent-bright, #9B87FF)' }}
          >
            Call
          </motion.button>
          <motion.button
            whileTap={buttonTap}
            style={{ flex: 1, padding: '7px 0', borderRadius: 8, background: 'var(--stable, #22C55E)', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, color: 'white' }}
          >
            Acknowledge
          </motion.button>
        </div>
      </GlassCard>
    </div>
  );
}

// ── Col 2 — Case timeline (compact) ───────────────────────────────────────────

function TimelineEventRow({ event }: { event: ConsoleTimelineEvent }) {
  const accent = timelineAccent(event);
  return (
    <motion.div variants={staggerItem} style={{ marginBottom: 8, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: accent, marginTop: 5, flexShrink: 0, boxShadow: `0 0 6px ${accent}66` }} />
      <div style={{ flex: 1, padding: '9px 12px', borderRadius: 10, background: 'rgba(255,255,255,0.025)', border: `1px solid rgba(255,255,255,0.06)`, borderLeft: `3px solid ${accent}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'rgba(255,255,255,0.6)', textTransform: 'capitalize' }}>{event.type}</span>
          <span style={{ fontSize: 10, color: 'var(--text-muted, #4A4A5A)', flexShrink: 0, marginLeft: 8 }}>{event.time}</span>
        </div>
        <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-secondary, #8B8B99)', lineHeight: 1.4 }}>{event.summary}</p>
      </div>
    </motion.div>
  );
}

function CaseTimelineColumn({ c, loading }: { c: ConsoleCase; loading: boolean }) {
  return (
    <div style={{ width: '45%', borderRight: '1px solid rgba(255,255,255,0.04)', padding: '16px 12px', overflowY: 'auto', scrollbarWidth: 'none', maxHeight: 'calc(100vh - 52px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'rgba(255,255,255,0.3)' }}>Case Timeline</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted, #4A4A5A)' }}>{c.patient.name}</span>
      </div>
      {loading ? (
        <div style={{ paddingTop: 24 }}>
          {[0, 1, 2].map((i) => (
            <div key={i} style={{ height: 56, borderRadius: 10, background: 'rgba(255,255,255,0.03)', marginBottom: 8 }} />
          ))}
        </div>
      ) : c.timeline.length === 0 ? (
        <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)', margin: '24px 0 0', textAlign: 'center' }}>No timeline events yet.</p>
      ) : (
        <motion.div variants={staggerFast} initial="hidden" animate="visible" key={c.id}>
          {c.timeline.map((event) => (
            <TimelineEventRow key={event.id} event={event} />
          ))}
        </motion.div>
      )}
    </div>
  );
}

// ── Col 3 — Agent activity ─────────────────────────────────────────────────────

function AgentActivityColumn({ agents }: { agents: ConsoleAgent[] }) {
  return (
    <div style={{ width: '30%', padding: '16px 12px', overflowY: 'auto', scrollbarWidth: 'none', maxHeight: 'calc(100vh - 52px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'rgba(255,255,255,0.3)', flex: 1 }}>Agent Activity</span>
        <StatusOrb live size={8} />
      </div>

      {agents.length === 0 ? (
        <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)', margin: '24px 0 0', textAlign: 'center' }}>No agent activity yet.</p>
      ) : (
        <motion.div
          variants={staggerFast}
          initial="hidden"
          animate="visible"
          key={agents[0]?.id ?? 'empty'}
          style={{ display: 'flex', flexDirection: 'column' }}
        >
          <AnimatePresence>
            {agents.map((msg) => (
              <motion.div
                key={msg.id}
                variants={staggerItem}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                style={{ marginBottom: 10 }}
              >
                <AgentMessage
                  agent={msg.agent}
                  action={msg.action}
                  finding={msg.finding}
                  timestamp={msg.timestamp}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}

// ── Case workspace ─────────────────────────────────────────────────────────────

function CaseWorkspace({ c, timelineLoading }: { c: ConsoleCase; timelineLoading: boolean }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={c.id}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.1 }}
        style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}
      >
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.22, delay: 0.1 }}
          style={{ display: 'flex', flex: 1 }}
        >
          <PatientMetaColumn c={c} />
          <CaseTimelineColumn c={c} loading={timelineLoading} />
          <AgentActivityColumn agents={c.agents} />
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ── Empty workspace (no selection) ────────────────────────────────────────────

function EmptyWorkspace() {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.2)', margin: 0 }}>
        Select an escalation to view case timeline
      </p>
    </div>
  );
}

// ── Keyframe injection ─────────────────────────────────────────────────────────

const CONSOLE_CSS = `
  @keyframes esc-border-pulse {
    0%, 100% { border-left-color: var(--critical, #FF4444); box-shadow: none; }
    40%, 60% { border-left-color: #FF6666; box-shadow: -4px 0 16px rgba(255,68,68,0.4); }
  }
`;

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ConsolePage() {
  const [cases, setCases]               = useState<ConsoleCase[]>([]);
  const [loading, setLoading]           = useState(true);
  const [selectedId, setSelectedId]     = useState<string>('');
  const [selectedTimeline, setSelectedTimeline] = useState<ConsoleTimelineEvent[]>([]);
  const [caseActivity, setCaseActivity] = useState<ConsoleAgent[]>([]);
  const [timelineLoading, setTimelineLoading]   = useState(false);
  const [paletteOpen, setPaletteOpen]   = useState(false);
  const [pulsingCards, setPulsingCards] = useState<Set<string>>(new Set());
  const [newCaseIds, setNewCaseIds]     = useState<Set<string>>(new Set());

  // Derive selected case: base escalation data + fetched timeline + fetched activity
  const baseCase    = cases.find((c) => c.id === selectedId) ?? null;
  const selectedCase: ConsoleCase | null = baseCase
    ? { ...baseCase, timeline: selectedTimeline, agents: caseActivity }
    : null;

  // ── Select a case: fetch its timeline + filtered activity ─────────────────
  const handleSelectCase = async (caseId: string) => {
    setSelectedId(caseId);
    setTimelineLoading(true);
    try {
      const [tlRes, actRes] = await Promise.all([
        fetch(`${BASE_URL}/api/cases/${caseId}/timeline`).then((r) => r.json()),
        fetch(`${BASE_URL}/api/console/agent-activity?case_id=${caseId}`).then((r) => r.json()),
      ]);
      setSelectedTimeline((tlRes.events ?? []).map(adaptTimelineEvent));
      setCaseActivity((actRes.activity ?? []).map(adaptActivity));
    } catch (err) {
      console.error('Case load failed:', err);
      setSelectedTimeline([]);
      setCaseActivity([]);
    } finally {
      setTimelineLoading(false);
    }
  };

  // ── Initial load: escalations + global agent activity ────────────────────
  useEffect(() => {
    Promise.all([
      fetch(`${BASE_URL}/api/console/escalations`).then((r) => r.json()),
      fetch(`${BASE_URL}/api/console/agent-activity`).then((r) => r.json()),
    ])
      .then(([escData, actData]) => {
        const escs = (escData.escalations ?? []).map(adaptEscalation);
        setCases(escs);
        // Pre-populate global activity (replaced per-case on selection)
        setCaseActivity((actData.activity ?? []).map(adaptActivity));
        // Auto-select first escalation
        if (escs.length > 0) {
          handleSelectCase(escs[0].id);
        } else {
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Console fetch failed:', err);
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Clear loading after first case selection completes
  useEffect(() => {
    if (!timelineLoading && selectedId) setLoading(false);
  }, [timelineLoading, selectedId]);

  // ── Supabase Realtime: escalations + agent_activity ───────────────────────
  useEffect(() => {
    const escChannel = supabase
      .channel('console-escalations')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'escalations' },
        (payload) => {
          const newCase = adaptEscalation(payload.new);
          setCases((prev) => [newCase, ...prev]);
          setNewCaseIds((prev) => new Set([...prev, newCase.id]));
          setPulsingCards(new Set([newCase.id]));
          setTimeout(() => setPulsingCards(new Set()), 3200);
        }
      )
      .subscribe();

    const actChannel = supabase
      .channel('console-activity')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'agent_activity' },
        (payload) => {
          const newMsg = adaptActivity(payload.new);
          setCaseActivity((prev) => [newMsg, ...prev]);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(escChannel);
      supabase.removeChannel(actChannel);
    };
  }, []);

  // ── Cmd+K shortcut ────────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div style={{ height: '100vh', background: '#050507', display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative', isolation: 'isolate' }}>
      <style>{CONSOLE_CSS}</style>
      <AmbientBackground glow="critical" />

      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
        <CommandBar onPaletteOpen={() => setPaletteOpen(true)} />

        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', background: 'var(--bg-surface, #0F0F14)' }}>
          <EscalationFeed
            cases={cases}
            loading={loading}
            selectedId={selectedId}
            pulsingCards={pulsingCards}
            newCaseIds={newCaseIds}
            onSelect={handleSelectCase}
          />
          {selectedCase ? (
            <CaseWorkspace c={selectedCase} timelineLoading={timelineLoading} />
          ) : (
            <EmptyWorkspace />
          )}
        </div>
      </div>

      <AnimatePresence>
        {paletteOpen && (
          <CommandPalette key="palette" onClose={() => setPaletteOpen(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}
