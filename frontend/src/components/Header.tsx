export default function Header() {
  return (
    <header
      className="w-full relative overflow-hidden"
      style={{
        background: '#080B14',
        borderBottom: '1px solid rgba(255,149,0,0.15)',
      }}
    >
      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,149,0,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,149,0,1) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      {/* Bottom gradient line */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px"
        style={{
          background: 'linear-gradient(90deg, transparent, rgba(255,149,0,0.5), rgba(6,214,160,0.4), transparent)',
        }}
      />

      <div className="relative max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3.5">
          <div className="relative w-11 h-11">
            <div
              className="absolute inset-0 rounded-xl"
              style={{
                background: 'rgba(255,149,0,0.3)',
                animation: 'pulse-ring 2s ease-out infinite',
              }}
            />
            <div
              className="relative w-11 h-11 rounded-xl flex items-center justify-center"
              style={{
                background: 'rgba(255,149,0,0.15)',
                border: '1px solid rgba(255,149,0,0.4)',
              }}
            >
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" fill="url(#hdrGrad)" />
                <path d="M13 7h-2v4H7v2h4v4h2v-4h4v-2h-4V7z" fill="white" />
                <defs>
                  <linearGradient id="hdrGrad" x1="0" y1="0" x2="24" y2="24">
                    <stop offset="0%" stopColor="#FF9500" />
                    <stop offset="100%" stopColor="#06D6A0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </div>
          <div>
            <h1
              className="font-extrabold text-2xl tracking-tight leading-none text-white"
              style={{ fontFamily: 'Sora, sans-serif' }}
            >
              ClinIQ
            </h1>
            <p className="text-xs font-medium mt-0.5 tracking-wide" style={{ color: '#94A3B8' }}>
              Medical Intelligence for India
            </p>
          </div>
        </div>

        {/* Right */}
        <div className="flex items-center gap-3">
          <span
            className="hidden sm:flex items-center gap-1.5 text-xs font-bold px-3.5 py-1.5 rounded-full"
            style={{
              background: 'rgba(255,149,0,0.1)',
              color: '#FF9500',
              border: '1px solid rgba(255,149,0,0.35)',
            }}
          >
            Powered by PubMed + AI
          </span>
          <span
            className="hidden md:flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full"
            style={{
              background: 'rgba(255,255,255,0.04)',
              color: '#475569',
              border: '1px solid rgba(255,255,255,0.06)',
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
