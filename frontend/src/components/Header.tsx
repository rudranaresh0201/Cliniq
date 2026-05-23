export default function Header() {
  return (
    <header
      className="w-full relative overflow-hidden"
      style={{
        background: '#0a0f1a',
        borderBottom: '1px solid rgba(16,185,129,0.15)',
      }}
    >
      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage:
            'linear-gradient(rgba(16,185,129,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(16,185,129,0.4) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Bottom gradient border */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px"
        style={{
          background: 'linear-gradient(90deg, transparent, rgba(16,185,129,0.5), rgba(6,182,212,0.5), transparent)',
        }}
      />

      <div className="relative max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo + name */}
        <div className="flex items-center gap-3.5">
          <div className="relative w-11 h-11">
            <div
              className="absolute inset-0 rounded-xl opacity-30"
              style={{
                background: 'rgba(16,185,129,0.4)',
                animation: 'pulse-ring 2s ease-out infinite',
              }}
            />
            <div
              className="relative w-11 h-11 rounded-xl flex items-center justify-center shadow-md"
              style={{
                background: 'rgba(16,185,129,0.15)',
                border: '1px solid rgba(16,185,129,0.4)',
                backdropFilter: 'blur(10px)',
              }}
            >
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" fill="url(#logoGrad)" />
                <path d="M13 7h-2v4H7v2h4v4h2v-4h4v-2h-4V7z" fill="white" />
                <defs>
                  <linearGradient id="logoGrad" x1="0" y1="0" x2="24" y2="24">
                    <stop offset="0%" stopColor="#10b981" />
                    <stop offset="100%" stopColor="#06b6d4" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </div>
          <div>
            <h1
              className="font-extrabold text-2xl tracking-tight leading-none"
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                fontFamily: 'Sora, sans-serif',
              }}
            >
              ClinIQ
            </h1>
            <p className="text-xs font-medium mt-0.5 tracking-wide" style={{ color: 'rgba(16,185,129,0.7)' }}>
              Medical Intelligence for India
            </p>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          <span
            className="hidden sm:flex items-center gap-1.5 text-xs font-bold px-3.5 py-1.5 rounded-full relative overflow-hidden"
            style={{
              background: 'rgba(16,185,129,0.1)',
              color: 'rgba(16,185,129,0.9)',
              border: '1px solid rgba(16,185,129,0.25)',
              backdropFilter: 'blur(10px)',
              backgroundSize: '200% auto',
              animation: 'shimmer 2.5s linear infinite',
            }}
          >
            Powered by PubMed + AI
          </span>

          <span
            className="hidden md:flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full"
            style={{
              background: 'rgba(255,255,255,0.05)',
              color: 'rgba(255,255,255,0.5)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
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
