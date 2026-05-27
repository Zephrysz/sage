import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type SessionState = 'ONBOARDING' | 'AWAITING_CONFIRMATION' | 'DIAGNOSIS' | 'PLAN_READY' | 'STUDY_MODE';

interface Profile {
  goal: string;
  level: 'iniciante' | 'intermediario' | 'avancado';
  time_available: number;
  learning_style: 'video' | 'leitura' | 'audio' | 'cinestetico';
}

interface StudyPlan {
  items: PlanItem[];
  total_estimated_minutes: number;
}

interface PlanItem {
  id: string;
  position: number;
  type: 'CEFIS_COURSE' | 'GENERATED_CONTENT';
  title: string;
  estimated_minutes: number;
  justification: string;
  course_id?: string;
  course_details?: Record<string, unknown>;
  has_certificate: boolean;
}

export interface ChatMessage {
  role: 'user' | 'tutor';
  text: string;
}

interface SessionStore {
  sessionId: string | null;
  state: SessionState;
  user: { name: string } | null;
  profile: Partial<Profile> | null;
  studyPlan: StudyPlan | null;
  messages: ChatMessage[];
  learningStyle: Profile['learning_style'] | null;
  setSessionId: (id: string) => void;
  setState: (state: SessionState) => void;
  setUser: (user: { name: string } | Record<string, unknown>) => void;
  setProfile: (profile: Partial<Profile>) => void;
  setStudyPlan: (plan: StudyPlan | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  updateLastMessage: (text: string) => void;
  setLearningStyle: (style: Profile['learning_style']) => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  state: 'ONBOARDING' as SessionState,
  user: null,
  profile: null,
  studyPlan: null,
  messages: [] as ChatMessage[],
  learningStyle: null as Profile['learning_style'] | null,
};

export const useSession = create<SessionStore>()(
  persist(
    (set) => ({
      ...initialState,
      setSessionId: (id) => set({ sessionId: id }),
      setState: (state) => set({ state }),
      // Normalize user to only store the name — the CEFIS API may return extra
      // fields (id, avatar, etc.) that would cause React render errors if stored raw
      setUser: (user) => set({ user: { name: String(user?.name ?? '') } }),
      setProfile: (profile) => set({ profile }),
      setStudyPlan: (studyPlan) => set({ studyPlan }),
      setMessages: (messages) => set({ messages }),
      addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
      updateLastMessage: (text) =>
        set((s) => {
          const updated = [...s.messages];
          if (updated.length > 0) {
            updated[updated.length - 1] = { ...updated[updated.length - 1], text };
          }
          return { messages: updated };
        }),
      setLearningStyle: (style) => set({ learningStyle: style }),
      reset: () => set(initialState),
    }),
    {
      name: 'cefis-session',
      version: 2,
      partialize: (state) => ({
        sessionId: state.sessionId,
        state: state.state,
        user: state.user,
        studyPlan: state.studyPlan,
        messages: state.messages,
        learningStyle: state.learningStyle,
      }),
    }
  )
);
