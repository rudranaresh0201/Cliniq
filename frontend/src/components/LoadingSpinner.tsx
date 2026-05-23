import { useState, useEffect } from 'react';

const MESSAGES = [
  { main: 'Reasoning clinically…', sub: 'Building diagnostic hypothesis' },
  { main: 'Searching PubMed…', sub: 'Scanning 35M+ medical papers' },
  { main: 'Applying India context…', sub: 'Adjusting for regional epidemiology' },
  { main: 'Ranking differentials…', sub: 'Weighing probability vs. severity' },
  { main: 'Checking red flags…', sub: 'Flagging must-not-miss diagnoses' },
  { main: 'Synthesizing findings…', sub: 'Generating your clinical report' },
];

export default function LoadingSpinner() {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setMsgIndex((i) => (i + 1) % MESSAGES.length);
    }, 2200);
    return () => clearInterval(id);
  }, []);

  const { main, sub } = MESSAGES[msgIndex];

  return (
    <div className="flex flex-col items-center justify-center py-20 gap-6">
      {/* Animated medical cross */}
      <div className="relative w-16 h-16">
        <div
          className="absolute inset-0 rounded-2xl animate-ping opacity-30"
          style={{ background: 'linear-gradient(135deg, #FF9500, #06D6A0)' }}
        />
        <div
          className="absolute inset-0 rounded-2xl flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #FF9500, #FF6B00)' }}
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
              background: i % 2 === 0 ? '#FF9500' : '#06D6A0',
              animationDelay: `${i * 0.1}s`,
              animationDuration: '0.8s',
            }}
          />
        ))}
      </div>

      <div className="text-center transition-all duration-500">
        <p className="font-semibold text-lg" style={{ color: '#f1f5f9' }}>{main}</p>
        <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>{sub}</p>
      </div>
    </div>
  );
}
