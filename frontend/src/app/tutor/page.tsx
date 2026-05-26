'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from '@/hooks/useSession';
import { apiRequest } from '@/lib/api';
import { StudyPlanList } from '@/components/plan/StudyPlanList';
import { DiagnosisQuestion, type DiagnosisQuestionData } from '@/components/diagnosis/DiagnosisQuestion';
import { DiagnosisResult, type DiagnosisResultData } from '@/components/diagnosis/DiagnosisResult';
import type { PlanItem } from '@/components/plan/PlanItemCard';

interface StudyPlan {
  items: PlanItem[];
  total_estimated_minutes: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

// ── SSE parser ────────────────────────────────────────────────────────────────
async function* parseSSE(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const event of events) {
      const lines = event.split('\n');
      const dataLines = lines.filter((l) => l.startsWith('data: ')).map((l) => l.slice(6));
      if (dataLines.length > 0) yield dataLines.join('\n');
    }
  }

  if (buffer.trim()) {
    const lines = buffer.split('\n');
    const dataLines = lines.filter((l) => l.startsWith('data: ')).map((l) => l.slice(6));
    if (dataLines.length > 0) yield dataLines.join('\n');
  }
}

// ── Markdown renderer ─────────────────────────────────────────────────────────
function MarkdownContent({ content, isUser }: { content: string; isUser: boolean }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="list-disc pl-4 mb-1 space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-4 mb-1 space-y-0.5">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        code: ({ children, className }) => {
          const isBlock = className?.includes('language-');
          return isBlock ? (
            <code className={`block rounded px-3 py-2 text-xs font-mono my-1 ${isUser ? 'bg-black/20' : 'bg-muted'}`}>{children}</code>
          ) : (
            <code className={`rounded px-1 py-0.5 text-xs font-mono ${isUser ? 'bg-black/20' : 'bg-muted'}`}>{children}</code>
          );
        },
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="underline opacity-80 hover:opacity-100">{children}</a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

// ── Diagnosis phase component ─────────────────────────────────────────────────
function DiagnosisPhase({
  sessionId,
  onComplete,
}: {
  sessionId: string;
  onComplete: (result: DiagnosisResultData) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [questions, setQuestions] = useState<DiagnosisQuestionData[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<DiagnosisResultData | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    (async () => {
      try {
        const data = await apiRequest<{ fallback: boolean; questions: DiagnosisQuestionData[] }>(
          '/diagnosis/start',
          { method: 'POST' },
          sessionId
        );
        if (data.fallback || data.questions.length === 0) {
          // Fallback: classified as Iniciante, skip to result
          onComplete({ level: 'iniciante', score: 0, gaps: [] });
          return;
        }
        setQuestions(data.questions);
      } catch {
        setError('Não foi possível carregar o diagnóstico. Tente novamente.');
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionId, onComplete]);

  const handleAnswer = useCallback((questionId: string, answer: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: answer }));
  }, []);

  const allAnswered = questions.length > 0 && questions.every((q) => answers[q.id]);

  const handleSubmit = async () => {
    if (!allAnswered || submitting) return;
    setSubmitting(true);
    try {
      const data = await apiRequest<DiagnosisResultData>(
        '/diagnosis/submit',
        {
          method: 'POST',
          body: JSON.stringify({ answers }),
        },
        sessionId
      );
      setResult(data);
    } catch {
      setError('Não foi possível enviar suas respostas. Tente novamente.');
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 px-4 py-8">
        <div className="w-full max-w-lg">
          <DiagnosisResult result={result} onContinue={() => onComplete(result)} />
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-4 px-4">
        <div className="flex gap-1">
          <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:0ms]" />
          <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:150ms]" />
          <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:300ms]" />
        </div>
        <p className="text-sm text-muted-foreground">Gerando diagnóstico personalizado...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 px-4 gap-3">
        <p className="text-sm text-destructive">{error}</p>
        <button
          onClick={() => { startedRef.current = false; setError(null); setLoading(true); }}
          className="text-xs underline text-muted-foreground hover:text-foreground"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Progress bar */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-muted-foreground">Diagnóstico de conhecimento</span>
          <span className="text-xs text-muted-foreground">
            {Object.keys(answers).length}/{questions.length} respondidas
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${(Object.keys(answers).length / questions.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Questions */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {questions.map((q, i) => (
          <DiagnosisQuestion
            key={q.id}
            question={q}
            questionNumber={i + 1}
            totalQuestions={questions.length}
            selectedAnswer={answers[q.id]}
            onAnswer={handleAnswer}
            disabled={submitting}
          />
        ))}

        {/* Submit */}
        <div className="pb-4">
          <button
            onClick={handleSubmit}
            disabled={!allAnswered || submitting}
            className="w-full rounded-xl bg-primary text-primary-foreground py-3 text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? 'Enviando...' : 'Enviar respostas'}
          </button>
          {!allAnswered && (
            <p className="text-center text-xs text-muted-foreground mt-2">
              Responda todas as perguntas para continuar
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TutorPage() {
  const router = useRouter();
  const { sessionId, state, user, studyPlan, setState, setStudyPlan } = useSession();

  const [messages, setMessages] = useState<{ role: 'user' | 'tutor'; text: string }[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [generatingItemId, setGeneratingItemId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const greetedRef = useRef(false);

  useEffect(() => {
    if (!sessionId) router.replace('/login');
  }, [sessionId, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    if (!sessionId || greetedRef.current) return;
    greetedRef.current = true;
    setMessages([{
      role: 'tutor',
      text: `Olá${user?.name ? `, **${user.name}**` : ''}! Sou o **CEFIS AI Tutor**. Vou te ajudar a montar um plano de estudos personalizado.\n\nPara começar, **em qual área você quer se desenvolver?**`,
    }]);
  }, [sessionId, user]);

  // Fetch plan when PLAN_READY
  useEffect(() => {
    if (state !== 'PLAN_READY' || studyPlan || planLoading || !sessionId) return;
    setPlanLoading(true);
    setPlanError(null);
    (async () => {
      try {
        const data = await apiRequest<StudyPlan>('/plan', {}, sessionId);
        setStudyPlan(data);
      } catch {
        setPlanError('Não foi possível carregar o plano de estudos. Tente novamente.');
      } finally {
        setPlanLoading(false);
      }
    })();
  }, [state, studyPlan, planLoading, sessionId, setStudyPlan]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isTyping || !sessionId) return;

    setInput('');
    setChatError(null);
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setIsTyping(true);

    try {
      const res = await fetch(`${API_URL}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      let accumulated = '';
      setMessages((prev) => [...prev, { role: 'tutor', text: '' }]);

      for await (const data of parseSSE(res.body)) {
        if (data === '[DONE]') break;

        if (data.startsWith('{')) {
          try {
            const parsed = JSON.parse(data);
            if (parsed.state) setState(parsed.state as typeof state);
            if (parsed.plan) setStudyPlan(parsed.plan);
            if (parsed.service_unavailable) {
              setChatError('Serviço indisponível. Não foi possível processar sua dúvida.');
              break;
            }
            continue;
          } catch { /* treat as text */ }
        }

        accumulated += data;
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { role: 'tutor', text: accumulated };
          return updated;
        });
      }

      // After confirmation, backend transitions to DIAGNOSIS — re-read session state
      // The state update comes via the session store on next render
    } catch {
      setChatError('Não foi possível processar sua mensagem. Tente novamente.');
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsTyping(false);
      inputRef.current?.focus();
    }
  }, [input, isTyping, sessionId, setState, setStudyPlan, state]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleDiagnosisComplete = useCallback((result: DiagnosisResultData) => {
    setState('PLAN_READY');
    setMessages((prev) => [
      ...prev,
      {
        role: 'tutor',
        text: `Diagnóstico concluído! Nível identificado: **${
          result.level === 'iniciante' ? 'Iniciante' :
          result.level === 'intermediario' ? 'Intermediário' : 'Avançado'
        }** (${Math.round(result.score * 100)}% de acertos).\n\nEstou montando seu plano de estudos personalizado...`,
      },
    ]);
  }, [setState]);

  const handleGenerateSummary = useCallback((item: PlanItem) => {
    if (!sessionId) return;
    setGeneratingItemId(item.id);
    setTimeout(() => setGeneratingItemId(null), 100);
  }, [sessionId]);

  const handleGenerateApostila = useCallback((item: PlanItem) => {
    if (!sessionId) return;
    setGeneratingItemId(item.id);
    setTimeout(() => setGeneratingItemId(null), 100);
  }, [sessionId]);

  const isPlanReady = state === 'PLAN_READY' || state === 'STUDY_MODE';
  const isDiagnosis = state === 'DIAGNOSIS';
  const isChatActive = state === 'ONBOARDING' || state === 'AWAITING_CONFIRMATION';

  if (!sessionId) return null;

  return (
    <main className="flex h-screen overflow-hidden bg-background">
      {/* ── Left panel: chat OR diagnosis ────────────────────────────────────── */}
      <section
        className={`flex flex-col ${isPlanReady ? 'w-full md:w-2/5' : 'w-full max-w-2xl mx-auto'} border-r border-border`}
        aria-label={isDiagnosis ? 'Diagnóstico' : 'Chat com o tutor'}
      >
        {/* Header */}
        <header className="flex items-center gap-3 border-b border-border px-4 py-3 bg-card shrink-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold text-sm select-none">
            AI
          </div>
          <div>
            <p className="font-semibold text-sm text-foreground">CEFIS AI Tutor</p>
            {user?.name && <p className="text-xs text-muted-foreground">{user.name}</p>}
          </div>
          <span className="ml-auto text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5">
            {state === 'ONBOARDING' && 'Onboarding'}
            {state === 'AWAITING_CONFIRMATION' && 'Confirmação'}
            {state === 'DIAGNOSIS' && 'Diagnóstico'}
            {state === 'PLAN_READY' && 'Plano pronto'}
            {state === 'STUDY_MODE' && 'Modo estudo'}
          </span>
        </header>

        {/* ── DIAGNOSIS phase ── */}
        {isDiagnosis && sessionId && (
          <DiagnosisPhase sessionId={sessionId} onComplete={handleDiagnosisComplete} />
        )}

        {/* ── CHAT phase (onboarding + awaiting confirmation + plan ready chat) ── */}
        {!isDiagnosis && (
          <>
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {messages.map((msg, i) => {
                const isUser = msg.role === 'user';
                return (
                  <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                      isUser
                        ? 'bg-primary text-primary-foreground rounded-br-sm'
                        : 'bg-muted text-foreground rounded-bl-sm'
                    }`}>
                      <MarkdownContent content={msg.text} isUser={isUser} />
                    </div>
                  </div>
                );
              })}

              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1 items-center">
                    <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:0ms]" />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:150ms]" />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              )}

              {chatError && <p className="text-center text-xs text-destructive">{chatError}</p>}
              <div ref={messagesEndRef} />
            </div>

            {/* Input — only shown during chat states */}
            {isChatActive && (
              <div className="border-t border-border bg-card px-4 py-3 shrink-0">
                <div className="flex items-center gap-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Digite sua mensagem..."
                    disabled={isTyping}
                    className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label="Mensagem para o tutor"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={isTyping || !input.trim()}
                    className="shrink-0 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Enviar
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Study Plan panel ─────────────────────────────────────────────────── */}
      {isPlanReady && (
        <section className="hidden md:flex flex-col flex-1 overflow-hidden" aria-label="Plano de estudos">
          <header className="border-b border-border px-6 py-3 bg-card shrink-0">
            <h2 className="font-semibold text-sm text-foreground">Plano de Estudos</h2>
          </header>
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {planLoading && (
              <div className="flex flex-col gap-3">
                {[1, 2, 3].map((n) => <div key={n} className="h-28 rounded-lg bg-muted animate-pulse" />)}
                <p className="text-center text-xs text-muted-foreground mt-2">Montando seu plano de estudos...</p>
              </div>
            )}
            {planError && !planLoading && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                <p>{planError}</p>
                <button
                  onClick={() => { setPlanError(null); setStudyPlan(null as unknown as StudyPlan); }}
                  className="mt-2 text-xs underline hover:no-underline"
                >Tentar novamente</button>
              </div>
            )}
            {studyPlan && !planLoading && (
              <StudyPlanList
                plan={studyPlan}
                onGenerateSummary={handleGenerateSummary}
                onGenerateApostila={handleGenerateApostila}
                generatingItemId={generatingItemId}
              />
            )}
          </div>
        </section>
      )}

      {/* ── Mobile plan drawer ───────────────────────────────────────────────── */}
      {isPlanReady && (
        <div className="md:hidden fixed bottom-0 left-0 right-0 z-10 max-h-[40vh] overflow-y-auto border-t border-border bg-background px-4 py-3">
          {planLoading && <p className="text-center text-xs text-muted-foreground py-2">Montando seu plano de estudos...</p>}
          {studyPlan && !planLoading && (
            <StudyPlanList
              plan={studyPlan}
              onGenerateSummary={handleGenerateSummary}
              onGenerateApostila={handleGenerateApostila}
              generatingItemId={generatingItemId}
            />
          )}
        </div>
      )}
    </main>
  );
}
