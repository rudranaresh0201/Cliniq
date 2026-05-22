interface Props {
  redFlags: string[];
}

export default function RedFlags({ redFlags }: Props) {
  if (!redFlags || redFlags.length === 0) return null;

  return (
    <div
      className="rounded-xl overflow-hidden shadow-md"
      style={{ background: '#FFF7ED', border: '1px solid #FED7AA' }}
    >
      <div className="px-5 py-4 border-b" style={{ borderColor: '#FED7AA', background: '#FEF3C7' }}>
        <div className="flex items-center gap-3">
          <span className="text-2xl">🚩</span>
          <div>
            <h3 className="font-bold text-orange-800 text-base">Red Flag Symptoms</h3>
            <p className="text-xs text-orange-600 mt-0.5">Go to the hospital immediately if you experience:</p>
          </div>
        </div>
      </div>

      <div className="p-5">
        <ul className="space-y-2.5">
          {redFlags.map((flag, i) => (
            <li key={i} className="flex items-start gap-3">
              <svg
                className="w-4 h-4 shrink-0 mt-0.5"
                style={{ color: '#EA580C' }}
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-sm text-orange-900">{flag}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
