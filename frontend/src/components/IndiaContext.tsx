interface Alert {
  disease: string;
  severity: string;
  message: string;
  source: string;
}

interface Props {
  season: string;
  high_risk_diseases: string[];
  regional_alerts: Alert[];
  epidemiological_note: string;
}

const SEASON_CONFIG: Record<string, { icon: string; label: string; bg: string; color: string }> = {
  monsoon: { icon: '🌧️', label: 'Monsoon Season', bg: '#EFF6FF', color: '#1D4ED8' },
  summer:  { icon: '☀️',  label: 'Summer',         bg: '#FFF7ED', color: '#C2410C' },
  winter:  { icon: '🌨️', label: 'Winter',          bg: '#F1F5F9', color: '#475569' },
};

export default function IndiaContext({ season, high_risk_diseases, regional_alerts, epidemiological_note }: Props) {
  const config = SEASON_CONFIG[season] ?? SEASON_CONFIG['winter'];

  return (
    <div className="bg-white rounded-xl shadow-md border border-slate-100 p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-base">🇮🇳</span>
        <h3 className="font-bold text-slate-800 text-sm">India Epidemiological Context</h3>
      </div>

      {/* Season badge */}
      <div className="mb-4">
        <span
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
          style={{ background: config.bg, color: config.color }}
        >
          {config.icon} {config.label}
        </span>
      </div>

      {/* Regional alerts */}
      {regional_alerts.length > 0 && (
        <div className="mb-4 space-y-2">
          {regional_alerts.map((alert, i) => (
            <div
              key={i}
              className="flex items-start gap-2 px-3 py-2 rounded-lg text-xs"
              style={{ background: '#FFF7ED', border: '1px solid #FED7AA' }}
            >
              <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-orange-400 mt-1" />
              <span className="text-orange-800">
                <strong>{alert.disease}:</strong> {alert.message} —{' '}
                <span className="text-orange-600">{alert.source}</span>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* High-risk disease pills */}
      {high_risk_diseases.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            High-risk this season
          </p>
          <div className="flex flex-wrap gap-2">
            {high_risk_diseases.map((disease, i) => (
              <span
                key={i}
                className="px-2.5 py-1 rounded-full text-xs font-medium"
                style={{ background: '#E8F5E9', color: '#2E7D32', border: '1px solid #4CAF50' }}
              >
                {disease.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Epidemiological note */}
      <p className="text-xs text-slate-500 leading-relaxed">{epidemiological_note}</p>
    </div>
  );
}
