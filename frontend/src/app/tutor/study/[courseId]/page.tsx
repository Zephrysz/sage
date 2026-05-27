'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { useSession } from '@/hooks/useSession';
import { apiRequest } from '@/lib/api';
import { LessonSidebar, type Lesson } from '@/components/study/LessonSidebar';
import { VideoPlayer } from '@/components/study/VideoPlayer';
import { StudyChatbot } from '@/components/study/StudyChatbot';

interface CourseDetails {
  id: string | number;
  title: string;
  teacher?: string;
  url?: string;
}

interface LessonFromApi {
  id: string | number;
  title: string;
  duration?: number;
  url?: string;
  stream_sources?: string[];
}

export default function StudyPage() {
  const params = useParams();
  const router = useRouter();
  const courseId = params?.courseId as string;

  const { sessionId, setState, studyPlan } = useSession();

  const [courseDetails, setCourseDetails] = useState<CourseDetails | null>(null);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [activeLesson, setActiveLesson] = useState<Lesson | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(true);

  useEffect(() => {
    if (!sessionId) router.replace('/login');
  }, [sessionId, router]);

  useEffect(() => {
    if (!sessionId) return;
    setState('STUDY_MODE');
    apiRequest('/session/state', {
      method: 'POST',
      body: JSON.stringify({ state: 'STUDY_MODE' }),
    }, sessionId).catch(() => {});
  }, [sessionId, setState]);

  useEffect(() => {
    if (!courseId) return;
    setLoading(true);
    setError(null);

    const planItem = studyPlan?.items.find((item) => item.course_id === courseId);

    if (planItem?.course_details) {
      const details = planItem.course_details as Record<string, unknown>;

      // Safely extract string fields — some CEFIS API fields may be objects
      const safeStr = (v: unknown): string | undefined => {
        if (typeof v === 'string') return v || undefined;
        if (typeof v === 'number') return String(v);
        if (v && typeof v === 'object' && 'name' in v) return String((v as Record<string, unknown>).name) || undefined;
        return undefined;
      };

      setCourseDetails({
        id: courseId,
        title: safeStr(details.title) || safeStr(details.name) || planItem.title,
        teacher: safeStr(details.teacher) || safeStr(details.professor),
        url: safeStr(details.url) || safeStr(details.link),
      });

      const rawLessons = (details.lessons as LessonFromApi[]) || [];
      const mappedLessons: Lesson[] = rawLessons.map((l) => ({
        id: l.id,
        title: l.title,
        duration: l.duration,
        url: l.url,
        stream_sources: l.stream_sources,
      }));
      setLessons(mappedLessons);
      if (mappedLessons.length > 0) setActiveLesson(mappedLessons[0]);
    } else if (planItem) {
      setCourseDetails({ id: courseId, title: planItem.title });
    } else {
      setError('Curso não encontrado no seu plano de estudos.');
    }
    setLoading(false);
  }, [courseId, studyPlan]);

  const handleSelectLesson = useCallback((lesson: Lesson) => {
    setActiveLesson(lesson);
  }, []);

  const handleBack = () => {
    setState('PLAN_READY');
    apiRequest('/session/state', {
      method: 'POST',
      body: JSON.stringify({ state: 'PLAN_READY' }),
    }, sessionId ?? '').catch(() => {});
    router.push('/tutor');
  };

  if (!sessionId) return null;

  // Lesson list for source URL resolution in chatbot — include id for exact matching
  const lessonList = lessons.map((l) => ({ id: l.id, title: l.title, url: l.url }));

  return (
    <main className="flex flex-col h-screen overflow-hidden bg-[hsl(var(--background))]">
      {/* Top bar — minimal, just back + course title */}
      <header className="flex items-center gap-2 px-3 py-2 border-b border-[hsl(var(--border))] bg-[hsl(var(--card))] shrink-0 min-w-0">
        <button
          onClick={handleBack}
          aria-label="Voltar ao plano de estudos"
          className="flex items-center gap-1.5 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors shrink-0"
        >
          <ArrowLeft size={14} />
          <span className="hidden sm:inline">Plano</span>
        </button>

        <div className="h-4 w-px bg-[hsl(var(--border))] shrink-0" aria-hidden="true" />

        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="h-4 w-48 rounded bg-[hsl(var(--muted))] animate-pulse" />
          ) : (
            <p className="text-sm font-semibold text-[hsl(var(--foreground))] truncate">
              {courseDetails?.title ?? 'Modo de Estudo'}
            </p>
          )}
          {courseDetails?.teacher && (
            <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">{courseDetails.teacher}</p>
          )}
        </div>

        <span className="shrink-0 text-xs bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))] rounded-full px-2 py-0.5 font-medium">
          Modo Estudo
        </span>
      </header>

      {/* Error */}
      {error && (
        <div className="flex-1 flex items-center justify-center px-4">
          <div className="text-center space-y-3">
            <p className="text-sm text-[hsl(var(--destructive))]">{error}</p>
            <button onClick={handleBack} className="text-xs underline text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
              Voltar ao plano
            </button>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !error && (
        <div className="flex flex-1 overflow-hidden">
          <div className="w-64 border-r border-[hsl(var(--border))] p-4 space-y-2 shrink-0">
            {[1, 2, 3, 4, 5].map((n) => (
              <div key={n} className="h-12 rounded-lg bg-[hsl(var(--muted))] animate-pulse" />
            ))}
          </div>
          <div className="flex-1 bg-black flex items-center justify-center">
            <div className="flex gap-1">
              <span className="h-2 w-2 rounded-full bg-white/30 animate-bounce [animation-delay:0ms]" />
              <span className="h-2 w-2 rounded-full bg-white/30 animate-bounce [animation-delay:150ms]" />
              <span className="h-2 w-2 rounded-full bg-white/30 animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
          <div className="w-96 border-l border-[hsl(var(--border))] p-4 shrink-0">
            <div className="h-8 rounded-lg bg-[hsl(var(--muted))] animate-pulse mb-3" />
          </div>
        </div>
      )}

      {/* 3-column layout */}
      {!loading && !error && (
        <div className="flex flex-1 overflow-hidden min-w-0">
          {/* Left: Lesson Sidebar — collapsible, toggle is inside the sidebar header */}
          <div className={`shrink-0 overflow-hidden transition-all duration-300 ease-in-out ${sidebarOpen ? 'w-64' : 'w-0'}`}>
            <div className="w-64 h-full">
              <LessonSidebar
                lessons={lessons}
                activeLessonId={activeLesson?.id ?? null}
                onSelectLesson={handleSelectLesson}
                courseTitle={courseDetails?.title}
                open={sidebarOpen}
                onToggle={() => setSidebarOpen((v) => !v)}
              />
            </div>
          </div>

          {/* Sidebar collapsed — show a slim toggle strip */}
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              aria-label="Mostrar lista de aulas"
              className="shrink-0 w-6 flex items-center justify-center bg-[hsl(var(--card))] border-r border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors"
              title="Mostrar aulas"
            >
              <span className="text-[10px] font-medium rotate-90 whitespace-nowrap select-none">Aulas</span>
            </button>
          )}

          {/* Center: Video Player */}
          <div className="flex-1 min-w-0 overflow-hidden">
            <VideoPlayer
              streamSources={activeLesson?.stream_sources}
              lessonTitle={activeLesson?.title}
              lessonUrl={activeLesson?.url ?? courseDetails?.url}
            />
          </div>

          {/* Chat collapsed — show a slim toggle strip */}
          {!chatOpen && (
            <button
              onClick={() => setChatOpen(true)}
              aria-label="Mostrar chat"
              className="shrink-0 w-6 flex items-center justify-center bg-[hsl(var(--card))] border-l border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors"
              title="Mostrar chat"
            >
              <span className="text-[10px] font-medium rotate-90 whitespace-nowrap select-none">Tutor IA</span>
            </button>
          )}

          {/* Right: Study Chatbot — collapsible, toggle is inside the chatbot header */}
          <div className={`shrink-0 overflow-hidden transition-all duration-300 ease-in-out ${chatOpen ? 'w-96' : 'w-0'}`}>
            <div className="w-96 h-full">
              {sessionId && (
                <StudyChatbot
                  sessionId={sessionId}
                  courseTitle={courseDetails?.title}
                  lessons={lessonList}
                  open={chatOpen}
                  onToggle={() => setChatOpen((v) => !v)}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
