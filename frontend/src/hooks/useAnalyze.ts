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
      // patient_id: form field first, then localStorage (set after a prior v2 call)
      const patientId = request.patient_id || localStorage.getItem('cliniq_patient_id') || '';
      const caseId    = localStorage.getItem('cliniq_active_case_id') || undefined;

      // Route to v2 pipeline only when we have a Supabase patient UUID
      const useV2 = Boolean(patientId);
      const url = useV2
        ? `${BASE_URL}/api/v2/analyze`
        : `${BASE_URL}/api/analyze`;

      // Correct PipelineRequest shape — fixes wrong field names from previous version
      const v2Body = {
        ...(patientId && { patient_id: patientId }),
        ...(caseId && { case_id: caseId }),
        user_input: request.query,   // was incorrectly sent as "query"
        input_type: 'text' as const, // required field that was previously missing
        language:   'en',
      };

      const body = useV2 ? v2Body : request;

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

      // Store patient_id and case_id so Patient OS and DeepDive can pick them up
      if ((data as any).patient_id) {
        localStorage.setItem('cliniq_patient_id', (data as any).patient_id);
        console.log('STORED patient_id:', (data as any).patient_id);
      }
      if ((data as any).case_id) {
        localStorage.setItem('cliniq_active_case_id', (data as any).case_id);
        console.log('STORED case_id:', (data as any).case_id);
      }

      // Persist episode to localStorage so Dashboard survives backend restarts
      if (request.patient_id) {
        const key = `cliniq_episodes_${request.patient_id}`;
        const existing = JSON.parse(localStorage.getItem(key) || '[]');
        existing.unshift({
          id: Date.now().toString(),
          patient_id: request.patient_id,
          query: request.query,
          triage: data.risk_tier || data.triage || '',
          conditions: (data.conditions || []).map((c: any) => c.name),
          response_summary: data.synthesis || data.patient_summary || '',
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
