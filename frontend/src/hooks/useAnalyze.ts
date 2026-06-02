import { useState } from 'react';
import type { AnalyzeRequest, AnalyzeResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export function useAnalyze() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const analyze = async (request: AnalyzeRequest) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const patientId = request.patient_id || localStorage.getItem('cliniq_patient_id') || '';
      const caseId    = localStorage.getItem('cliniq_active_case_id') || undefined;

      // Always v2. Backend auto-creates a patient when patient_id is absent.
      const url = `${BASE_URL}/api/v2/analyze`;

      const body = {
        ...(patientId && { patient_id: patientId }),
        ...(caseId    && { case_id:    caseId    }),
        user_input: request.query,
        input_type: 'text' as const,
        language:   'en',
      };

      console.log('ANALYZE ENDPOINT:', url);
      console.log('ANALYZE REQUEST:', JSON.stringify(body));

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${response.status}`);
      }

      const data: AnalyzeResponse = await response.json();
      console.log('ANALYZE RESPONSE:', data);
      setResult(data);

      if ((data as any).patient_id) {
        localStorage.setItem('cliniq_patient_id', (data as any).patient_id);
        console.log('STORED patient_id:', (data as any).patient_id);
      }
      if ((data as any).case_id) {
        localStorage.setItem('cliniq_active_case_id', (data as any).case_id);
        console.log('STORED case_id:', (data as any).case_id);
      }

      // Persist episode to localStorage so Dashboard survives backend restarts
      const savedPatientId = (data as any).patient_id || patientId;
      if (savedPatientId) {
        const key = `cliniq_episodes_${savedPatientId}`;
        const existing = JSON.parse(localStorage.getItem(key) || '[]');
        existing.unshift({
          id: Date.now().toString(),
          patient_id: savedPatientId,
          query: request.query,
          triage: (data as any).risk_tier || (data as any).triage || '',
          conditions: ((data as any).conditions || []).map((c: any) => c.name),
          response_summary: (data as any).synthesis || (data as any).patient_summary || '',
          timestamp: new Date().toISOString(),
        });
        localStorage.setItem(key, JSON.stringify(existing.slice(0, 20)));
      }
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
