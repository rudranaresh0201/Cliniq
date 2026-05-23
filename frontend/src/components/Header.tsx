export default function Header() {
  return (
    <header
      className="w-full shadow-lg relative overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #16a34a 0%, #0d9488 100%)' }}
    >
      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.15) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo + name */}
        <div className="flex items-center gap-3.5">
          <div className="relative w-11 h-11">
            <div
              className="absolute inset-0 rounded-xl opacity-40"
              style={{
                background: 'rgba(255,255,255,0.3)',
                animation: 'pulse-ring 2s ease-out infinite',
              }}
            />
            <div className="relative w-11 h-11 bg-white rounded-xl flex items-center justify-center shadow-md">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" fill="#16a34a" />
                <path d="M13 7h-2v4H7v2h4v4h2v-4h4v-2h-4V7z" fill="white" />
              </svg>
            </div>
          </div>
          <div>
            <h1 className="text-white font-extrabold text-2xl tracking-tight leading-none">
              ClinIQ
            </h1>
            <p className="text-green-100 text-xs font-medium mt-0.5 tracking-wide">
              Medical Intelligence for India
            </p>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Shimmer badge */}
          <span
            className="hidden sm:flex items-center gap-1.5 text-xs font-bold px-3.5 py-1.5 rounded-full relative overflow-hidden"
            style={{
              background: 'linear-gradient(90deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0.4) 50%, rgba(255,255,255,0.25) 100%)',
              backgroundSize: '200% auto',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.35)',
              animation: 'shimmer 2.5s linear infinite',
            }}
          >
            Powered by PubMed + AI
          </span>

          <span
            className="hidden md:flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full"
            style={{ background: 'rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.85)' }}
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L4 7v10l8 5 8-5V7L12 2zm0 2.3l6 3.75v8.9l-6 3.75-6-3.75V8.05L12 4.3z" />
            </svg>
            Not a substitute for medical advice
          </span>
        </div>
      </div>
    </header>
  );
}
