'use client';

import { useCallback, useRef, useState } from 'react';
import { Send, PanelRightClose, PanelRightOpen } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { TypingIndicator } from '@/components/chat/TypingIndicator';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ChatMessage {
  id: string;
  role: 'user' | 'tutor';
  content: string;
  sources?: SourceRef[];
}

interface SourceRef {
  label: string;   // "Fonte: [Curso] — [Aula]"
  url?: string;    // lesson URL if available
}

interface StudyChatbotProps {
  sessionId: string;
  courseTitle?: string;
  /** Lesson list from the current course — used to resolve source URLs by lesson_id */
  lessons?: { id?: string | number; title: string; url?: string }[];
  /** Controlled open state — if provided, renders a toggle button */
  open?: boolean;
  onToggle?: () => void;
}

// Parse SSE stream from a ReadableStream
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

// Extract "Fonte: ..." lines and resolve URLs from lesson list
function extractSources(
  raw: string,
  lessons?: { id?: string | number; title: string; url?: string }[],
): { text: string; sources: SourceRef[] } {
  const lines = raw.split('\n');
  const sources: SourceRef[] = [];
  const textLines: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (/^Fonte:\s/.test(trimmed)) {
      // Parse lesson_id tag: "Fonte: [Curso] — [Aula] [lesson_id:123]"
      const lessonIdMatch = trimmed.match(/\[lesson_id:([^\]]+)\]/);
      const lessonId = lessonIdMatch?.[1]?.trim();
      // Clean label — remove the lesson_id tag for display
      const label = trimmed.replace(/\s*\[lesson_id:[^\]]+\]/, '');

      let url: string | undefined;
      if (lessonId && lessons) {
        const match = lessons.find((l) => String(l.id) === lessonId);
        url = match?.url;
      }
      sources.push({ label, url });
    } else {
      textLines.push(line);
    }
  }

  return { text: textLines.join('\n').trim(), sources };
}

function TutorMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-1.5 last:mb-0 leading-relaxed">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="list-disc pl-4 mb-1.5 space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-4 mb-1.5 space-y-0.5">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="w-full text-xs border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-[hsl(var(--muted))]">{children}</thead>,
        th: ({ children }) => (
          <th className="border border-[hsl(var(--border))] px-2 py-1 text-left font-semibold">{children}</th>
        ),
        td: ({ children }) => (
          <td className="border border-[hsl(var(--border))] px-2 py-1">{children}</td>
        ),
        code: ({ children, className }) => {
          const isBlock = className?.includes('language-');
          return isBlock ? (
            <code className="block rounded bg-[hsl(var(--background))] border border-[hsl(var(--border))] px-3 py-2 text-xs font-mono my-1.5 overflow-x-auto">
              {children}
            </code>
          ) : (
            <code className="rounded bg-[hsl(var(--background))] border border-[hsl(var(--border))] px-1 py-0.5 text-xs font-mono">
              {children}
            </code>
          );
        },
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="underline opacity-80 hover:opacity-100">
            {children}
          </a>
        ),
        h1: ({ children }) => <h1 className="text-sm font-bold mt-2 mb-1">{children}</h1>,
        h2: ({ children }) => <h2 className="text-xs font-bold mt-2 mb-1">{children}</h2>,
        h3: ({ children }) => <h3 className="text-xs font-semibold mt-1.5 mb-0.5">{children}</h3>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-[hsl(var(--primary))] pl-3 my-1.5 opacity-80">
            {children}
          </blockquote>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function MessageBubble({
  message,
  lessons,
}: {
  message: ChatMessage;
  lessons?: { title: string; url?: string }[];
}) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[90%] rounded-2xl px-3 py-2.5 text-xs ${
          isUser
            ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-br-sm'
            : 'bg-[hsl(var(--card))] text-[hsl(var(--foreground))] rounded-bl-sm border border-[hsl(var(--border))] border-l-2 border-l-[hsl(var(--primary))] shadow-sm'
        }`}
      >
        {isUser ? (
          <p className="leading-relaxed">{message.content}</p>
        ) : (
          <TutorMarkdown content={message.content} />
        )}

        {/* Source references */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 pt-2 border-t border-[hsl(var(--border))]/40 space-y-1">
            <p className="text-[10px] font-medium text-[hsl(var(--muted-foreground))] uppercase tracking-wide">
              Fontes RAG
            </p>
            {message.sources.map((src, i) => (
              src.url ? (
                <a
                  key={i}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-[10px] text-[hsl(var(--primary))] hover:underline truncate"
                  title={src.label}
                >
                  📖 {src.label.replace(/^Fonte:\s*/, '')}
                </a>
              ) : (
                <p key={i} className="text-[10px] text-[hsl(var(--muted-foreground))] italic truncate" title={src.label}>
                  📖 {src.label.replace(/^Fonte:\s*/, '')}
                </p>
              )
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function StudyChatbot({ sessionId, courseTitle, lessons, open, onToggle }: StudyChatbotProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isTyping) return;

    setInput('');
    setError(null);

    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const userMsg: ChatMessage = { id: `user-${Date.now()}`, role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setIsTyping(true);
    setTimeout(scrollToBottom, 50);

    try {
      const res = await fetch(`${API_URL}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      const tutorMsgId = `tutor-${Date.now()}`;
      let accumulated = '';

      setMessages((prev) => [...prev, { id: tutorMsgId, role: 'tutor', content: '', sources: [] }]);

      for await (const data of parseSSE(res.body)) {
        if (data === '[DONE]') break;

        if (data.startsWith('{')) {
          try {
            const parsed = JSON.parse(data);
            if (parsed.service_unavailable) {
              setError('Serviço indisponível. Não foi possível processar sua dúvida.');
              break;
            }
            continue;
          } catch { /* treat as text */ }
        }

        accumulated += data;
        const { text: bodyText, sources } = extractSources(accumulated, lessons);

        setMessages((prev) =>
          prev.map((m) => m.id === tutorMsgId ? { ...m, content: bodyText, sources } : m)
        );
        setTimeout(scrollToBottom, 50);
      }
    } catch {
      setError('Não foi possível processar sua dúvida. Tente novamente.');
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === 'tutor' && last.content === '') return prev.slice(0, -1);
        return prev;
      });
    } finally {
      setIsTyping(false);
      setTimeout(scrollToBottom, 100);
    }
  }, [input, isTyping, sessionId, scrollToBottom, lessons]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  const canSend = input.trim().length > 0 && !isTyping;

  return (
    <div className="flex flex-col h-full min-h-0 bg-[hsl(var(--background))] border-l border-[hsl(var(--border))]">
      {/* Header with collapse toggle */}
      <div className="flex items-center gap-2 px-3 py-3 border-b border-[hsl(var(--border))] bg-[hsl(var(--card))] shrink-0">
        {onToggle && (
          <button
            onClick={onToggle}
            aria-label={open ? 'Ocultar chat' : 'Mostrar chat'}
            className="flex items-center justify-center w-6 h-6 rounded-md text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors shrink-0"
          >
            {open ? <PanelRightClose size={13} /> : <PanelRightOpen size={13} />}
          </button>
        )}
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[hsl(174_72%_42%/0.15)] border border-[hsl(174_72%_42%/0.4)] shrink-0">
          <img src="/cefis-logo.svg" alt="CEFIS" width={16} height={16} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-[hsl(var(--foreground))] truncate">Tutor IA</p>
          {courseTitle && (
            <p className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">{courseTitle}</p>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[hsl(174_72%_42%/0.15)] border border-[hsl(174_72%_42%/0.3)]">
              <img src="/cefis-logo.svg" alt="" width={20} height={20} aria-hidden="true" />
            </div>
            <p className="text-xs text-[hsl(var(--muted-foreground))] leading-relaxed">
              Tire suas dúvidas sobre o conteúdo desta aula. As respostas são baseadas no material do curso.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} lessons={lessons} />
        ))}

        {isTyping && messages[messages.length - 1]?.role !== 'tutor' && <TypingIndicator />}

        {error && (
          <p className="text-center text-[10px] text-[hsl(var(--destructive))] px-2">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-[hsl(var(--border))] px-3 py-2.5 bg-[hsl(var(--background))] shrink-0">
        <div className="flex items-end gap-2 min-w-0">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder="Pergunte sobre esta aula..."
            disabled={isTyping}
            rows={1}
            className="flex-1 min-w-0 resize-none rounded-xl border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 py-2 text-xs text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ minHeight: '36px', maxHeight: '120px' }}
            aria-label="Pergunta sobre a aula"
          />
          <button
            onClick={sendMessage}
            disabled={!canSend}
            aria-label="Enviar pergunta"
            className="shrink-0 flex items-center justify-center w-9 h-9 min-w-[36px] rounded-xl bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
