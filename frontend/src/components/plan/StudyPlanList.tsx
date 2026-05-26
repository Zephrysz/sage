'use client';

import { PlanItemCard, type PlanItem } from './PlanItemCard';

interface StudyPlan {
  items: PlanItem[];
  total_estimated_minutes: number;
}

export interface StudyPlanListProps {
  plan: StudyPlan;
  generatingItemId: string | null;
  onGenerateSummary: (item: PlanItem) => void;
  onGenerateApostila: (item: PlanItem) => void;
}

export function StudyPlanList({
  plan,
  generatingItemId,
  onGenerateSummary,
  onGenerateApostila,
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
          onGenerateSummary={onGenerateSummary}
          onGenerateApostila={onGenerateApostila}
          isGenerating={generatingItemId === item.id}
        />
      ))}
    </div>
  );
}
