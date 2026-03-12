import { useState, useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS, generateFeatureImportance, generateEntities, SECTOR_KPIS } from "@/lib/mockData";
import { ACCENT_THEMES } from "@/types/app";
import { Rocket } from "lucide-react";
import { t } from "@/lib/i18n";

interface LaunchStep {
  label: string;
  agent: string;
  detail: string;
  result: string;
}

export function StepConfirmation() {
  const { onboarding, dataset, userPreferences, setOnboardingStep, setPhase, updateModelResults, updatePreferences } = useAppStore();
  const lang = userPreferences.language;
  const [launching, setLaunching] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);
  const [done, setDone] = useState(false);

  const sectorInfo  = SECTOR_LABELS[dataset.detectedSector] ?? { icon: "📊", label: dataset.detectedSector ?? "Général" };
  const safeSector  = dataset.detectedSector in SECTOR_LABELS ? dataset.detectedSector : "finance";
  const accentTheme = ACCENT_THEMES[userPreferences.accentTheme];
  const targetCol   = dataset.columns.find((c) => c.semanticType === "target");
  const sectorContext = onboarding.sectorContext;

  // when sectorContext is missing (e.g. after navigating back to settings)
  // fall back to the dataset value so that the launch animation still shows
  // a valid sector instead of "Unknown".
  const displaySector = sectorContext?.sector || dataset.detectedSector || "Unknown";
  const displayConfidence = sectorContext?.confidence ?? 0;
  const displayDashboardFocus = sectorContext?.dashboard_focus;

  const LAUNCH_STEPS: LaunchStep[] = [
    { 
      label: "Sector Detection Agent", 
      agent: lang === "fr" ? "Détection du secteur ·" : "Sector detection ·", 
      detail: displaySector, 
      result: `✅ ${displaySector} - ${ (displayConfidence * 100).toFixed(1) }%` 
    },
    { 
      label: "Orchestrator", 
      agent: lang === "fr" ? "Initialisation de l'orchestrateur ·" : "Orchestrator initialization ·", 
      detail: "Coordination des agents", 
      result: "✅ Orchestrator ready" 
    },
    { 
      label: "Dashboard Generation", 
      agent: lang === "fr" ? "Création du dashboard ·" : "Dashboard creation ·", 
      detail: "Feature importance & Analysis", 
      result: `✅ ${t("insightsGenerated", lang)}` 
    },
    { 
      label: "Chatbot / NLQ Interface", 
      agent: lang === "fr" ? "Initialisation du chatbot ·" : "Chatbot initialization ·", 
      detail: "Natural Language Queries", 
      result: "✅ NLQ Interface ready" 
    },
  ];

  const handleLaunch = () => { setLaunching(true); setCurrentStep(0); };

  useEffect(() => {
    if (currentStep < 0 || currentStep >= LAUNCH_STEPS.length) return;
    const timer = setTimeout(() => {
      if (currentStep < LAUNCH_STEPS.length - 1) {
        setCurrentStep(currentStep + 1);
      } else {
        const fi       = generateFeatureImportance(dataset.columns);
        const entities = generateEntities(safeSector);
        updateModelResults({ featureImportance: fi, topRiskyEntities: entities });
        const kpis = SECTOR_KPIS[safeSector] ?? [];
        updatePreferences({ visibleKPIs: kpis.map((k) => k.key) });
        setDone(true);
        // after launch sequence complete move to dashboard (phase 2)
        setTimeout(() => setPhase(2), 1500);
      }
    }, 1800);
    return () => clearTimeout(timer);
  }, [currentStep]);

  if (launching) {
    return (
      <div className="max-w-2xl mx-auto py-12 space-y-6 animate-fade-in">
        <h2 className="text-xl font-bold text-primary text-center mb-8">{t("analysisInProgress", lang)}</h2>
        {LAUNCH_STEPS.map((step, i) => (
          <div key={i} className={`transition-all duration-500 ${i <= currentStep ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>
            <div className="bg-card rounded-xl p-4 border border-border shadow-sm space-y-2">
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-foreground">{t("stepLabel", lang)} {i + 1}</span>
                <span className="text-sm font-semibold text-primary">{step.label}</span>
              </div>
              <p className="text-xs text-muted-foreground">{step.agent} {step.detail}</p>
              {i <= currentStep && (
                <div className="space-y-1">
                  <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-dxc-melon rounded-full transition-all duration-1000" style={{ width: i < currentStep ? "100%" : "80%" }} />
                  </div>
                  {i < currentStep && <p className="text-xs text-primary font-medium">✅ {step.result}</p>}
                </div>
              )}
            </div>
          </div>
        ))}
        {done && (
          <div className="text-center animate-fade-in">
            <p className="text-dxc-melon font-bold">✅ {t("systemReady", lang)}</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <h2 className="text-xl font-bold text-primary">{t("confirmationTitle", lang)}</h2>

      <div className="bg-card rounded-2xl border border-border shadow-sm divide-y divide-border">
        <div className="p-5 space-y-2">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t("useCase", lang)}</h3>
          <p className="text-sm text-foreground line-clamp-2">{onboarding.useCaseDescription}</p>
          <div className="flex gap-2 mt-2 flex-wrap">
            <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded font-medium">{sectorInfo.icon} {onboarding.sectorContext?.sector || sectorInfo.label}</span>
            {onboarding.sectorContext && (
              <>
                <span className="text-xs bg-dxc-sky text-white px-2 py-0.5 rounded font-medium">📊 Confidence: {(onboarding.sectorContext.confidence * 100).toFixed(1)}%</span>
                <span className="text-xs bg-dxc-peach text-white px-2 py-0.5 rounded font-medium">🎯 {onboarding.sectorContext.dashboard_focus}</span>
              </>
            )}
          </div>
        </div>

        <div className="p-5">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t("dataset", lang)}</h3>
          <p className="text-sm text-foreground font-medium mt-1">📄 {dataset.fileName}</p>
          <div className="flex gap-2 mt-1">
            <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">{dataset.rowCount.toLocaleString()} {t("rows", lang)}</span>
            <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">{dataset.columnCount} {t("cols", lang)}</span>
          </div>
        </div>

        {targetCol && (
          <div className="p-5">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t("targetVariableLabel", lang)}</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs bg-dxc-melon text-white px-2 py-0.5 rounded font-semibold">🎯 {targetCol.businessName}</span>
              <span className="text-xs text-muted-foreground">{t("binaryClassification", lang)}</span>
            </div>
          </div>
        )}

        <div className="p-5">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">{t("features", lang)}</h3>
          <div className="flex flex-wrap gap-1.5">
            {dataset.columns.filter((c) => c.semanticType !== "identifier" && c.semanticType !== "target" && c.semanticType !== "ignore").map((c) => (
              <span key={c.originalName} className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">{c.businessName}</span>
            ))}
          </div>
        </div>

        <div className="p-5">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">{t("preferences", lang)}</h3>
          <div className="flex gap-4 text-xs text-foreground flex-wrap">
            <span>{userPreferences.darkMode ? "🌙 " + t("dark", lang) : "☀️ " + t("light", lang)}</span>
            <span>📊 {userPreferences.chartStyle}</span>
            <span>📐 {userPreferences.density}</span>
            <span style={{ color: accentTheme.primary }}>● {accentTheme.label}</span>
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center flex-wrap gap-3">
        <button onClick={() => setOnboardingStep(3)} className="px-6 py-2 text-primary border border-primary rounded-lg hover:bg-primary/5 transition-colors">
          ← {t("back", lang)}
        </button>
        <button
          onClick={handleLaunch}
          className="flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-white bg-dxc-melon hover:bg-dxc-red transition-colors text-base w-full sm:w-auto justify-center"
        >
          <Rocket size={18} /> {t("launchAnalysis", lang)}
        </button>
      </div>
    </div>
  );
}