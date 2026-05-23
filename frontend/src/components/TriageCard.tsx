interface Props {
  triage: string;
  message?: string;
  cached: boolean;
}

const triageConfig: Record<string, {
  gradient: string;
  border: string;
  icon: string;
  label: string;
  sub: string;
  pulse: boolean;
}> = {
  EMERGENCY: {
    gradient: 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)',
    border: '#fca5a5',
    icon: '🚨',
    label: 'Emergency',
    sub: 'Seek immediate emergency care',
    pulse: true,
  },
  URGENT: {
    gradient: 'linear-gradient(135deg, #ea580c 0%, #c2410c 100%)',
    border: '#fdba74',
    icon: '⚠️',
    label: 'Urgent',
    sub: 'See a doctor today',
    pulse: false,
  },
  ROUTINE: {
    gradient: 'linear-gradient(135deg, #16a34a 0%, #0d9488 100%)',
    border: '#86efac',
    icon: '✅',
    label: 'Routine',
    sub: 'Schedule an appointment when convenient',
    pulse: false,
  },
  INFORMATIONAL: {
    gradient: 'linear-gradient(135deg, #2563eb 0%, #4f46e5 100%)',
    border: '#93c5fd',
    icon: 'ℹ️',
    label: 'Informational',
    sub: 'General health information',
    pulse: false,
  },
};

export default function TriageCard({ triage, message, cached }: Props) {
  const level = triage?.toUpperCase() || 'INFORMATIONAL';
  const config = triageConfig[level] || triageConfig.INFORMATIONAL;

  return (
    <div
      className="w-full rounded-2xl p-6 text-white relative overflow-hidden shadow-xl animate-fade-in-up"
      style={{ background: config.gradient }}
    >
      {/* Decorative circles */}
      <div className="absolute -right-10 -top-10 w-44 h-44 rounded-full opacity-10 bg-white" />
      <div className="absolute -right-4 -bottom-10 w-32 h-32 rounded-full opacity-10 bg-white" />

      <div className="relative flex items-start justify-between gap-4">
        <div className="flex items-center gap-5">
          {/* Icon with optional pulse ring */}
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
              <span className="text-3xl">{config.icon}</span>
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
              ⚡ From memory
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
