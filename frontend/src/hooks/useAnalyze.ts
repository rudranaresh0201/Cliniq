import { useState } from 'react';
import type { AnalyzeRequest, AnalyzeResponse } from '../types';

export function useAnalyze() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const analyze = async (request: AnalyzeRequest) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const useV2 = Boolean(request.patient_id);
      const url = useV2
        ? 'http://127.0.0.1:8000/api/analyze/v2'
        : 'http://127.0.0.1:8000/api/analyze';
      // v2 model field is user_id, not patient_id
      const body = useV2
        ? { query: request.query, user_id: request.patient_id, state: request.state }
        : request;
      console.log('patient_id value:', request.patient_id);
      console.log('useV2:', !!request.patient_id);
      console.log(`[ClinIQ] analyze → ${url}`, useV2 ? `user_id=${request.patient_id}` : '(no patient ID)');

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${response.status}`);
      }

      const data: AnalyzeResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
    setLoading(false);
  };

  return { analyze, loading, error, result, reset };
}
