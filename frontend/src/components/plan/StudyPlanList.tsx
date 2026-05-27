'use client';

import { PlanItemCard, type PlanItem } from './PlanItemCard';

interface StudyPlan {
  items: PlanItem[];
  total_estimated_minutes: number;
}

export interface StudyPlanListProps {
  plan: StudyPlan;
  generatingItemId: string | null;
  learningStyle?: 'video' | 'leitura' | 'audio' | 'cinestetico' | null;
  onGenerateSummary: (item: PlanItem) => void;
  onGenerateApostila: (item: PlanItem) => void;
  onGeneratePodcast: (item: PlanItem) => void;
}

export function StudyPlanList({
  plan,
  generatingItemId,
  learningStyle,
  onGenerateSummary,
  onGenerateApostila,
  onGeneratePodcast,
}: StudyPlanListProps) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        {plan.items.length} item{plan.items.length !== 1 ? 's' : ''} ·{' '}
        ~{plan.total_estimated_minutes} min no total
      </p>
      {plan.items.map((item) => (
        <PlanItemCard
          key={item.id}
          item={item}
          learningStyle={learningStyle}
          onGenerateSummary={onGenerateSummary}
          onGenerateApostila={onGenerateApostila}
          onGeneratePodcast={onGeneratePodcast}
          isGenerating={generatingItemId === item.id}
        />
      ))}
    </div>
  );
}
