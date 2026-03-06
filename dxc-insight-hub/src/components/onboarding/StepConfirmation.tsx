import { useState, useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS, generateFeatureImportance, generateEntities, SECTOR_KPIS } from "@/lib/mockData";
import { ACCENT_THEMES } from "@/types/app";
import { Rocket } from "lucide-react";

interface LaunchStep {
  label: string;
  agent: string;
  detail: string;
  result: string;
}

const LAUNCH_STEPS: LaunchStep[] = [
  { label: "Data Preparation Agent", agent: "Nettoyage · Normalisation · Imputation", detail: "des valeurs manquantes", result: "42 312 lignes traitées en 1.2s" },
  { label: "Generic Predictive Agent (AutoML)", agent: "Test XGBoost · LightGBM ·", detail: "Logistic Regression", result: "XGBoost sélectionné — AUC: 0.871 · F1: 0.83" },
  { label: "Insight Agent", agent: "Génération des métriques ·", detail: "Feature importance", result: "8 insights générés" },
];

export function StepConfirmation() {
  const { onboarding, dataset, userPreferences, setOnboardingStep, setPhase, updateModelResults, updatePreferences } = useAppStore();
  const [launching, setLaunching] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);
  const [done, setDone] = useState(false);

  const sectorInfo = SECTOR_LABELS[dataset.detectedSector];
  const accentTheme = ACCENT_THEMES[userPreferences.accentTheme];
  const targetCol = dataset.columns.find((c) => c.semanticType === "target");

  const handleLaunch = () => {
    setLaunching(true);
    setCurrentStep(0);
  };

  useEffect(() => {
    if (currentStep < 0 || currentStep >= LAUNCH_STEPS.length) return;
    const timer = setTimeout(() => {
      if (currentStep < LAUNCH_STEPS.length - 1) {
        setCurrentStep(currentStep + 1);
      } else {
        // Finalize
        const fi = generateFeatureImportance(dataset.columns);
        const entities = generateEntities(dataset.detectedSector);
        updateModelResults({ featureImportance: fi, topRiskyEntities: entities });

        const kpis = SECTOR_KPIS[dataset.detectedSector];
        updatePreferences({ visibleKPIs: kpis.map((k) => k.key) });

        setDone(true);
        setTimeout(() => setPhase(2), 1500);
      }
    }, 1800);
    return () => clearTimeout(timer);
  }, [currentStep, dataset, setPhase, updateModelResults, updatePreferences]);

  if (launching) {
    return (
      <div className="max-w-2xl mx-auto py-12 space-y-6 animate-fade-in">
        <h2 className="text-xl font-bold text-dxc-royal text-center mb-8">Analyse en cours...</h2>
        {LAUNCH_STEPS.map((step, i) => (
          <div
            key={i}
            className={`transition-all duration-500 ${i <= currentStep ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}
          >
            <div className="bg-dxc-white rounded-xl p-4 border border-dxc-canvas shadow-sm space-y-2">
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-dxc-midnight">Étape {i + 1}</span>
                <span className="text-sm font-semibold text-dxc-royal">{step.label}</span>
              </div>
              <p className="text-xs text-dxc-midnight/60">{step.agent} {step.detail}</p>
              {i <= currentStep && (
                <div className="space-y-1">
                  <div className="h-1.5 bg-dxc-canvas rounded-full overflow-hidden">
                    <div
                      className="h-full bg-dxc-melon rounded-full transition-all duration-1000"
                      style={{ width: i < currentStep ? "100%" : "80%" }}
                    />
                  </div>
                  {i < currentStep && (
                    <p className="text-xs text-dxc-royal font-medium">✅ {step.result}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {done && (
          <div className="text-center animate-fade-in">
            <p className="text-dxc-melon font-bold">✅ Système prêt — Bienvenue dans votre espace personnalisé</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <h2 className="text-xl font-bold text-dxc-royal">Confirmation & Lancement</h2>

      <div className="bg-dxc-white rounded-2xl border border-dxc-canvas shadow-sm divide-y divide-dxc-canvas">
        {/* Use Case */}
        <div className="p-5 space-y-2">
          <h3 className="text-xs font-semibold text-dxc-midnight/50 uppercase tracking-wider">Use Case</h3>
          <p className="text-sm text-dxc-midnight line-clamp-2">{onboarding.useCaseDescription}</p>
          <div className="flex gap-2 mt-2">
            <span className="text-[11px] bg-dxc-royal text-dxc-white px-2 py-0.5 rounded font-medium">{sectorInfo.icon} {sectorInfo.label}</span>
            {onboarding.analysisTypes.map((t) => (
              <span key={t} className="text-[11px] bg-dxc-melon text-dxc-white px-2 py-0.5 rounded font-medium">{t}</span>
            ))}
          </div>
        </div>

        {/* Dataset */}
        <div className="p-5 flex items-center gap-3">
          <div className="flex-1">
            <h3 className="text-xs font-semibold text-dxc-midnight/50 uppercase tracking-wider">Dataset</h3>
            <p className="text-sm text-dxc-midnight font-medium mt-1">📄 {dataset.fileName}</p>
            <div className="flex gap-2 mt-1">
              <span className="text-[11px] bg-dxc-canvas text-dxc-royal px-2 py-0.5 rounded">{dataset.rowCount.toLocaleString()} lignes</span>
              <span className="text-[11px] bg-dxc-canvas text-dxc-royal px-2 py-0.5 rounded">{dataset.columnCount} colonnes</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-dxc-royal">{dataset.qualityScore}/100</div>
        </div>

        {/* Target */}
        {targetCol && (
          <div className="p-5">
            <h3 className="text-xs font-semibold text-dxc-midnight/50 uppercase tracking-wider">Variable cible</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] bg-dxc-melon text-dxc-white px-2 py-0.5 rounded font-semibold">🎯 {targetCol.businessName}</span>
              <span className="text-xs text-dxc-midnight/60">Classification binaire</span>
            </div>
          </div>
        )}

        {/* Features */}
        <div className="p-5">
          <h3 className="text-xs font-semibold text-dxc-midnight/50 uppercase tracking-wider mb-2">Features</h3>
          <div className="flex flex-wrap gap-1.5">
            {dataset.columns
              .filter((c) => c.semanticType !== "identifier" && c.semanticType !== "target" && c.semanticType !== "ignore")
              .map((c) => (
                <span key={c.originalName} className="text-[11px] bg-[#EEF8FF] text-dxc-blue px-2 py-0.5 rounded">{c.businessName}</span>
              ))}
          </div>
        </div>

        {/* Preferences */}
        <div className="p-5">
          <h3 className="text-xs font-semibold text-dxc-midnight/50 uppercase tracking-wider mb-2">Préférences</h3>
          <div className="flex gap-4 text-xs text-dxc-midnight">
            <span>{userPreferences.darkMode ? "🌙 Sombre" : "☀️ Clair"}</span>
            <span>📊 {userPreferences.chartStyle}</span>
            <span>📐 {userPreferences.density}</span>
            <span style={{ color: accentTheme.primary }}>● {accentTheme.label}</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <button onClick={() => setOnboardingStep(3)} className="px-6 py-2 text-dxc-royal border border-dxc-royal rounded-lg hover:bg-dxc-canvas transition-colors">
          ← Retour
        </button>
        <button
          onClick={handleLaunch}
          className="flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-dxc-white bg-dxc-melon hover:bg-dxc-red transition-colors text-base w-full sm:w-auto justify-center"
        >
          <Rocket size={18} /> Lancer l'analyse
        </button>
      </div>
    </div>
  );
}
