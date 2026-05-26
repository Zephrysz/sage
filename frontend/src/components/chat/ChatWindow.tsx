'use client';

import { useEffect, useRef, useState, KeyboardEvent } from 'react';
import { Send } from 'lucide-react';
import { MessageBubble, type Message } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';

interface ChatWindowProps {
  messages: Message[];
  isStreaming: boolean;
  streamingText?: string;
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatWindow({
  messages,
  isStreaming,
  streamingText,
  onSend,
  disabled = false,
  placeholder = 'Digite sua mensagem...',
}: ChatWindowProps) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom whenever messages or streaming text changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, isStreaming]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSend(trimmed);
    setInput('');
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  const canSend = input.trim().length > 0 && !disabled && !isStreaming;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 min-h-0">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Streaming tutor message */}
        {isStreaming && streamingText && (
          <MessageBubble
            message={{ id: 'streaming', role: 'tutor', content: streamingText }}
          />
        )}

        {/* Typing indicator — shown while waiting for first chunk */}
        {isStreaming && !streamingText && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-[hsl(var(--border))] px-4 py-3 bg-[hsl(var(--background))]">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={placeholder}
            disabled={disabled || isStreaming}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
            style={{ minHeight: '40px', maxHeight: '120px' }}
            aria-label="Mensagem"
          />
          <button
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Enviar mensagem"
            className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-xl bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
