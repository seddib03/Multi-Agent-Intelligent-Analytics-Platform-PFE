import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AppState } from "@/types/app";
import { ACCENT_THEMES } from "@/types/app";

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      currentPhase: 1,
      onboardingStep: 1,
      onboarding: {
        useCaseDescription: "",
        analysisTypes: [],
        timeHorizon: "30 jours",
      },
      dataset: {
        fileName: "",
        rowCount: 0,
        columnCount: 0,
        columns: [],
        qualityScore: 0,
        businessRules: "",
        detectedSector: "finance",
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
      userPreferences: {
        darkMode: false,
        chartStyle: "bar",
        density: "standard",
        accentTheme: "royal-melon",
        dashboardLayout: "grid",
        visibleKPIs: [],
        primaryColor: "#004AAC",
        secondaryColor: "#FF7E51",
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
    }),
    {
      name: "dxc-insight-platform",
      partialize: (state) => ({
        userPreferences: state.userPreferences,
        pinnedInsights: state.pinnedInsights,
      }),
    }
  )
);
