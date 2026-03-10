import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AppState, SavedProject } from "@/types/app";
import { ACCENT_THEMES } from "@/types/app";

const EMPTY_PROJECT = {
  currentPhase: 1 as const,
  onboardingStep: 1 as const,
  currentConversationId: null,
  currentProjectId: null,
  onboarding: {
    useCaseDescription: "",
    analysisTypes: [] as string[],
    timeHorizon: "30 jours",
  },
  dataset: {
    fileName: "",
    rowCount: 0,
    columnCount: 0,
    columns: [],
    qualityScore: 0,
    businessRules: "",
    detectedSector: "finance" as const,
    previewData: [],
  },
  modelResults: {
    algorithm: "XGBoost",
    auc: 0.871,
    accuracy: 0.856,
    f1Score: 0.83,
    precision: 0.84,
    recall: 0.82,
    rmse: 0.312,
    gini: 0.742,
    logLoss: 0.387,
    featureImportance: [],
    topRiskyEntities: [],
  },
  messages: [],
  pinnedInsights: [],
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      ...EMPTY_PROJECT,
      savedProjects: [],
      userPreferences: {
        darkMode: false,
        chartStyle: "bar",
        density: "standard",
        accentTheme: "royal-melon",
        dashboardLayout: "grid",
        visibleKPIs: [],
        primaryColor: "#004AAC",
        secondaryColor: "#FF7E51",
        language: "fr" as const,
      },

      setPhase: (phase) => set({ currentPhase: phase }),
      setOnboardingStep: (step) => set({ onboardingStep: step }),
      updateOnboarding: (data) =>
        set((s) => ({ onboarding: { ...s.onboarding, ...data } })),
      updateDataset: (data) =>
        set((s) => ({ dataset: { ...s.dataset, ...data } })),
      updatePreferences: (prefs) =>
        set((s) => {
          const newPrefs = { ...s.userPreferences, ...prefs };
          if (prefs.accentTheme) {
            const theme = ACCENT_THEMES[prefs.accentTheme];
            newPrefs.primaryColor = theme.primary;
            newPrefs.secondaryColor = theme.secondary;
          }
          return { userPreferences: newPrefs };
        }),
      addMessage: (msg) =>
        set((s) => ({ messages: [...s.messages, msg] })),
      togglePin: (msgId) =>
        set((s) => {
          const msg = s.messages.find((m) => m.id === msgId);
          if (!msg) return s;
          const isPinned = s.pinnedInsights.some((m) => m.id === msgId);
          return {
            pinnedInsights: isPinned
              ? s.pinnedInsights.filter((m) => m.id !== msgId)
              : [...s.pinnedInsights, { ...msg, pinned: true }],
          };
        }),
      updateModelResults: (results) =>
        set((s) => ({ modelResults: { ...s.modelResults, ...results } })),
      clearMessages: () => set({ messages: [] }),

      saveCurrentProject: () => {
        const s = get();
        // Only save if there's meaningful data
        if (!s.onboarding.useCaseDescription.trim() && !s.dataset.fileName) return;

        const now = new Date().toISOString();
        const existingIdx = s.savedProjects.findIndex((p) => p.id === s.currentProjectId);

        const project: SavedProject = {
          id: s.currentProjectId || `proj-${Date.now()}`,
          name: s.onboarding.useCaseDescription.slice(0, 60) || s.dataset.fileName || "Sans titre",
          createdAt: existingIdx >= 0 ? s.savedProjects[existingIdx].createdAt : now,
          updatedAt: now,
          currentPhase: s.currentPhase,
          onboardingStep: s.onboardingStep,
          onboarding: { ...s.onboarding },
          dataset: { ...s.dataset },
          modelResults: { ...s.modelResults },
          messages: [...s.messages],
          pinnedInsights: [...s.pinnedInsights],
        };

        const updated = existingIdx >= 0
          ? s.savedProjects.map((p, i) => (i === existingIdx ? project : p))
          : [project, ...s.savedProjects];

        set({ savedProjects: updated, currentProjectId: project.id });
      },

      loadProject: (projectId) => {
        const s = get();
        const project = s.savedProjects.find((p) => p.id === projectId);
        if (!project) return;

        set({
          currentProjectId: project.id,
          currentPhase: project.currentPhase,
          onboardingStep: project.onboardingStep,
          onboarding: { ...project.onboarding },
          dataset: { ...project.dataset },
          modelResults: { ...project.modelResults },
          messages: [...project.messages],
          pinnedInsights: [...project.pinnedInsights],
        });
      },

      deleteProject: (projectId) =>
        set((s) => ({
          savedProjects: s.savedProjects.filter((p) => p.id !== projectId),
          ...(s.currentProjectId === projectId ? { currentProjectId: null } : {}),
        })),

      resetProject: () => {
        // Save current project before resetting
        get().saveCurrentProject();
        set({
          ...EMPTY_PROJECT,
          currentProjectId: null,
        });
      },
    }),
    {
      name: "dxc-insight-platform",
      partialize: (state) => ({
        userPreferences: state.userPreferences,
        pinnedInsights: state.pinnedInsights,
        savedProjects: state.savedProjects,
        currentProjectId: state.currentProjectId,
      }),
    }
  )
);
