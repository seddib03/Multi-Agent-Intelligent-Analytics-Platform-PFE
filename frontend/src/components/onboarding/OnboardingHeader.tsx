import { useAppStore } from "@/stores/appStore";
import { AccountMenu } from "@/components/ui/AccountMenu";
import { t } from "@/lib/i18n";
import BrandLogo from "@/components/BrandLogo";

export function OnboardingHeader() {
  const step = useAppStore((s) => s.onboardingStep);
  const setOnboardingStep = useAppStore((s) => s.setOnboardingStep);
  const lang = useAppStore((s) => s.userPreferences.language);

  // currently we hide the "quality" phase until after launch
  const steps = [
    t("stepUseCase", lang),
    t("stepData", lang),
    t("stepMetadata", lang),
    // quality step intentionally removed for now
    t("stepLaunch", lang),
  ];

  return (
    <div className="sticky top-0 z-50">
      <div className="h-16 bg-dxc-midnight px-4 md:px-6 flex items-center justify-between">
        <BrandLogo logoClassName="h-7" subtitleClassName="text-[13px] font-semibold" showSubtitle />
        <AccountMenu variant="dark" position="top" />
      </div>
      <div className="bg-card border-b border-border px-4 md:px-6 py-3">
        <div className="max-w-3xl mx-auto flex items-center gap-1 sm:gap-2">
          {steps.map((label, i) => {
            const idx = i + 1;
            const isActive = idx === step;
            const isDone = idx < step;
            const canNavigate = isDone;
            return (
              <div key={label} className="flex items-center flex-1">
                <div className="flex items-center gap-1.5 sm:gap-2 flex-1">
                  <button
                    onClick={() => canNavigate && setOnboardingStep(idx as 1 | 2 | 3 | 4)}
                    disabled={!canNavigate}
                    className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-xs sm:text-sm font-semibold shrink-0 transition-all ${
                      isDone
                        ? "bg-dxc-melon text-white cursor-pointer hover:bg-dxc-red"
                        : isActive
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    } ${!canNavigate ? "cursor-default" : ""}`}
                  >
                    {isDone ? "✓" : idx}
                  </button>
                  <span
                    className={`text-[10px] sm:text-xs font-medium hidden sm:block ${
                      isActive ? "text-primary" : isDone ? "text-dxc-melon" : "text-muted-foreground"
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <div className={`h-0.5 flex-1 mx-1 sm:mx-2 rounded ${isDone ? "bg-dxc-melon" : "bg-border"}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
