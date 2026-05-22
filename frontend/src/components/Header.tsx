export default function Header() {
  return (
    <header style={{ background: '#4CAF50' }} className="w-full shadow-md">
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-sm">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="#4CAF50" />
              <path d="M13 7h-2v4H7v2h4v4h2v-4h4v-2h-4V7z" fill="white" />
            </svg>
          </div>
          <div>
            <h1 className="text-white font-bold text-2xl tracking-tight leading-none">ClinIQ</h1>
            <p className="text-green-100 text-xs font-medium mt-0.5">Medical intelligence for everyone</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className="hidden sm:flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full"
            style={{ background: 'rgba(255,255,255,0.2)', color: 'white' }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L4 7v10l8 5 8-5V7L12 2zm0 2.3l6 3.75v8.9l-6 3.75-6-3.75V8.05L12 4.3z" />
            </svg>
            Not a substitute for medical advice
          </span>
        </div>
      </div>
    </header>
  );
}
