'use client';

export interface DiagnosisQuestionData {
  id: string;
  text: string;
  options: { A: string; B: string; C: string; D: string; E?: string };
  topic: string;
}

interface DiagnosisQuestionProps {
  question: DiagnosisQuestionData;
  questionNumber: number;
  totalQuestions: number;
  selectedAnswer?: string;
  onAnswer: (questionId: string, answer: string) => void;
  disabled?: boolean;
}

const OPTION_KEYS = ['A', 'B', 'C', 'D', 'E'] as const;

export function DiagnosisQuestion({
  question,
  questionNumber,
  totalQuestions,
  selectedAnswer,
  onAnswer,
  disabled = false,
}: DiagnosisQuestionProps) {
  return (
    <div className="rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 shadow-sm space-y-4 border-l-2 border-l-[hsl(var(--primary))]">
      {/* Header: question number only — topic removed (spoiler) */}
      <div className="flex items-center justify-end">
        <span className="text-xs text-[hsl(var(--muted-foreground))]">
          {questionNumber} / {totalQuestions}
        </span>
      </div>

      <p className="text-sm font-medium text-[hsl(var(--foreground))] leading-relaxed">
        {question.text}
      </p>

      <div className="space-y-2">
        {OPTION_KEYS.filter((key) => question.options[key]).map((key) => {
          const isSelected = selectedAnswer === key;
          return (
            <button
              key={key}
              onClick={() => onAnswer(question.id, key)}
              disabled={disabled}
              aria-pressed={isSelected}
              className={`w-full flex items-start gap-3 rounded-xl border px-4 py-3 text-left text-sm transition-all disabled:cursor-not-allowed ${
                isSelected
                  ? 'border-[hsl(var(--primary))] bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-md shadow-[hsl(174_72%_42%/0.25)]'
                  : 'border-[hsl(var(--border))] bg-[hsl(var(--background))] text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] hover:border-[hsl(var(--primary)/0.4)] disabled:opacity-50'
              }`}
            >
              <span className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                isSelected
                  ? 'bg-white/20 text-[hsl(var(--primary-foreground))]'
                  : 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]'
              }`}>
                {key}
              </span>
              <span className="leading-relaxed">{question.options[key]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
