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
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {question.topic}
        </span>
        <span className="text-xs text-muted-foreground">
          {questionNumber} / {totalQuestions}
        </span>
      </div>

      <p className="text-sm font-medium text-foreground leading-relaxed">
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
              className={`w-full flex items-start gap-3 rounded-xl border px-4 py-3 text-left text-sm transition-colors disabled:cursor-not-allowed ${
                isSelected
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background text-foreground hover:bg-muted disabled:opacity-50'
              }`}
            >
              <span className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                isSelected ? 'bg-primary-foreground text-primary' : 'bg-muted text-muted-foreground'
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
