'use client';

import { useState } from 'react';
import { BookOpen, PlayCircle, ChevronDown, PanelLeftClose } from 'lucide-react';

export interface Lesson {
  id: string | number;
  title: string;
  duration?: number; // minutes
  url?: string;
  stream_sources?: string[];
}

interface LessonSidebarProps {
  lessons: Lesson[];
  activeLessonId: string | number | null;
  onSelectLesson: (lesson: Lesson) => void;
  courseTitle?: string;
  /** Controlled open state — if provided, renders a collapse toggle in the header */
  open?: boolean;
  onToggle?: () => void;
}

export function LessonSidebar({
  lessons,
  activeLessonId,
  onSelectLesson,
  courseTitle,
  open,
  onToggle,
}: LessonSidebarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeLesson = lessons.find((l) => l.id === activeLessonId);

  const lessonList = (
    <nav className="py-2" aria-label="Lista de aulas">
      {lessons.length === 0 ? (
        <p className="px-4 py-6 text-xs text-center text-[hsl(var(--muted-foreground))]">
          Nenhuma aula disponível.
        </p>
      ) : (
        <ul className="space-y-0.5 px-2">
          {lessons.map((lesson, index) => {
            const isActive = lesson.id === activeLessonId;
            return (
              <li key={lesson.id}>
                <button
                  onClick={() => {
                    onSelectLesson(lesson);
                    // Close accordion on mobile after selecting
                    setMobileOpen(false);
                  }}
                  aria-current={isActive ? 'true' : undefined}
                  className={`w-full text-left rounded-lg px-3 py-2.5 transition-colors group ${
                    isActive
                      ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]'
                      : 'hover:bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={`shrink-0 mt-0.5 ${
                        isActive
                          ? 'text-[hsl(var(--primary-foreground))]'
                          : 'text-[hsl(var(--muted-foreground))] group-hover:text-[hsl(var(--foreground))]'
                      }`}
                    >
                      <PlayCircle size={14} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <p
                        className={`text-xs font-medium leading-snug ${
                          isActive
                            ? 'text-[hsl(var(--primary-foreground))]'
                            : 'text-[hsl(var(--foreground))]'
                        }`}
                      >
                        <span
                          className={`mr-1 ${
                            isActive
                              ? 'text-[hsl(var(--primary-foreground))]/70'
                              : 'text-[hsl(var(--muted-foreground))]'
                          }`}
                        >
                          {index + 1}.
                        </span>
                        {lesson.title}
                      </p>
                      {lesson.duration != null && (
                        <p
                          className={`text-xs mt-0.5 ${
                            isActive
                              ? 'text-[hsl(var(--primary-foreground))]/70'
                              : 'text-[hsl(var(--muted-foreground))]'
                          }`}
                        >
                          ~{lesson.duration} min
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );

  return (
    <aside className="bg-[hsl(var(--card))] border-b md:border-b-0 md:border-r border-[hsl(var(--border))] md:flex md:flex-col md:h-full">
      {/* ── Mobile: accordion header ── */}
      <button
        type="button"
        onClick={() => setMobileOpen((prev) => !prev)}
        aria-expanded={mobileOpen}
        aria-controls="lesson-list-mobile"
        className="md:hidden w-full flex items-center justify-between gap-2 px-4 py-3 border-b border-[hsl(var(--border))]"
      >
        <div className="flex items-center gap-2 min-w-0">
          <BookOpen size={16} className="text-[hsl(var(--primary))] shrink-0" />
          <div className="min-w-0 text-left">
            <p className="text-sm font-semibold text-[hsl(var(--foreground))] truncate">
              {courseTitle ?? 'Aulas do curso'}
            </p>
            {activeLesson && (
              <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">
                Aula atual: {activeLesson.title}
              </p>
            )}
          </div>
        </div>
        <ChevronDown
          size={16}
          className={`shrink-0 text-[hsl(var(--muted-foreground))] transition-transform duration-200 ${
            mobileOpen ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* Mobile: collapsible lesson list */}
      <div
        id="lesson-list-mobile"
        className={`md:hidden overflow-hidden transition-all duration-200 ${
          mobileOpen ? 'max-h-64 overflow-y-auto' : 'max-h-0'
        }`}
      >
        {lessonList}
      </div>

      {/* ── Desktop: always-visible sidebar ── */}
      {/* Header */}
      <div className="hidden md:flex md:items-center gap-2 px-3 py-3 border-b border-[hsl(var(--border))] shrink-0">
        {onToggle && (
          <button
            onClick={onToggle}
            aria-label="Ocultar lista de aulas"
            className="flex items-center justify-center w-6 h-6 rounded-md text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors shrink-0"
          >
            <PanelLeftClose size={13} />
          </button>
        )}
        <BookOpen size={15} className="text-[hsl(var(--primary))] shrink-0" />
        <div className="min-w-0 flex-1">
          <h2 className="text-xs font-semibold text-[hsl(var(--foreground))] truncate">
            {courseTitle ?? 'Aulas do curso'}
          </h2>
          <p className="text-[10px] text-[hsl(var(--muted-foreground))]">
            {lessons.length} {lessons.length === 1 ? 'aula' : 'aulas'}
          </p>
        </div>
      </div>

      {/* Desktop: scrollable lesson list */}
      <div className="hidden md:block flex-1 overflow-y-auto">
        {lessonList}
      </div>
    </aside>
  );
}
