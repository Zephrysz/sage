'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send } from 'lucide-react';
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

// ── User avatar ───────────────────────────────────────────────────────────────
function UserAvatar({ name }: { name?: string }) {
  if (name) {
    const parts = name.trim().split(/\s+/);
    const initials =
      parts.length >= 2
        ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
        : parts[0].slice(0, 2).toUpperCase();
    return (
      <div
        className="shrink-0 w-7 h-7 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[10px] font-bold flex items-center justify-center select-none"
        aria-label={`Avatar de ${name}`}
      >
        {initials}
      </div>
    );
  }
  // Generic person icon
  return (
    <div
      className="shrink-0 w-7 h-7 rounded-full bg-[hsl(var(--muted))] border border-[hsl(var(--border))] flex items-center justify-center"
      aria-label="Usuário"
    >
      <svg viewBox="0 0 24 24" className="w-4 h-4 text-[hsl(var(--muted-foreground))]" fill="currentColor" aria-hidden="true">
        <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
      </svg>
    </div>
  );
}

// ── Tutor avatar ──────────────────────────────────────────────────────────────
function TutorAvatar() {
  return (
    <div
      className="shrink-0 w-7 h-7 rounded-full bg-[hsl(174_72%_42%/0.15)] border border-[hsl(174_72%_42%/0.4)] flex items-center justify-center"
      aria-label="CEFIS AI Tutor"
    >
      <img src="/cefis-logo.svg" alt="" width={16} height={16} aria-hidden="true" />
    </div>
  );
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
            <code className={`block rounded px-3 py-2 text-xs font-mono my-1 ${isUser ? 'bg-black/20' : 'bg-[hsl(var(--muted))]'}`}>{children}</code>
          ) : (
            <code className={`rounded px-1 py-0.5 text-xs font-mono ${isUser ? 'bg-black/20' : 'bg-[hsl(var(--muted))]'}`}>{children}</code>
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
      <div className="px-5 pt-4 pb-2">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-muted-foreground font-medium">Diagnóstico de conhecimento</span>
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
      <div className="flex-1 overflow-y-auto px-5 py-3 space-y-4">
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
  const {
    sessionId, state, user, studyPlan,
    messages, setState, setStudyPlan, addMessage, updateLastMessage, setMessages, learningStyle,
  } = useSession();

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
    if (!sessionId || greetedRef.current || messages.length > 0) return;
    greetedRef.current = true;
    addMessage({
      role: 'tutor',
      text: `Olá${user?.name ? `, **${user.name}**` : ''}! Sou o **CEFIS AI Tutor**. Vou te ajudar a montar um plano de estudos personalizado.\n\nPara começar, **em qual área você quer se desenvolver?**`,
    });
  }, [sessionId, user, messages.length, addMessage]);

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
    addMessage({ role: 'user', text });
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
      addMessage({ role: 'tutor', text: '' });

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
        updateLastMessage(accumulated);
      }
    } catch {
      setChatError('Não foi possível processar sua mensagem. Tente novamente.');
      setMessages(messages.filter((_, i) => i < messages.length - 1));
    } finally {
      setIsTyping(false);
      inputRef.current?.focus();
    }
  }, [input, isTyping, sessionId, setState, setStudyPlan, state, addMessage, updateLastMessage, setMessages, messages]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleDiagnosisComplete = useCallback((result: DiagnosisResultData) => {
    setState('PLAN_READY');
    addMessage({
      role: 'tutor',
      text: `Diagnóstico concluído! Nível identificado: **${
        result.level === 'iniciante' ? 'Iniciante' :
        result.level === 'intermediario' ? 'Intermediário' : 'Avançado'
      }** (${Math.round(result.score * 100)}% de acertos).\n\nEstou montando seu plano de estudos personalizado...`,
    });
  }, [setState, addMessage]);

  const handleGenerateContent = useCallback(async (item: PlanItem, type: 'SUMMARY' | 'APOSTILA') => {
    if (!sessionId) return;
    router.push(`/tutor/content/${item.id}?type=${type}&title=${encodeURIComponent(item.title)}`);
  }, [sessionId, router]);

  const handleGenerateSummary = useCallback((item: PlanItem) => {
    handleGenerateContent(item, 'SUMMARY');
  }, [handleGenerateContent]);

  const handleGenerateApostila = useCallback((item: PlanItem) => {
    handleGenerateContent(item, 'APOSTILA');
  }, [handleGenerateContent]);

  const handleGeneratePodcast = useCallback((item: PlanItem) => {
    if (!sessionId) return;
    router.push(`/tutor/content/${item.id}?type=PODCAST&title=${encodeURIComponent(item.title)}`);
  }, [sessionId, router]);

  const isPlanReady = state === 'PLAN_READY' || state === 'STUDY_MODE';
  const isDiagnosis = state === 'DIAGNOSIS';
  const isChatActive = state === 'ONBOARDING' || state === 'AWAITING_CONFIRMATION';

  if (!sessionId) return null;

  return (
    <main className="flex h-screen overflow-hidden bg-[hsl(var(--background))] bg-pink">
      {/* ── Left panel: chat OR diagnosis ────────────────────────────────────── */}
      <section
        className={`flex flex-col ${isPlanReady ? 'w-full md:w-2/5' : 'w-full max-w-2xl mx-auto'} border border-[hsl(var(--border))]`}
        aria-label={isDiagnosis ? 'Diagnóstico' : 'Chat com o tutor'}
      >
        {/* Header */}
        <header className="flex items-center gap-3 border-b border-[hsl(var(--border))] px-5 py-3.5 bg-[hsl(var(--card))] shrink-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[hsl(174_72%_42%/0.15)] border border-[hsl(174_72%_42%/0.4)] select-none">
            <img src="/cefis-logo.svg" alt="CEFIS" width={20} height={20} />
          </div>
          <div>
            <p className="font-semibold text-sm text-[hsl(var(--foreground))]">CEFIS AI Tutor</p>
            {user?.name && <p className="text-xs text-[hsl(var(--muted-foreground))]">{user.name}</p>}
          </div>
          <span className="ml-auto text-xs text-[hsl(var(--muted-foreground))] bg-[hsl(var(--muted))] rounded-full px-2.5 py-0.5">
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

        {/* ── CHAT phase ── */}
        {!isDiagnosis && (
          <>
            <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
              {messages.map((msg, i) => {
                const isUser = msg.role === 'user';
                return (
                  <div key={i} className={`flex items-end gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
                    {/* Tutor avatar on the left */}
                    {!isUser && <TutorAvatar />}

                    <div className={`max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                      isUser
                        ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-br-sm'
                        : 'bg-[hsl(var(--card))] text-[hsl(var(--foreground))] rounded-bl-sm border border-[hsl(var(--border))] border-l-2 border-l-[hsl(var(--primary))] shadow-sm'
                    }`}>
                      <MarkdownContent content={msg.text} isUser={isUser} />
                    </div>

                    {/* User avatar on the right */}
                    {isUser && <UserAvatar name={user?.name} />}
                  </div>
                );
              })}

              {isTyping && (
                <div className="flex items-end gap-2 justify-start">
                  <TutorAvatar />
                  <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] border-l-2 border-l-[hsl(var(--primary))] rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1 items-center shadow-sm">
                    <span className="h-2 w-2 rounded-full bg-[hsl(var(--muted-foreground))] animate-bounce [animation-delay:0ms]" />
                    <span className="h-2 w-2 rounded-full bg-[hsl(var(--muted-foreground))] animate-bounce [animation-delay:150ms]" />
                    <span className="h-2 w-2 rounded-full bg-[hsl(var(--muted-foreground))] animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              )}

              {chatError && <p className="text-center text-xs text-destructive">{chatError}</p>}
              <div ref={messagesEndRef} />
            </div>

            {/* Input — pill style with integrated send button */}
            {isChatActive && (
              <div className="border-t border-[hsl(var(--border))] bg-[hsl(var(--card))] px-5 py-4 shrink-0">
                <div className="flex items-center gap-2 rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-4 py-2 focus-within:ring-2 focus-within:ring-[hsl(var(--ring))] transition-shadow">
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Digite sua mensagem..."
                    className="flex-1 bg-transparent text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none"
                    aria-label="Mensagem para o tutor"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={isTyping || !input.trim()}
                    className="shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] transition-all hover:opacity-90 hover:shadow-md hover:shadow-[hsl(174_72%_42%/0.3)] disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label="Enviar mensagem"
                  >
                    <Send className="w-3.5 h-3.5" aria-hidden="true" />
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
          <header className="border-b border-[hsl(var(--border))] px-6 py-3.5 shrink-0 bg-[hsl(var(--card))]">
            <div className="flex items-center gap-2">
              <div className="w-1 h-5 rounded-full bg-[hsl(var(--primary))]" aria-hidden="true" />
              <h2 className="font-semibold text-sm text-[hsl(var(--foreground))]">Plano de Estudos</h2>
            </div>
          </header>
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {planLoading && (
              <div className="flex flex-col gap-3">
                {[1, 2, 3].map((n) => <div key={n} className="h-28 rounded-xl bg-[hsl(var(--muted))] animate-pulse" />)}
                <p className="text-center text-xs text-[hsl(var(--muted-foreground))] mt-2">Montando seu plano de estudos...</p>
              </div>
            )}
            {planError && !planLoading && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                <p>{planError}</p>
                <button onClick={() => { setPlanError(null); setStudyPlan(null as unknown as StudyPlan); }} className="mt-2 text-xs underline hover:no-underline">Tentar novamente</button>
              </div>
            )}
            {studyPlan && !planLoading && (
              studyPlan.items.length === 0 ? (
                <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/40 p-6 text-center space-y-2">
                  <p className="text-sm font-medium text-[hsl(var(--foreground))]">Nenhum curso encontrado no catálogo para seu perfil no momento.</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">O catálogo da CEFIS pode não ter cursos relacionados ao seu objetivo atual.</p>
                </div>
              ) : (
                <StudyPlanList
                  plan={studyPlan}
                  learningStyle={learningStyle}
                  onGenerateSummary={handleGenerateSummary}
                  onGenerateApostila={handleGenerateApostila}
                  onGeneratePodcast={handleGeneratePodcast}
                  generatingItemId={generatingItemId}
                />
              )
            )}
          </div>
        </section>
      )}

      {/* ── Mobile plan drawer ───────────────────────────────────────────────── */}
      {isPlanReady && (
        <div className="md:hidden fixed bottom-0 left-0 right-0 z-10 max-h-[40vh] overflow-y-auto border-t border-[hsl(var(--border))] bg-[hsl(var(--background))] px-4 py-3">
          {planLoading && <p className="text-center text-xs text-[hsl(var(--muted-foreground))] py-2">Montando seu plano de estudos...</p>}
          {studyPlan && !planLoading && (
            studyPlan.items.length === 0 ? (
              <p className="text-center text-xs text-[hsl(var(--muted-foreground))] py-3">
                Nenhum curso encontrado no catálogo para seu perfil no momento.
              </p>
            ) : (
              <StudyPlanList
                plan={studyPlan}
                learningStyle={learningStyle}
                onGenerateSummary={handleGenerateSummary}
                onGenerateApostila={handleGenerateApostila}
                onGeneratePodcast={handleGeneratePodcast}
                generatingItemId={generatingItemId}
              />
            )
          )}
        </div>
      )}

    </main>
  );
}
