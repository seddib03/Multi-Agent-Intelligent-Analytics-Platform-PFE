import { useAppStore } from "@/stores/appStore";

const steps = ["Use Case", "Données", "Métadonnées", "Lancement"];

export function OnboardingHeader() {
  const step = useAppStore((s) => s.onboardingStep);

  return (
    <div className="sticky top-0 z-50">
      <div className="bg-dxc-midnight px-6 py-3 flex items-center">
        <span className="text-dxc-white font-bold text-[22px] tracking-tight">DXC</span>
        <span className="text-dxc-peach text-xs ml-2 mt-1">Insight Platform</span>
      </div>
      <div className="bg-dxc-white border-b border-dxc-canvas px-6 py-3">
        <div className="max-w-3xl mx-auto flex items-center gap-2">
          {steps.map((label, i) => {
            const idx = i + 1;
            const isActive = idx === step;
            const isDone = idx < step;
            return (
              <div key={label} className="flex items-center flex-1">
                <div className="flex items-center gap-2 flex-1">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 transition-all ${
                      isDone
                        ? "bg-dxc-melon text-dxc-white"
                        : isActive
                        ? "bg-dxc-royal text-dxc-white"
                        : "bg-dxc-canvas text-dxc-royal"
                    }`}
                  >
                    {isDone ? "✓" : idx}
                  </div>
                  <span
                    className={`text-xs font-medium hidden sm:block ${
                      isActive ? "text-dxc-royal" : isDone ? "text-dxc-melon" : "text-dxc-royal/50"
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <div className={`h-0.5 flex-1 mx-2 rounded ${isDone ? "bg-dxc-melon" : "bg-dxc-canvas"}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
