interface Props {
  immediateActions: string[];
  recommendedTests: string[];
}

export default function ActionsList({ immediateActions, recommendedTests }: Props) {
  const hasActions = immediateActions.length > 0;
  const hasTests = recommendedTests.length > 0;

  if (!hasActions && !hasTests) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {hasActions && (
        <div className="bg-white rounded-xl shadow-md border border-slate-100 p-5">
          <div className="flex items-center gap-2 mb-4">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: '#FEF9E7' }}
            >
              <span className="text-base">⚡</span>
            </div>
            <h3 className="font-bold text-slate-800">Immediate Actions</h3>
          </div>
          <ul className="space-y-3">
            {immediateActions.map((action, i) => (
              <li key={i} className="flex items-start gap-3">
                <div
                  className="w-1 shrink-0 rounded-full mt-1.5"
                  style={{ height: '14px', background: '#F5C518' }}
                />
                <span className="text-sm text-slate-700 leading-relaxed">{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasTests && (
        <div className="bg-white rounded-xl shadow-md border border-slate-100 p-5">
          <div className="flex items-center gap-2 mb-4">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: '#E8F5E9' }}
            >
              <span className="text-base">🔬</span>
            </div>
            <h3 className="font-bold text-slate-800">Recommended Tests</h3>
          </div>
          <ul className="space-y-3">
            {recommendedTests.map((test, i) => (
              <li key={i} className="flex items-start gap-3">
                <div
                  className="w-1 shrink-0 rounded-full mt-1.5"
                  style={{ height: '14px', background: '#4CAF50' }}
                />
                <span className="text-sm text-slate-700 leading-relaxed">{test}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
