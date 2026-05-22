export default function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-6">
      {/* Animated medical cross */}
      <div className="relative w-16 h-16">
        <div
          className="absolute inset-0 rounded-2xl animate-ping opacity-30"
          style={{ background: '#4CAF50' }}
        />
        <div
          className="absolute inset-0 rounded-2xl flex items-center justify-center"
          style={{ background: '#4CAF50' }}
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="white">
            <path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-2 10h-4v4h-2v-4H7v-2h4V7h2v4h4v2z" />
          </svg>
        </div>
      </div>

      {/* Pulse bars */}
      <div className="flex items-end gap-1 h-8">
        {[0.3, 0.7, 1, 0.7, 0.4, 0.8, 1, 0.5, 0.3].map((h, i) => (
          <div
            key={i}
            className="w-1.5 rounded-full animate-pulse"
            style={{
              height: `${h * 32}px`,
              background: '#4CAF50',
              animationDelay: `${i * 0.1}s`,
              animationDuration: '0.8s',
            }}
          />
        ))}
      </div>

      <div className="text-center">
        <p className="text-slate-800 font-semibold text-lg">Analyzing your symptoms...</p>
        <p className="text-slate-500 text-sm mt-1">Searching PubMed medical database</p>
      </div>
    </div>
  );
}
