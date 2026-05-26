'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ApostilaSection {
  id: string;
  title: string;
  icon: string;
  content: string;
}

interface ApostilaViewProps {
  text: string;
  isStreaming: boolean;
  ragSourced: boolean | null;
}

/** Parse the apostila text into sections based on known headings */
function parseSections(text: string): ApostilaSection[] {
  const sectionDefs = [
    { id: 'introducao', title: 'Introdução', icon: '📖', patterns: ['introdução', 'introducao', 'introduction'] },
    { id: 'conceitos', title: 'Conceitos Principais', icon: '🧠', patterns: ['conceitos principais', 'conceitos-chave', 'conceitos chave', 'main concepts'] },
    { id: 'exemplos', title: 'Exemplos Práticos', icon: '💡', patterns: ['exemplos práticos', 'exemplos praticos', 'practical examples', 'exemplos'] },
    { id: 'atencao', title: 'Pontos de Atenção', icon: '⚠️', patterns: ['pontos de atenção', 'pontos de atencao', 'attention points', 'pontos importantes'] },
  ];

  // Try to split by markdown headings (## or ###) or bold headings
  const headingRegex = /^#{1,3}\s+(.+)$/gim;
  const boldHeadingRegex = /^\*\*(.+)\*\*\s*$/gim;

  let matches: Array<{ index: number; heading: string }> = [];

  let m: RegExpExecArray | null;
  headingRegex.lastIndex = 0;
  while ((m = headingRegex.exec(text)) !== null) {
    matches.push({ index: m.index, heading: m[1].trim() });
  }

  if (matches.length === 0) {
    boldHeadingRegex.lastIndex = 0;
    while ((m = boldHeadingRegex.exec(text)) !== null) {
      matches.push({ index: m.index, heading: m[1].trim() });
    }
  }

  if (matches.length > 0) {
    // Sort by position
    matches.sort((a, b) => a.index - b.index);

    return matches.map((match, i) => {
      const start = match.index + match.heading.length + (text[match.index] === '#' ? text.slice(match.index).indexOf(' ') + 1 : 4);
      const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
      const content = text.slice(start, end).trim();

      // Try to match to a known section
      const headingLower = match.heading.toLowerCase();
      const def = sectionDefs.find((d) =>
        d.patterns.some((p) => headingLower.includes(p))
      );

      return {
        id: def?.id ?? `section-${i}`,
        title: def?.title ?? match.heading,
        icon: def?.icon ?? '📄',
        content,
      };
    });
  }

  // Fallback: return the whole text as a single section
  return [
    {
      id: 'content',
      title: 'Conteúdo',
      icon: '📄',
      content: text,
    },
  ];
}

function SkeletonSection() {
  return (
    <div className="animate-pulse space-y-2 rounded-lg border border-border p-4">
      <div className="h-5 w-48 rounded bg-muted" />
      <div className="space-y-2 pt-2">
        <div className="h-3 w-full rounded bg-muted" />
        <div className="h-3 w-5/6 rounded bg-muted" />
        <div className="h-3 w-4/5 rounded bg-muted" />
      </div>
    </div>
  );
}

interface CollapsibleSectionProps {
  section: ApostilaSection;
  defaultOpen?: boolean;
}

function CollapsibleSection({ section, defaultOpen = true }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-controls={`section-content-${section.id}`}
        className="flex w-full items-center justify-between gap-2 bg-muted/50 px-4 py-3 text-left text-sm font-semibold text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
      >
        <span className="flex items-center gap-2">
          <span aria-hidden="true">{section.icon}</span>
          {section.title}
        </span>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
      </button>

      <div
        id={`section-content-${section.id}`}
        role="region"
        aria-labelledby={`section-btn-${section.id}`}
        className={cn(
          'overflow-hidden transition-all duration-200',
          isOpen ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className="px-4 py-3 text-sm leading-relaxed text-foreground whitespace-pre-wrap">
          {section.content}
        </div>
      </div>
    </div>
  );
}

export function ApostilaView({ text, isStreaming, ragSourced }: ApostilaViewProps) {
  const showSkeleton = isStreaming && text.length === 0;
  const sections = text.length > 0 ? parseSections(text) : [];

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

      {/* Skeleton while waiting for first chunk */}
      {showSkeleton && (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonSection key={i} />
          ))}
        </div>
      )}

      {/* Streaming: show raw text with cursor until done */}
      {isStreaming && text.length > 0 && (
        <div className="space-y-2">
          <div
            className="whitespace-pre-wrap text-sm leading-relaxed text-foreground after:ml-0.5 after:inline-block after:h-4 after:w-0.5 after:animate-pulse after:bg-foreground after:align-middle after:content-['']"
          >
            {text}
          </div>
          <p className="text-xs text-muted-foreground" aria-live="polite">
            Gerando apostila…
          </p>
        </div>
      )}

      {/* Final parsed sections (shown when streaming is done) */}
      {!isStreaming && sections.length > 0 && (
        <div className="space-y-2">
          {sections.map((section, i) => (
            <CollapsibleSection
              key={section.id}
              section={section}
              defaultOpen={i === 0}
            />
          ))}
        </div>
      )}
    </div>
  );
}
