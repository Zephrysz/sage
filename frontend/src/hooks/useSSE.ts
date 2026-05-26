import { useState, useCallback, useRef } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useSSE() {
  const [text, setText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const startStream = useCallback((path: string, sessionId?: string) => {
    setText('');
    setError(null);
    setIsStreaming(true);

    const url = new URL(`${API_URL}${path}`);
    if (sessionId) url.searchParams.set('session_id', sessionId);

    const es = new EventSource(url.toString());
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      if (event.data === '[DONE]') {
        setIsStreaming(false);
        es.close();
        return;
      }
      setText((prev) => prev + event.data);
    };

    es.onerror = () => {
      setError('Stream error');
      setIsStreaming(false);
      es.close();
    };
  }, []);

  const stopStream = useCallback(() => {
    eventSourceRef.current?.close();
    setIsStreaming(false);
  }, []);

  return { text, isStreaming, error, startStream, stopStream };
}
