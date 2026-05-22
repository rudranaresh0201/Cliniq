interface Props {
  text?: string;
}

export default function Disclaimer({ text }: Props) {
  return (
    <div className="bg-slate-50 rounded-xl border border-slate-200 px-5 py-4">
      <div className="flex items-start gap-3">
        <svg className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
            clipRule="evenodd"
          />
        </svg>
        <p className="text-xs text-slate-500 leading-relaxed">
          {text ||
            'ClinIQ is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition. Never disregard professional medical advice or delay in seeking it because of something you have read here.'}
        </p>
      </div>
    </div>
  );
}
