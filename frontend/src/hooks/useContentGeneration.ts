import { useState, useCallback, useRef } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ContentDonePayload {
  rag_sourced: boolean;
  sources: Array<{ course_name: string; lesson_name: string }>;
}

export type ContentType = 'SUMMARY' | 'APOSTILA';

interface UseContentGenerationOptions {
  onDone?: (payload: ContentDonePayload) => void;
  onError?: (error: string) => void;
}

export function useContentGeneration(options?: UseContentGenerationOptions) {
  const [text, setText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [donePayload, setDonePayload] = useState<ContentDonePayload | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const generate = useCallback(
    async (
      planItemId: string,
      contentType: ContentType,
      sessionId: string
    ) => {
      // Reset state
      setText('');
      setError(null);
      setDonePayload(null);
      setIsStreaming(true);

      // Cancel any in-flight request
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const res = await fetch(`${API_URL}/content/generate`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Session-Id': sessionId,
          },
          body: JSON.stringify({
            plan_item_id: planItemId,
            content_type: contentType,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`API error: ${res.status} ${res.statusText}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE lines
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6); // Remove "data: " prefix

            if (data.startsWith('[DONE]')) {
              // Parse the JSON payload after [DONE]
              const jsonStr = data.slice(6).trim(); // Remove "[DONE]" prefix
              let payload: ContentDonePayload = { rag_sourced: true, sources: [] };
              if (jsonStr) {
                try {
                  payload = JSON.parse(jsonStr);
                } catch {
                  // If parsing fails, keep default
                }
              }
              setDonePayload(payload);
              setIsStreaming(false);
              options?.onDone?.(payload);
              return;
            }

            setText((prev) => prev + data);
          }
        }

        setIsStreaming(false);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        const message = err instanceof Error ? err.message : 'Erro ao gerar conteúdo';
        setError(message);
        setIsStreaming(false);
        options?.onError?.(message);
      }
    },
    [options]
  );

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { text, isStreaming, error, donePayload, generate, cancel };
}
