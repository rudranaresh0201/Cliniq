import type { DrugSafety as DrugSafetyType } from '../types';

interface Props {
  drugSafety: DrugSafetyType;
}

export default function DrugSafety({ drugSafety }: Props) {
  if (!drugSafety?.interactions_found) return null;

  return (
    <div className="bg-white rounded-xl shadow-md border-l-4 border-red-500 overflow-hidden">
      <div className="bg-red-50 px-5 py-4 border-b border-red-100">
        <div className="flex items-center gap-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <h3 className="font-bold text-red-800 text-base">Drug Interaction Warning</h3>
            <p className="text-xs text-red-600 mt-0.5">Potential interactions detected with your medications</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {drugSafety.warnings.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Warnings</p>
            <ul className="space-y-2">
              {drugSafety.warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                  <span className="shrink-0 mt-0.5">•</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {drugSafety.recommendations.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Recommendations</p>
            <ul className="space-y-2">
              {drugSafety.recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                  <span className="text-green-500 shrink-0 mt-0.5">›</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
