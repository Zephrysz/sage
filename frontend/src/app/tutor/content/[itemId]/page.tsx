'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, Play, Pause, Download, Mic } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from '@/hooks/useSession';
import { StudyChatbot } from '@/components/study/StudyChatbot';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type ContentType = 'SUMMARY' | 'APOSTILA' | 'PODCAST';

interface TtsVoice {
  name: string;
  description: string;
}

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

export default function ContentPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const itemId = params?.itemId as string;
  const contentType = (searchParams?.get('type') || 'SUMMARY') as ContentType;
  const itemTitle = searchParams?.get('title') || 'Conteúdo';

  const { sessionId, studyPlan, learningStyle } = useSession();

  const [text, setText] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [ragSourced, setRagSourced] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Podcast state
  const [voices, setVoices] = useState<TtsVoice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState('Achernar');
  const [speakingRate, setSpeakingRate] = useState(1.0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [synthesizing, setSynthesizing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!sessionId) { router.replace('/login'); return; }
  }, [sessionId, router]);

  // Load TTS voices
  useEffect(() => {
    fetch(`${API_URL}/content/tts/voices`)
      .then((r) => r.json())
      .then((d) => setVoices(d.voices || []))
      .catch(() => {});
  }, []);

  // Auto-generate on mount
  useEffect(() => {
    if (!sessionId || !itemId || startedRef.current) return;
    startedRef.current = true;
    generateContent();
  }, [sessionId, itemId]);

  const generateContent = useCallback(async () => {
    if (!sessionId) return;
    setText('');
    setError(null);
    setRagSourced(null);
    setAudioUrl(null);
    setStreaming(true);

    const endpoint = contentType === 'PODCAST' ? '/content/podcast/script' : '/content/generate';
    const body = contentType === 'PODCAST'
      ? { plan_item_id: itemId, voice_name: selectedVoice }
      : { plan_item_id: itemId, content_type: contentType };

    try {
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No body');

      let accumulated = '';
      for await (const data of parseSSE(res.body)) {
        if (data.startsWith('[DONE]')) {
          try {
            const payload = JSON.parse(data.slice(6).trim());
            setRagSourced(payload.rag_sourced ?? true);
          } catch { setRagSourced(true); }
          break;
        }
        accumulated += data.replace(/\\n/g, '\n');
        setText(accumulated);
      }
    } catch {
      setError('Não foi possível gerar o conteúdo. Tente novamente.');
    } finally {
      setStreaming(false);
    }
  }, [sessionId, itemId, contentType, selectedVoice]);

  const synthesizeAudio = useCallback(async () => {
    if (!sessionId || synthesizing) return;
    setSynthesizing(true);
    setAudioUrl(null);
    try {
      const res = await fetch(`${API_URL}/content/podcast/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
        body: JSON.stringify({ plan_item_id: itemId, voice_name: selectedVoice, speaking_rate: speakingRate }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
    } catch {
      setError('Não foi possível sintetizar o áudio. Tente novamente.');
    } finally {
      setSynthesizing(false);
    }
  }, [sessionId, itemId, selectedVoice, speakingRate, synthesizing]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) { audioRef.current.pause(); setIsPlaying(false); }
    else { audioRef.current.play(); setIsPlaying(true); }
  };

  // Find the plan item for the chatbot context
  const planItem = studyPlan?.items.find((i) => i.id === itemId);

  if (!sessionId) return null;

  const typeLabel = contentType === 'SUMMARY' ? 'Resumo' : contentType === 'APOSTILA' ? 'Apostila' : 'Mini-Podcast';

  return (
    <main className="flex h-screen overflow-hidden bg-[hsl(var(--background))]">
      {/* ── Content panel ── */}
      <section className="flex flex-col flex-1 overflow-hidden border-r border-[hsl(var(--border))]">
        {/* Header */}
        <header className="flex items-center gap-3 px-5 py-3 border-b border-[hsl(var(--border))] bg-[hsl(var(--card))] shrink-0">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-1.5 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors shrink-0"
          >
            <ArrowLeft size={14} />
            Voltar
          </button>
          <div className="h-4 w-px bg-[hsl(var(--border))]" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-[hsl(var(--foreground))] truncate">{itemTitle}</p>
            <p className="text-xs text-[hsl(var(--primary))]">{typeLabel}</p>
          </div>
          <button
            onClick={generateContent}
            disabled={streaming}
            className="text-xs rounded-lg border border-[hsl(var(--border))] px-3 py-1.5 text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors disabled:opacity-50"
          >
            {streaming ? 'Gerando...' : 'Regenerar'}
          </button>
        </header>

        {/* Podcast voice selector */}
        {contentType === 'PODCAST' && (
          <div className="px-5 py-3 border-b border-[hsl(var(--border))] bg-[hsl(var(--card))] shrink-0 flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Mic size={14} className="text-[hsl(var(--primary))]" />
              <span className="text-xs font-medium text-[hsl(var(--foreground))]">Voz:</span>
              <select
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                className="text-xs rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2 py-1 text-[hsl(var(--foreground))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--ring))]"
              >
                {voices.map((v) => (
                  <option key={v.name} value={v.name}>{v.name} — {v.description}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[hsl(var(--muted-foreground))]">Velocidade:</span>
              <input
                type="range" min="0.5" max="2" step="0.1"
                value={speakingRate}
                onChange={(e) => setSpeakingRate(parseFloat(e.target.value))}
                className="w-20 accent-[hsl(var(--primary))]"
              />
              <span className="text-xs text-[hsl(var(--muted-foreground))]">{speakingRate.toFixed(1)}x</span>
            </div>
            {text && !streaming && (
              <button
                onClick={synthesizeAudio}
                disabled={synthesizing}
                className="inline-flex items-center gap-1.5 text-xs rounded-lg bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] px-3 py-1.5 hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {synthesizing ? 'Sintetizando...' : '🎙️ Gerar Áudio'}
              </button>
            )}
          </div>
        )}

        {/* Audio player */}
        {audioUrl && (
          <div className="px-5 py-3 border-b border-[hsl(var(--border))] bg-[hsl(var(--card))] shrink-0 flex items-center gap-3">
            <button
              onClick={togglePlay}
              className="flex items-center justify-center w-9 h-9 rounded-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-opacity"
            >
              {isPlaying ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <audio
              ref={audioRef}
              src={audioUrl}
              onEnded={() => setIsPlaying(false)}
              className="flex-1 h-8"
              controls
            />
            <a
              href={audioUrl}
              download={`podcast-${itemId}.mp3`}
              className="flex items-center justify-center w-8 h-8 rounded-lg border border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors"
              title="Baixar MP3"
            >
              <Download size={14} />
            </a>
          </div>
        )}

        {/* Content body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive mb-4">
              {error}
            </div>
          )}

          {streaming && text.length === 0 ? (
            <div className="space-y-3 animate-pulse">
              {[100, 90, 95, 80, 85, 70, 88, 75].map((w, i) => (
                <div key={i} className="h-4 rounded bg-[hsl(var(--muted))]" style={{ width: `${w}%` }} />
              ))}
            </div>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none text-[hsl(var(--foreground))] text-sm leading-relaxed [&_h1]:text-base [&_h1]:font-bold [&_h1]:mt-5 [&_h1]:mb-2 [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mt-4 [&_h2]:mb-1.5 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1 [&_p]:mb-2.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2.5 [&_li]:mb-1 [&_strong]:font-semibold [&_em]:italic [&_code]:bg-[hsl(var(--muted))] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_blockquote]:border-l-2 [&_blockquote]:border-[hsl(var(--primary))] [&_blockquote]:pl-4 [&_blockquote]:opacity-80 [&_table]:w-full [&_table]:text-xs [&_th]:border [&_th]:border-[hsl(var(--border))] [&_th]:px-2 [&_th]:py-1.5 [&_th]:bg-[hsl(var(--muted))] [&_td]:border [&_td]:border-[hsl(var(--border))] [&_td]:px-2 [&_td]:py-1.5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
              {streaming && (
                <span className="inline-block w-0.5 h-4 bg-[hsl(var(--foreground))] animate-pulse align-middle ml-0.5" />
              )}
            </div>
          )}
        </div>
      </section>

      {/* ── AI Chat panel ── */}
      <aside className="hidden md:flex flex-col w-96 shrink-0 overflow-hidden">
        {sessionId && (
          <StudyChatbot
            sessionId={sessionId}
            courseTitle={itemTitle}
            lessons={[]}
          />
        )}
      </aside>
    </main>
  );
}
