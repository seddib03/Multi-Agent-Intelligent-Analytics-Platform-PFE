import { useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { OnboardingHeader } from "@/components/onboarding/OnboardingHeader";
import { StepUseCase } from "@/components/onboarding/StepUseCase";
import { StepUpload } from "@/components/onboarding/StepUpload";
import { StepMetadata } from "@/components/onboarding/StepMetadata";
import { StepConfirmation } from "@/components/onboarding/StepConfirmation";
import { NLQInterface } from "@/components/nlq/NLQInterface";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { useDarkMode } from "@/hooks/useDarkMode";
import {
  getProject,
  getProjectSectorContext,
  getProjectStoredMessages,
  isProjectDashboardGenerated,
  type Project,
} from "@/lib/projectsApi";

const STEPS = [StepUseCase, StepUpload, StepMetadata, StepConfirmation];
const SUPPORTED_SECTORS = ["finance", "transport", "retail", "manufacturing", "public"] as const;

function normalizeSector(value: string | null | undefined): (typeof SUPPORTED_SECTORS)[number] {
  if (value && (SUPPORTED_SECTORS as readonly string[]).includes(value)) {
    return value as (typeof SUPPORTED_SECTORS)[number];
  }
  return "public";
}

const Index = () => {
  const phase = useAppStore((s) => s.currentPhase);
  const step = useAppStore((s) => s.onboardingStep);
  const currentProjectId = useAppStore((s) => s.currentProjectId);
  const messagesCount = useAppStore((s) => s.messages.length);
  const useCase = useAppStore((s) => s.onboarding.useCaseDescription);
  useDarkMode();

  useEffect(() => {
    let cancelled = false;

    if (!currentProjectId) return;
    // Avoid overriding an already hydrated local session.
    if (messagesCount > 0 || Boolean(useCase.trim())) return;

    getProject(currentProjectId)
      .then((project: Project) => {
        if (cancelled) return;
        const restoredMessages = getProjectStoredMessages(project);
        const dashboardGenerated = isProjectDashboardGenerated(project);

        useAppStore.setState((state) => ({
          currentProjectId: project.id,
          currentPhase: dashboardGenerated ? 2 : state.currentPhase,
          onboardingStep: dashboardGenerated ? 4 : state.onboardingStep,
          onboarding: {
            ...state.onboarding,
            useCaseDescription: project.use_case ?? state.onboarding.useCaseDescription,
            sectorContext: getProjectSectorContext(project) ?? state.onboarding.sectorContext,
          },
          dataset: {
            ...state.dataset,
            detectedSector: normalizeSector(project.detected_sector),
            businessRules: project.business_rules ?? state.dataset.businessRules,
            dashboardGenerated,
          },
          messages: restoredMessages,
          pinnedInsights: restoredMessages.filter((m) => m.pinned),
        }));
      })
      .catch(() => {
        // Non-blocking: app still works with local state even if API fetch fails.
      });

    return () => {
      cancelled = true;
    };
  }, [currentProjectId, messagesCount, useCase]);

  // phase 2 now leads to the dashboard; chat comes later in phase 3
  if (phase === 2) return <Dashboard />;
  if (phase === 3) return <NLQInterface />;

  const StepComponent = STEPS[step - 1];
  return (
    <div className="min-h-screen bg-background">
      <OnboardingHeader />
      <div className="p-4 md:p-6">
        <StepComponent />
      </div>
    </div>
  );
};

export default Index;