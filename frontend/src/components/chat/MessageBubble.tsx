'use client';

export interface Message {
  id: string;
  role: 'user' | 'tutor';
  content: string;
}

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
          isUser
            ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-br-sm'
            : 'bg-[hsl(var(--muted))] text-[hsl(var(--foreground))] rounded-bl-sm'
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}
