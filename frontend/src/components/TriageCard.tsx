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
  gradient: string;
  label: string;
  sub: string;
  pulse: boolean;
  Icon: () => React.ReactElement;
}> = {
  EMERGENCY: {
    gradient: 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)',
    label: 'Emergency',
    sub: 'Seek immediate emergency care',
    pulse: true,
    Icon: EmergencyIcon,
  },
  URGENT: {
    gradient: 'linear-gradient(135deg, #ea580c 0%, #c2410c 100%)',
    label: 'Urgent',
    sub: 'See a doctor today',
    pulse: false,
    Icon: UrgentIcon,
  },
  ROUTINE: {
    gradient: 'linear-gradient(135deg, #16a34a 0%, #0d9488 100%)',
    label: 'Routine',
    sub: 'Schedule an appointment when convenient',
    pulse: false,
    Icon: RoutineIcon,
  },
  INFORMATIONAL: {
    gradient: 'linear-gradient(135deg, #2563eb 0%, #4f46e5 100%)',
    label: 'Informational',
    sub: 'General health information',
    pulse: false,
    Icon: InfoIcon,
  },
};

export default function TriageCard({ triage, message, cached }: Props) {
  const level = triage?.toUpperCase() || 'INFORMATIONAL';
  const config = triageConfig[level] || triageConfig.INFORMATIONAL;
  const { Icon } = config;

  return (
    <div
      className="w-full rounded-2xl p-6 text-white relative overflow-hidden shadow-xl animate-fade-in-up"
      style={{ background: config.gradient }}
    >
      <div className="absolute -right-10 -top-10 w-44 h-44 rounded-full opacity-10 bg-white" />
      <div className="absolute -right-4 -bottom-10 w-32 h-32 rounded-full opacity-10 bg-white" />

      <div className="relative flex items-start justify-between gap-4">
        <div className="flex items-center gap-5">
          <div className="relative shrink-0">
            {config.pulse && (
              <>
                <div
                  className="absolute inset-0 rounded-full bg-white opacity-30"
                  style={{ animation: 'pulse-ring 1.4s ease-out infinite' }}
                />
                <div
                  className="absolute inset-0 rounded-full bg-white opacity-20"
                  style={{ animation: 'pulse-ring 1.4s ease-out infinite 0.5s' }}
                />
              </>
            )}
            <div className="relative w-14 h-14 bg-white/20 rounded-2xl flex items-center justify-center backdrop-blur-sm border border-white/30">
              <Icon />
            </div>
          </div>

          <div>
            <div className="text-xs font-bold uppercase tracking-widest opacity-70 mb-0.5">
              Triage Level
            </div>
            <div className="text-3xl font-extrabold tracking-tight leading-none">
              {config.label}
            </div>
            <div className="text-sm opacity-85 mt-1.5 font-medium">
              {message || config.sub}
            </div>
          </div>
        </div>

        {cached && (
          <div className="shrink-0">
            <span className="inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-sm text-white text-xs font-bold px-3 py-1.5 rounded-full border border-white/30">
              From memory
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
