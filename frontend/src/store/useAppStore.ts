import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, Project, ColumnMetadata, QualityIssue, Correction, ModelResults, Message, UserPreferences, DataPrepStep, Sector } from '@/types';

interface AppState {
  currentUser: User | null;
  isAuthenticated: boolean;
  currentProjectId: string | null;
  projects: Project[];
  dataPreparationStep: DataPrepStep;
  dataset: {
    fileName: string;
    rowCount: number;
    columnCount: number;
    columns: ColumnMetadata[];
    qualityScore: number;
    qualityIssues: QualityIssue[];
    appliedCorrections: Correction[];
    businessRules: string;
    detectedSector: Sector;
  };
  modelResults: ModelResults;
  messages: Message[];
  pinnedInsights: Message[];
  userPreferences: UserPreferences;
  // Actions
  login: (user: User) => void;
  logout: () => void;
  register: (user: User) => void;
  setCurrentProject: (id: string | null) => void;
  addProject: (project: Project) => void;
  updateProject: (id: string, updates: Partial<Project>) => void;
  deleteProject: (id: string) => void;
  setDataPrepStep: (step: DataPrepStep) => void;
  addMessage: (msg: Message) => void;
  togglePinMessage: (id: string) => void;
  updatePreferences: (prefs: Partial<UserPreferences>) => void;
  setDataset: (data: Partial<AppState['dataset']>) => void;
  applyCorrection: (correction: Correction) => void;
}

const defaultPreferences: UserPreferences = {
  darkMode: false,
  chartStyle: 'bar',
  density: 'standard',
  accentTheme: 'royal-melon',
  dashboardLayout: 'grid',
  visibleKPIs: ['auc', 'accuracy', 'f1', 'totalPredictions', 'highRisk', 'avgRisk'],
  primaryColor: '#004AAC',
  secondaryColor: '#FF7E51',
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      currentUser: null,
      isAuthenticated: false,
      currentProjectId: null,
      projects: [],
      dataPreparationStep: 'upload',
      dataset: {
        fileName: '',
        rowCount: 0,
        columnCount: 0,
        columns: [],
        qualityScore: 0,
        qualityIssues: [],
        appliedCorrections: [],
        businessRules: '',
        detectedSector: 'finance',
      },
      modelResults: {
        algorithm: 'XGBoost',
        auc: 0.89,
        accuracy: 0.87,
        f1Score: 0.84,
        featureImportance: [],
        topRiskyEntities: [],
      },
      messages: [],
      pinnedInsights: [],
      userPreferences: defaultPreferences,

      login: (user) => set({ currentUser: user, isAuthenticated: true }),
      logout: () => set({ currentUser: null, isAuthenticated: false, currentProjectId: null }),
      register: (user) => set({ currentUser: user, isAuthenticated: true }),
      setCurrentProject: (id) => set({ currentProjectId: id }),
      addProject: (project) => set((s) => ({ projects: [...s.projects, project] })),
      updateProject: (id, updates) => set((s) => ({
        projects: s.projects.map((p) => (p.id === id ? { ...p, ...updates } : p)),
      })),
      deleteProject: (id) => set((s) => ({
        projects: s.projects.filter((p) => p.id !== id),
        currentProjectId: s.currentProjectId === id ? null : s.currentProjectId,
      })),
      setDataPrepStep: (step) => set({ dataPreparationStep: step }),
      addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
      togglePinMessage: (id) => set((s) => {
        const msg = s.messages.find((m) => m.id === id);
        if (!msg) return s;
        const pinned = !msg.pinned;
        return {
          messages: s.messages.map((m) => (m.id === id ? { ...m, pinned } : m)),
          pinnedInsights: pinned
            ? [...s.pinnedInsights, { ...msg, pinned: true }]
            : s.pinnedInsights.filter((m) => m.id !== id),
        };
      }),
      updatePreferences: (prefs) => set((s) => ({
        userPreferences: { ...s.userPreferences, ...prefs },
      })),
      setDataset: (data) => set((s) => ({ dataset: { ...s.dataset, ...data } })),
      applyCorrection: (correction) => set((s) => ({
        dataset: {
          ...s.dataset,
          appliedCorrections: [...s.dataset.appliedCorrections, correction],
        },
      })),
    }),
    { name: 'dxc-insight-store' }
  )
);
