import { useState, useRef } from 'react';
import type { AnalyzeResponse } from '../types';

const STAGE_MESSAGES: Record<string, string> = {
  safety_check: '🛡️ Running safety check...',
  cache_hit:    '⚡ Found in memory',
  classified:   '🧠 Query classified',
  planned:      '📋 Search strategy ready',
  fetching:     '🌐 Fetching medical literature...',
  evaluated:    '⚖️ Evaluating source quality...',
  synthesizing: '✍️ Synthesizing answer...',
};

interface StreamParams {
  query: string;
  age?: number | null;
  gender?: string;
  state?: string;
}

export function useAnalyzeStream() {
  const [stage, setStage] = useState('');
  const [stageMessage, setStageMessage] = useState('');
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const reset = () => {
    esRef.current?.close();
    esRef.current = null;
    setStage('');
    setStageMessage('');
    setCompletedStages([]);
    setResult(null);
    setError(null);
    setLoading(false);
  };

  const streamAnalyze = ({ query, age, gender, state }: StreamParams) => {
    reset();
    setLoading(true);

    const params = new URLSearchParams({ query });
    if (age != null) params.set('age', String(age));
    if (gender) params.set('gender', gender);
    if (state) params.set('state', state);

    const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
    const url = `${BASE_URL}/api/analyze/stream?${params.toString()}`;
    const es = new EventSource(url);
    esRef.current = es;

    const advanceStage = (newStage: string) => {
      setCompletedStages((prev) =>
        prev.includes(newStage) ? prev : [...prev, newStage]
      );
      setStage(newStage);
      setStageMessage(STAGE_MESSAGES[newStage] ?? newStage);
    };

    // Map pipeline events to frontend stage ids
    const STAGE_MAP: Record<string, string> = {
      safety_check: 'safety_check',
      cache_hit:    'cache_hit',
      classified:   'classified',
      planned:      'planned',
      fetching:     'fetching',
      fetched:      'fetching',
      evaluating:   'evaluated',
      evaluated:    'evaluated',
      synthesizing: 'synthesizing',
    };

    const handleEvent = (eventName: string) => (e: MessageEvent) => {
      const mappedStage = STAGE_MAP[eventName];
      if (mappedStage) advanceStage(mappedStage);

      if (eventName === 'result') {
        try {
          const data: AnalyzeResponse = JSON.parse(e.data);
          setResult(data);
        } catch {
          setError('Failed to parse result from server.');
        }
        setLoading(false);
        es.close();
      }

      if (eventName === 'error') {
        try {
          const data = JSON.parse(e.data);
          setError(data.message ?? 'Stream error');
        } catch {
          setError('Stream error');
        }
        setLoading(false);
        es.close();
      }

      if (eventName === 'done') {
        setLoading(false);
        es.close();
      }
    };

    const events = [
      'safety_check', 'cache_hit', 'cache_miss', 'classified',
      'planned', 'fetching', 'fetched', 'evaluating', 'evaluated',
      'synthesizing', 'complete', 'result', 'error', 'done',
    ];
    events.forEach((evt) => es.addEventListener(evt, handleEvent(evt)));

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return;
      setError('Connection lost. Make sure the backend is running.');
      setLoading(false);
      es.close();
    };
  };

  return {
    stage,
    stageMessage,
    completedStages,
    result,
    error,
    loading,
    streamAnalyze,
    reset,
  };
}
