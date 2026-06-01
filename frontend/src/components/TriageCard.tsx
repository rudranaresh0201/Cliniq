import React from 'react';

interface Props {
  triage: string;
  message?: string;
  cached: boolean;
}

function EmergencyIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function UrgentIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function RoutineIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

const triageConfig: Record<string, {
  borderColor: string;
  glowColor: string;
  iconBg: string;
  accentGradient: string;
  label: string;
  sub: string;
  pulse: boolean;
  Icon: () => React.ReactElement;
}> = {
  // v1 triage levels
  EMERGENCY: {
    borderColor: 'rgba(239,68,68,0.4)',
    glowColor: 'rgba(239,68,68,0.2)',
    iconBg: 'rgba(239,68,68,0.25)',
    accentGradient: 'linear-gradient(135deg, #ef4444, #b91c1c)',
    label: 'Emergency',
    sub: 'Seek immediate emergency care',
    pulse: true,
    Icon: EmergencyIcon,
  },
  URGENT: {
    borderColor: 'rgba(255,149,0,0.4)',
    glowColor: 'rgba(255,149,0,0.15)',
    iconBg: 'rgba(255,149,0,0.2)',
    accentGradient: 'linear-gradient(135deg, #FF9500, #FF6B00)',
    label: 'Urgent',
    sub: 'See a doctor today',
    pulse: false,
    Icon: UrgentIcon,
  },
  ROUTINE: {
    borderColor: 'rgba(6,214,160,0.4)',
    glowColor: 'rgba(6,214,160,0.12)',
    iconBg: 'rgba(6,214,160,0.18)',
    accentGradient: 'linear-gradient(135deg, #06D6A0, #059669)',
    label: 'Routine',
    sub: 'Schedule an appointment when convenient',
    pulse: false,
    Icon: RoutineIcon,
  },
  INFORMATIONAL: {
    borderColor: 'rgba(124,58,237,0.4)',
    glowColor: 'rgba(124,58,237,0.12)',
    iconBg: 'rgba(124,58,237,0.18)',
    accentGradient: 'linear-gradient(135deg, #7C3AED, #5B21B6)',
    label: 'Informational',
    sub: 'General health information',
    pulse: false,
    Icon: InfoIcon,
  },
  // v2 risk_tier levels
  CRITICAL: {
    borderColor: 'rgba(239,68,68,0.4)',
    glowColor: 'rgba(239,68,68,0.2)',
    iconBg: 'rgba(239,68,68,0.25)',
    accentGradient: 'linear-gradient(135deg, #ef4444, #b91c1c)',
    label: 'Critical',
    sub: 'Seek immediate emergency care',
    pulse: true,
    Icon: EmergencyIcon,
  },
  HIGH: {
    borderColor: 'rgba(255,149,0,0.4)',
    glowColor: 'rgba(255,149,0,0.15)',
    iconBg: 'rgba(255,149,0,0.2)',
    accentGradient: 'linear-gradient(135deg, #FF9500, #FF6B00)',
    label: 'High Risk',
    sub: 'See a doctor today',
    pulse: false,
    Icon: UrgentIcon,
  },
  MODERATE: {
    borderColor: 'rgba(234,179,8,0.4)',
    glowColor: 'rgba(234,179,8,0.12)',
    iconBg: 'rgba(234,179,8,0.18)',
    accentGradient: 'linear-gradient(135deg, #EAB308, #CA8A04)',
    label: 'Moderate',
    sub: 'Schedule an appointment soon',
    pulse: false,
    Icon: UrgentIcon,
  },
  LOW: {
    borderColor: 'rgba(6,214,160,0.4)',
    glowColor: 'rgba(6,214,160,0.12)',
    iconBg: 'rgba(6,214,160,0.18)',
    accentGradient: 'linear-gradient(135deg, #06D6A0, #059669)',
    label: 'Low Risk',
    sub: 'Monitor your symptoms',
    pulse: false,
    Icon: RoutineIcon,
  },
};

export default function TriageCard({ triage, message, cached }: Props) {
  const level = triage?.toUpperCase() || 'INFORMATIONAL';
  const config = triageConfig[level] || triageConfig.INFORMATIONAL;
  const { Icon } = config;

  return (
    <div
      className="w-full rounded-2xl p-6 text-white relative overflow-hidden animate-fade-in-up"
      style={{
        background: '#0F1623',
        border: `1px solid ${config.borderColor}`,
        boxShadow: `0 0 40px ${config.glowColor}, inset 0 1px 0 rgba(255,255,255,0.06)`,
      }}
    >
      {/* Decorative orb */}
      <div
        className="absolute -right-16 -top-16 w-48 h-48 rounded-full pointer-events-none"
        style={{
          background: `radial-gradient(circle, ${config.glowColor} 0%, transparent 70%)`,
        }}
      />

      {/* Top accent bar */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{ background: config.accentGradient, opacity: 0.8 }}
      />

      <div className="relative flex items-start justify-between gap-4">
        <div className="flex items-center gap-5">
          <div className="relative shrink-0">
            {config.pulse && (
              <>
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    background: config.iconBg,
                    animation: 'pulse-ring 1.4s ease-out infinite',
                  }}
                />
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    background: config.iconBg,
                    animation: 'pulse-ring 1.4s ease-out infinite 0.5s',
                  }}
                />
              </>
            )}
            <div
              className="relative w-14 h-14 rounded-2xl flex items-center justify-center"
              style={{
                background: config.iconBg,
                border: `1px solid ${config.borderColor}`,
                backdropFilter: 'blur(10px)',
              }}
            >
              <Icon />
            </div>
          </div>

          <div>
            <div className="text-xs font-bold uppercase tracking-widest mb-0.5" style={{ color: 'rgba(255,255,255,0.45)' }}>
              Triage Level
            </div>
            <div
              className="text-3xl font-extrabold tracking-tight leading-none"
              style={{ fontFamily: 'Sora, sans-serif' }}
            >
              {config.label}
            </div>
            <div className="text-sm mt-1.5 font-medium" style={{ color: 'rgba(255,255,255,0.7)' }}>
              {message || config.sub}
            </div>
          </div>
        </div>

        {cached && (
          <div className="shrink-0">
            <span
              className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full"
              style={{
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: 'rgba(255,255,255,0.6)',
              }}
            >
              From memory
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
