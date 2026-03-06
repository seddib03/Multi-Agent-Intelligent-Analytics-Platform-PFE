import { useAppStore } from "@/stores/appStore";
import { OnboardingHeader } from "@/components/onboarding/OnboardingHeader";
import { StepUseCase } from "@/components/onboarding/StepUseCase";
import { StepUpload } from "@/components/onboarding/StepUpload";
import { StepMetadata } from "@/components/onboarding/StepMetadata";
import { StepConfirmation } from "@/components/onboarding/StepConfirmation";
import { NLQInterface } from "@/components/nlq/NLQInterface";
import { Dashboard } from "@/components/dashboard/Dashboard";

const STEPS = [StepUseCase, StepUpload, StepMetadata, StepConfirmation];

const Index = () => {
  const phase = useAppStore((s) => s.currentPhase);
  const step = useAppStore((s) => s.onboardingStep);

  if (phase === 2) return <NLQInterface />;
  if (phase === 3) return <Dashboard />;

  const StepComponent = STEPS[step - 1];

  return (
    <div className="min-h-screen bg-dxc-canvas">
      <OnboardingHeader />
      <div className="p-6">
        <StepComponent />
      </div>
    </div>
  );
};

export default Index;
