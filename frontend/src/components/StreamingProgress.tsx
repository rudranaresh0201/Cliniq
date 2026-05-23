interface Props {
  stage: string;
  completedStages: string[];
  stageMessage: string;
}

const ALL_STAGES = [
  { id: 'safety_check',  label: 'Safety Check',         icon: '🛡️' },
  { id: 'cache_check',   label: 'Memory Check',          icon: '⚡' },
  { id: 'classified',    label: 'Classifying Query',     icon: '🧠' },
  { id: 'planned',       label: 'Planning Search',       icon: '📋' },
  { id: 'fetching',      label: 'Fetching Medical Data', icon: '🌐' },
  { id: 'evaluated',     label: 'Evaluating Sources',    icon: '⚖️' },
  { id: 'synthesizing',  label: 'Synthesizing Answer',   icon: '✍️' },
];

export default function StreamingProgress({ stage, completedStages, stageMessage }: Props) {
  return (
    <div className="bg-white rounded-2xl shadow-lg border border-slate-100 p-6 w-full max-w-md mx-auto">
      <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-5">
        Analyzing...
      </h3>

      <div className="relative">
        {/* Connecting line */}
        <div
          className="absolute left-4 top-5 bottom-5 w-px"
          style={{ background: '#e2e8f0' }}
        />

        <ul className="space-y-4">
          {ALL_STAGES.map((s) => {
            const done   = completedStages.includes(s.id);
            const active = !done && stage === s.id;

            return (
              <li key={s.id} className="flex items-start gap-3 relative">
                {/* Stage indicator */}
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm z-10"
                  style={{
                    background: done   ? '#E8F5E9'
                               : active ? '#FEF9E7'
                               : '#f1f5f9',
                    border: `2px solid ${done ? '#4CAF50' : active ? '#F5C518' : '#e2e8f0'}`,
                  }}
                >
                  {done ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="#4CAF50" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : active ? (
                    <span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-yellow-400 border-t-transparent rounded-full" />
                  ) : (
                    <span className="w-2 h-2 rounded-full" style={{ background: '#cbd5e1' }} />
                  )}
                </div>

                {/* Label + message */}
                <div className="pt-1">
                  <span
                    className="text-sm font-semibold"
                    style={{
                      color: done   ? '#4CAF50'
                             : active ? '#B8860B'
                             : '#94a3b8',
                    }}
                  >
                    {s.icon} {s.label}
                  </span>
                  {active && stageMessage && (
                    <p className="text-xs text-slate-400 mt-0.5">{stageMessage}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
