'use client';

import { useEffect, useRef, useState } from 'react';
import { ExternalLink, VideoOff } from 'lucide-react';

interface VideoPlayerProps {
  streamSources?: string[];
  lessonTitle?: string;
  lessonUrl?: string;
}

type PlayerState = 'loading' | 'playing' | 'fallback';

const LOAD_TIMEOUT_MS = 8000;

export function VideoPlayer({ streamSources, lessonTitle, lessonUrl }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [playerState, setPlayerState] = useState<PlayerState>('loading');

  useEffect(() => {
    // Reset state when sources change
    setPlayerState('loading');

    const video = videoRef.current;
    if (!video) return;

    // No sources available — go straight to fallback
    if (!streamSources || streamSources.length === 0) {
      setPlayerState('fallback');
      return;
    }

    // Set a timeout: if the video hasn't started loading within LOAD_TIMEOUT_MS, show fallback
    timeoutRef.current = setTimeout(() => {
      setPlayerState('fallback');
    }, LOAD_TIMEOUT_MS);

    const handleCanPlay = () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setPlayerState('playing');
    };

    const handleError = () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setPlayerState('fallback');
    };

    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('error', handleError);

    // Load the video
    video.load();

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('error', handleError);
    };
  }, [streamSources]);

  const hasSources = streamSources && streamSources.length > 0;

  return (
    <div className="flex flex-col h-full min-h-[200px] bg-black">
      {/* Video element — always rendered so we can detect errors */}
      {hasSources && playerState !== 'fallback' && (
        <div className="relative flex-1 flex items-center justify-center">
          {playerState === 'loading' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black z-10">
              <div className="flex gap-1">
                <span className="h-2 w-2 rounded-full bg-white/40 animate-bounce [animation-delay:0ms]" />
                <span className="h-2 w-2 rounded-full bg-white/40 animate-bounce [animation-delay:150ms]" />
                <span className="h-2 w-2 rounded-full bg-white/40 animate-bounce [animation-delay:300ms]" />
              </div>
              <p className="text-xs text-white/50">Carregando vídeo...</p>
            </div>
          )}
          <video
            ref={videoRef}
            controls
            className="w-full h-full object-contain"
            aria-label={lessonTitle ?? 'Vídeo da aula'}
            crossOrigin="anonymous"
          >
            {streamSources.map((src, i) => (
              <source key={i} src={src} />
            ))}
            Seu navegador não suporta reprodução de vídeo.
          </video>
        </div>
      )}

      {/* Fallback — shown when no sources or video fails to load */}
      {(!hasSources || playerState === 'fallback') && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white/10">
            <VideoOff size={28} className="text-white/60" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-white/80">
              {lessonTitle ?? 'Aula'}
            </p>
            <p className="text-xs text-white/50">
              O vídeo não pôde ser carregado neste ambiente.
            </p>
          </div>
          {lessonUrl ? (
            <a
              href={lessonUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg bg-[hsl(var(--primary))] px-4 py-2 text-sm font-medium text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-opacity"
            >
              <ExternalLink size={14} />
              Assistir na CEFIS
            </a>
          ) : (
            <p className="text-xs text-white/40 italic">
              Link da aula não disponível.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
