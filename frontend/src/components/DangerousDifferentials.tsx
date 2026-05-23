interface Props {
  differentials: string[];
}

export default function DangerousDifferentials({ differentials }: Props) {
  if (!differentials || differentials.length === 0) return null;
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">⚕️</span>
        <div>
          <h3 className="font-bold text-amber-900 text-sm">
            Conditions To Rule Out
          </h3>
          <p className="text-xs text-amber-700">
            Less likely but serious — mention to your doctor
          </p>
        </div>
      </div>
      <ul className="space-y-1.5">
        {differentials.map((d, i) => (
          <li key={i} className="text-sm text-amber-800 flex items-start gap-2">
            <span className="text-amber-500 shrink-0">◆</span>
            {d}
          </li>
        ))}
      </ul>
    </div>
  );
}
