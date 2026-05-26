import { create } from 'zustand';

type SessionState = 'ONBOARDING' | 'AWAITING_CONFIRMATION' | 'DIAGNOSIS' | 'PLAN_READY' | 'STUDY_MODE';

interface Profile {
  goal: string;
  level: 'iniciante' | 'intermediario' | 'avancado';
  time_available: number;
  learning_style: 'video' | 'leitura' | 'audio';
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
  has_certificate: boolean;
}

interface SessionStore {
  sessionId: string | null;
  state: SessionState;
  user: { name: string } | null;
  profile: Partial<Profile> | null;
  studyPlan: StudyPlan | null;
  setSessionId: (id: string) => void;
  setState: (state: SessionState) => void;
  setUser: (user: { name: string }) => void;
  setProfile: (profile: Partial<Profile>) => void;
  setStudyPlan: (plan: StudyPlan) => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  state: 'ONBOARDING' as SessionState,
  user: null,
  profile: null,
  studyPlan: null,
};

export const useSession = create<SessionStore>((set) => ({
  ...initialState,
  setSessionId: (id) => set({ sessionId: id }),
  setState: (state) => set({ state }),
  setUser: (user) => set({ user }),
  setProfile: (profile) => set({ profile }),
  setStudyPlan: (studyPlan) => set({ studyPlan }),
  reset: () => set(initialState),
}));
