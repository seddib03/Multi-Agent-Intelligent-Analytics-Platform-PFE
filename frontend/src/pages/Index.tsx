import { useAppStore } from "@/stores/appStore";
import { OnboardingHeader } from "@/components/onboarding/OnboardingHeader";
import { StepUseCase } from "@/components/onboarding/StepUseCase";
import { StepUpload } from "@/components/onboarding/StepUpload";
import { StepMetadata } from "@/components/onboarding/StepMetadata";
import { StepConfirmation } from "@/components/onboarding/StepConfirmation";
import { NLQInterface } from "@/components/nlq/NLQInterface";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { useDarkMode } from "@/hooks/useDarkMode";

const STEPS = [StepUseCase, StepUpload, StepMetadata, StepConfirmation];

const Index = () => {
  const phase = useAppStore((s) => s.currentPhase);
  const step = useAppStore((s) => s.onboardingStep);
  useDarkMode();

  if (phase === 2) return <NLQInterface />;
  if (phase === 3) return <Dashboard />;

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