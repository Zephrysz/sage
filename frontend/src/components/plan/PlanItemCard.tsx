'use client';

import { useRouter } from 'next/navigation';
import { BookOpen, Sparkles, ArrowRight, FileText, BookMarked, Mic } from 'lucide-react';

export interface PlanItem {
  id: string;
  position: number;
  type: 'CEFIS_COURSE' | 'GENERATED_CONTENT';
  title: string;
  estimated_minutes: number;
  justification: string;
  course_id?: string;
  course_details?: Record<string, unknown>;
  has_certificate: boolean;
  highlighted_lessons?: string[];
}

interface PlanItemCardProps {
  item: PlanItem;
  /** User's learning style — used to highlight the matching content button */
  learningStyle?: 'video' | 'leitura' | 'audio' | 'cinestetico' | null;
  onGenerateSummary: (item: PlanItem) => void;
  onGenerateApostila: (item: PlanItem) => void;
  onGeneratePodcast: (item: PlanItem) => void;
  isGenerating?: boolean;
}

const TYPE_LABELS: Record<PlanItem['type'], string> = {
  CEFIS_COURSE: 'Curso CEFIS',
  GENERATED_CONTENT: 'Conteúdo Gerado',
};

const TypeIcon = ({ type }: { type: PlanItem['type'] }) =>
  type === 'CEFIS_COURSE' ? (
    <BookOpen className="h-4 w-4 shrink-0 text-[hsl(var(--primary))]" aria-hidden="true" />
  ) : (
    <Sparkles className="h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
  );

// Glow class for the button matching the user's learning style
function glowClass(active: boolean) {
  if (!active) return '';
  return 'ring-2 ring-[hsl(var(--primary))] shadow-md shadow-[hsl(174_72%_42%/0.4)]';
}

export function PlanItemCard({
  item,
  learningStyle,
  onGenerateSummary,
  onGenerateApostila,
  onGeneratePodcast,
  isGenerating = false,
}: PlanItemCardProps) {
  const router = useRouter();

  const handleStudy = () => {
    if (item.course_id) router.push(`/tutor/study/${item.course_id}`);
  };

  const handleContent = (type: 'SUMMARY' | 'APOSTILA' | 'PODCAST') => {
    router.push(
      `/tutor/content/${item.id}?type=${type}&title=${encodeURIComponent(item.title)}`
    );
  };

  const banner = item.course_details?.banner as string | undefined;

  // Which button glows based on learning style
  const summaryGlows = learningStyle === 'leitura' || learningStyle === 'cinestetico';
  const apostilaGlows = learningStyle === 'leitura' || learningStyle === 'cinestetico';
  const podcastGlows = learningStyle === 'audio';

  return (
    <div className="group rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] overflow-hidden shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:border-[hsl(174_72%_42%/0.35)]">
      {/* Banner image */}
      {banner && (
        <div className="relative h-28 w-full overflow-hidden bg-[hsl(var(--muted))]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={banner}
            alt={`Banner do curso ${item.title}`}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-linear-to-t from-[hsl(var(--card))] via-transparent to-transparent" />
        </div>
      )}

      <div className="p-4 space-y-3">
        {/* Header row */}
        <div className="flex items-start gap-3">
          <span className="shrink-0 w-6 h-6 rounded-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] text-xs font-bold flex items-center justify-center shadow-sm">
            {item.position}
          </span>

          <div className="flex-1 min-w-0">
            <div className="flex items-start gap-1.5">
              <TypeIcon type={item.type} />
              <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] leading-snug">
                {item.title}
              </h3>
            </div>

            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className="text-xs bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] rounded-full px-2 py-0.5">
                {TYPE_LABELS[item.type]}
              </span>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                ~{item.estimated_minutes} min
              </span>
              {item.has_certificate && (
                <span
                  className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full px-2 py-0.5"
                  title="Você já possui certificado neste tópico"
                >
                  ✓ Certificado
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Justification */}
        <p className="text-xs text-[hsl(var(--muted-foreground))] leading-relaxed border-l-2 border-[hsl(var(--border))] pl-3">
          {item.justification}
        </p>

        {/* Highlighted lessons */}
        {item.highlighted_lessons && item.highlighted_lessons.length > 0 && (
          <div className="space-y-1 pt-1">
            <p className="text-[10px] font-medium text-[hsl(var(--muted-foreground))] uppercase tracking-wide">
              Aulas mais relevantes para você
            </p>
            <ul className="space-y-0.5">
              {item.highlighted_lessons.map((lesson, i) => (
                <li key={i} className="flex items-center gap-1.5 text-xs text-[hsl(var(--foreground))]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[hsl(var(--primary))] shrink-0" />
                  {lesson}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 flex-wrap pt-0.5">
          {item.type === 'CEFIS_COURSE' && item.course_id && (
            <button
              onClick={handleStudy}
              className="inline-flex items-center gap-1.5 text-xs rounded-lg bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] px-3 py-1.5 hover:opacity-90 hover:shadow-md hover:shadow-[hsl(174_72%_42%/0.3)] transition-all font-semibold"
            >
              Estudar
              <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </button>
          )}

          <button
            onClick={() => handleContent('SUMMARY')}
            disabled={isGenerating}
            className={`inline-flex items-center gap-1.5 text-xs rounded-lg border border-[hsl(var(--border))] px-3 py-1.5 text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-all disabled:opacity-50 disabled:cursor-not-allowed ${glowClass(summaryGlows)}`}
          >
            <FileText className="h-3 w-3" aria-hidden="true" />
            Resumo
          </button>

          <button
            onClick={() => handleContent('APOSTILA')}
            disabled={isGenerating}
            className={`inline-flex items-center gap-1.5 text-xs rounded-lg border border-[hsl(var(--border))] px-3 py-1.5 text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-all disabled:opacity-50 disabled:cursor-not-allowed ${glowClass(apostilaGlows)}`}
          >
            <BookMarked className="h-3 w-3" aria-hidden="true" />
            Apostila
          </button>

          <button
            onClick={() => handleContent('PODCAST')}
            disabled={isGenerating}
            className={`inline-flex items-center gap-1.5 text-xs rounded-lg border border-[hsl(var(--border))] px-3 py-1.5 text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-all disabled:opacity-50 disabled:cursor-not-allowed ${glowClass(podcastGlows)}`}
          >
            <Mic className="h-3 w-3" aria-hidden="true" />
            Mini-Podcast
          </button>
        </div>
      </div>
    </div>
  );
}
