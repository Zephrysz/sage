'use client';

export interface PlanItem {
  id: string;
  position: number;
  type: 'CEFIS_COURSE' | 'GENERATED_CONTENT';
  title: string;
  estimated_minutes: number;
  justification: string;
  course_id?: string;
  has_certificate: boolean;
}

interface PlanItemCardProps {
  item: PlanItem;
  onGenerateSummary: (item: PlanItem) => void;
  onGenerateApostila: (item: PlanItem) => void;
  isGenerating?: boolean;
}

const TYPE_LABELS: Record<PlanItem['type'], string> = {
  CEFIS_COURSE: 'Curso CEFIS',
  GENERATED_CONTENT: 'Conteúdo Gerado',
};

export function PlanItemCard({
  item,
  onGenerateSummary,
  onGenerateApostila,
  isGenerating = false,
}: PlanItemCardProps) {
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start gap-3">
        <span className="shrink-0 w-6 h-6 rounded-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] text-xs font-bold flex items-center justify-center">
          {item.position}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] truncate">
              {item.title}
            </h3>
            {item.has_certificate && (
              <span
                className="text-xs bg-green-100 text-green-700 rounded-full px-2 py-0.5"
                title="Você já possui certificado neste tópico"
              >
                ✓ Certificado
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] rounded-full px-2 py-0.5">
              {TYPE_LABELS[item.type]}
            </span>
            <span className="text-xs text-[hsl(var(--muted-foreground))]">
              ~{item.estimated_minutes} min
            </span>
          </div>
        </div>
      </div>

      {/* Justification */}
      <p className="text-xs text-[hsl(var(--muted-foreground))] leading-relaxed">
        {item.justification}
      </p>

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => onGenerateSummary(item)}
          disabled={isGenerating}
          className="text-xs rounded-lg border border-[hsl(var(--border))] px-3 py-1.5 text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? 'Gerando...' : 'Gerar Resumo'}
        </button>
        <button
          onClick={() => onGenerateApostila(item)}
          disabled={isGenerating}
          className="text-xs rounded-lg border border-[hsl(var(--border))] px-3 py-1.5 text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? 'Gerando...' : 'Gerar Apostila'}
        </button>
        <button
          disabled
          title="Em breve"
          className="text-xs rounded-lg border border-[hsl(var(--border))] px-3 py-1.5 text-[hsl(var(--muted-foreground))] opacity-50 cursor-not-allowed"
        >
          Gerar Mini-Podcast
        </button>
      </div>
    </div>
  );
}
