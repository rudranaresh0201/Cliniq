interface Props {
  triage: string;
  message?: string;
  cached: boolean;
}

const triageConfig: Record<string, { bg: string; icon: string; label: string; sub: string }> = {
  EMERGENCY: {
    bg: '#DC2626',
    icon: '🚨',
    label: 'Emergency',
    sub: 'Seek immediate emergency care',
  },
  URGENT: {
    bg: '#EA580C',
    icon: '⚠️',
    label: 'Urgent',
    sub: 'See a doctor today',
  },
  ROUTINE: {
    bg: '#4CAF50',
    icon: '✅',
    label: 'Routine',
    sub: 'Schedule an appointment when convenient',
  },
  INFORMATIONAL: {
    bg: '#2563EB',
    icon: 'ℹ️',
    label: 'Informational',
    sub: 'General health information',
  },
};

export default function TriageCard({ triage, message, cached }: Props) {
  const level = triage?.toUpperCase() || 'INFORMATIONAL';
  const config = triageConfig[level] || triageConfig.INFORMATIONAL;

  return (
    <div
      className="w-full rounded-2xl p-6 text-white relative overflow-hidden shadow-lg"
      style={{ background: config.bg }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="text-4xl">{config.icon}</span>
          <div>
            <div className="text-xs font-semibold uppercase tracking-widest opacity-80 mb-0.5">Triage Level</div>
            <div className="text-2xl font-extrabold tracking-tight">{config.label}</div>
            <div className="text-sm opacity-90 mt-1">{message || config.sub}</div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0">
          {cached && (
            <span className="inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-sm text-white text-xs font-semibold px-3 py-1.5 rounded-full border border-white/30">
              ⚡ Answered from memory
            </span>
          )}
        </div>
      </div>

      {/* Decorative circle */}
      <div
        className="absolute -right-8 -bottom-8 w-36 h-36 rounded-full opacity-20"
        style={{ background: 'rgba(255,255,255,0.3)' }}
      />
    </div>
  );
}
