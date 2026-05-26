'use client';

export interface Gap {
  topic: string;
  is_critical: boolean;
  wrong_count: number;
}

export type DiagnosisLevel = 'iniciante' | 'intermediario' | 'avancado';

export interface DiagnosisResultData {
  level: DiagnosisLevel;
  score: number;
  gaps: Gap[];
}

interface DiagnosisResultProps {
  result: DiagnosisResultData;
  onContinue: () => void;
}

const LEVEL_CONFIG: Record<
  DiagnosisLevel,
  { label: string; color: string; bg: string; description: string }
> = {
  iniciante: {
    label: 'Iniciante',
    color: 'text-orange-700',
    bg: 'bg-orange-100',
    description: 'Você está começando sua jornada nessa área.',
  },
  intermediario: {
    label: 'Intermediário',
    color: 'text-blue-700',
    bg: 'bg-blue-100',
    description: 'Você já tem uma base sólida para avançar.',
  },
  avancado: {
    label: 'Avançado',
    color: 'text-green-700',
    bg: 'bg-green-100',
    description: 'Você domina bem os fundamentos da área.',
  },
};

export function DiagnosisResult({ result, onContinue }: DiagnosisResultProps) {
  const config = LEVEL_CONFIG[result.level];
  const topGaps = result.gaps.slice(0, 3);
  const scorePercent = Math.round(result.score * 100);

  return (
    <div className="rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-6 shadow-sm space-y-5">
      {/* Level badge */}
      <div className="flex flex-col items-center gap-2 text-center">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-semibold ${config.bg} ${config.color}`}
        >
          Nível: {config.label}
        </span>
        <p className="text-xs text-[hsl(var(--muted-foreground))]">
          {scorePercent}% de acertos — {config.description}
        </p>
      </div>

      {/* Gaps */}
      {topGaps.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wide">
            Principais lacunas identificadas
          </p>
          <ul className="space-y-2">
            {topGaps.map((gap) => (
              <li
                key={gap.topic}
                className="flex items-center gap-2 rounded-lg bg-[hsl(var(--muted))] px-3 py-2 text-sm"
              >
                {gap.is_critical && (
                  <span
                    className="flex-shrink-0 text-red-500"
                    title="Lacuna crítica"
                    aria-label="Lacuna crítica"
                  >
                    ⚠️
                  </span>
                )}
                <span className="text-[hsl(var(--foreground))]">{gap.topic}</span>
                {gap.is_critical && (
                  <span className="ml-auto text-xs text-red-500 font-medium">Crítica</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {topGaps.length === 0 && (
        <p className="text-sm text-center text-[hsl(var(--muted-foreground))]">
          Nenhuma lacuna crítica identificada. Ótimo trabalho!
        </p>
      )}

      {/* CTA */}
      <button
        onClick={onContinue}
        className="w-full rounded-xl bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] py-2.5 text-sm font-medium hover:opacity-90 transition-opacity"
      >
        Ver meu plano de estudos
      </button>
    </div>
  );
}
