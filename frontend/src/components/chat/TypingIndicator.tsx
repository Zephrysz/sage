'use client';

export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-[hsl(var(--muted))] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1">
        <span
          className="w-2 h-2 rounded-full bg-[hsl(var(--muted-foreground))] animate-bounce"
          style={{ animationDelay: '0ms', animationDuration: '1s' }}
        />
        <span
          className="w-2 h-2 rounded-full bg-[hsl(var(--muted-foreground))] animate-bounce"
          style={{ animationDelay: '200ms', animationDuration: '1s' }}
        />
        <span
          className="w-2 h-2 rounded-full bg-[hsl(var(--muted-foreground))] animate-bounce"
          style={{ animationDelay: '400ms', animationDuration: '1s' }}
        />
      </div>
    </div>
  );
}
