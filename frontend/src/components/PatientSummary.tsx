interface Props {
  summary: string;
}

export default function PatientSummary({ summary }: Props) {
  if (!summary) return null;

  return (
    <div className="bg-white rounded-xl shadow-md border border-slate-100 p-6">
      <div className="flex items-center gap-2 mb-4">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: '#E8F5E9' }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="#4CAF50">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
          </svg>
        </div>
        <h3 className="font-bold text-slate-800">Summary</h3>
      </div>

      <div className="flex gap-4">
        <div className="shrink-0 mt-1">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="#4CAF50" opacity="0.4">
            <path d="M6 17h3l2-4H7c-.55 0-1-.45-1-1V7c0-.55.45-1 1-1h4c.55 0 1 .45 1 1v5l-3 5zm8 0h3l2-4h-4c-.55 0-1-.45-1-1V7c0-.55.45-1 1-1h4c.55 0 1 .45 1 1v5l-3 5z" />
          </svg>
        </div>
        <p className="text-slate-700 text-base leading-relaxed">{summary}</p>
      </div>
    </div>
  );
}
