'use client';

import { cn } from '@/lib/utils';

interface SummaryViewProps {
  text: string;
  isStreaming: boolean;
  ragSourced: boolean | null;
}

/** Skeleton line placeholder shown while streaming hasn't produced text yet */
function SkeletonLines() {
  return (
    <div className="space-y-3 animate-pulse" aria-hidden="true">
      {[100, 90, 95, 80, 85, 70].map((w, i) => (
        <div
          key={i}
          className="h-4 rounded bg-muted"
          style={{ width: `${w}%` }}
        />
      ))}
    </div>
  );
}

export function SummaryView({ text, isStreaming, ragSourced }: SummaryViewProps) {
  const showSkeleton = isStreaming && text.length === 0;

  return (
    <div className="space-y-4">
      {/* RAG disclaimer */}
      {ragSourced === false && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-700 dark:bg-yellow-950 dark:text-yellow-300"
        >
          <span aria-hidden="true" className="mt-0.5 shrink-0 text-base">⚠️</span>
          <span>
            Este conteúdo foi gerado pela IA e não está baseado em material CEFIS.
          </span>
        </div>
      )}

      {/* Content area */}
      {showSkeleton ? (
        <SkeletonLines />
      ) : (
        <div
          className={cn(
            'whitespace-pre-wrap text-sm leading-relaxed text-foreground',
            isStreaming && 'after:ml-0.5 after:inline-block after:h-4 after:w-0.5 after:animate-pulse after:bg-foreground after:align-middle after:content-[""]'
          )}
        >
          {text}
        </div>
      )}

      {/* Streaming indicator */}
      {isStreaming && text.length > 0 && (
        <p className="text-xs text-muted-foreground" aria-live="polite">
          Gerando resumo…
        </p>
      )}
    </div>
  );
}
