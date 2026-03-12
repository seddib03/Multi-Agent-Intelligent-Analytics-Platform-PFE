import { useState, useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS, generateFeatureImportance, generateEntities, SECTOR_KPIS } from "@/lib/mockData";
import { ACCENT_THEMES } from "@/types/app";
import { Rocket } from "lucide-react";
import { t } from "@/lib/i18n";
import { toast } from "sonner";
import { analyzeOrchestrator, type AnalyzeResponse, type InsightChart } from "@/lib/orchestratorApi";
import type { ChartData } from "@/types/app";

interface LaunchStep {
  label: string;
  agent: string;
  detail: string;
  result: string;
}

export function StepConfirmation() {
  const { onboarding, dataset, userPreferences, setOnboardingStep, setPhase, updateModelResults, updatePreferences, clearMessages, addMessage } = useAppStore();
  const lang = userPreferences.language;
  const [launching, setLaunching] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);
  const [done, setDone] = useState(false);

  const sectorInfo  = SECTOR_LABELS[dataset.detectedSector] ?? { icon: "📊", label: dataset.detectedSector ?? "Général" };
  const safeSector  = dataset.detectedSector in SECTOR_LABELS ? dataset.detectedSector : "finance";
  const accentTheme = ACCENT_THEMES[userPreferences.accentTheme];
  const targetCol   = dataset.columns.find((c) => c.semanticType === "target");
  const sectorContext = onboarding.sectorContext;

  const toChartData = (chart: InsightChart): ChartData | null => {
    const rawType = (chart.type || "bar").toLowerCase();
    const type: ChartData["type"] = rawType === "line" || rawType === "pie" || rawType === "area" ? rawType : "bar";
    const xKey = chart.x || "name";
    const yKey = chart.y || "value";
    const rows = Array.isArray(chart.data) ? chart.data : [];
    if (!rows.length) return null;

    return {
      type,
      title: chart.title || "Chart",
      data: rows.map((row) => ({
        name: String(row[xKey] ?? ""),
        [yKey]: Number(row[yKey] ?? 0),
      })),
      dataKeys: [yKey],
    };
  };

  const buildMetadataPayload = () => ({
    columns: dataset.columns.map((c) => ({
      column_name: c.originalName,
      business_name: c.businessName,
      type: c.semanticType,
      description: c.description ?? "",
      nullable: c.missingPercent > 0,
    })),
  });

  const buildAssistantMessage = (result: AnalyzeResponse): { content: string; charts?: ChartData[] } => {
    if (result.needs_clarification) {
      return {
        content: result.clarification_question || result.final_response || "Pouvez-vous préciser votre demande ?",
      };
    }

    const format = (result.response_format || "text").toLowerCase();
    const payload = result.agent_response || {};
    const charts = (Array.isArray(payload.charts) ? payload.charts : [])
      .map(toChartData)
      .filter((chart): chart is ChartData => chart !== null);

    if (format === "kpi") {
      const kpiLines = (payload.kpis || []).map((kpi) => `- ${kpi.name}: ${kpi.value ?? "N/A"}`).join("\n");
      const insightLines = (payload.insights || []).map((insight) => `- ${insight}`).join("\n");
      return {
        content: `Dashboard généré.\n\nKPIs\n${kpiLines || "- Aucun KPI"}\n\nInsights\n${insightLines || "- Aucun insight"}`,
        charts,
      };
    }

    if (format === "chart") {
      return {
        content: result.final_response || "Graphique généré.",
        charts,
      };
    }

    return {
      content: result.final_response || "Réponse reçue.",
      charts: charts.length ? charts : undefined,
    };
  };

  const runInitialAnalyze = async () => {
    const queryRaw = onboarding.useCaseDescription?.trim() || "Generate dashboard insights";

    const result = await analyzeOrchestrator({
      queryRaw,
      datasetFile: dataset.sourceCsvFile ?? null,
      metadata: buildMetadataPayload(),
    });

    const assistant = buildAssistantMessage(result);

    clearMessages();
    addMessage({
      id: `u-${Date.now()}`,
      role: "user",
      content: queryRaw,
      timestamp: new Date(),
    });
    addMessage({
      id: `s-${Date.now()}`,
      role: "system",
      content: assistant.content,
      charts: assistant.charts,
      timestamp: new Date(),
    });
  };

  const LAUNCH_STEPS: LaunchStep[] = [
    { 
      label: "Sector Detection Agent", 
      agent: lang === "fr" ? "Détection du secteur ·" : "Sector detection ·", 
      detail: sectorContext?.sector || "Unknown", 
      result: `✅ ${sectorContext?.sector || "N/A"} - ${(sectorContext?.confidence || 0 * 100).toFixed(1)}%` 
    },
    { 
      label: "Orchestrator", 
      agent: lang === "fr" ? "Initialisation de l'orchestrateur ·" : "Orchestrator initialization ·", 
      detail: "Coordination des agents", 
      result: "✅ Orchestrator ready" 
    },
    { 
      label: "Insight Agent", 
      agent: lang === "fr" ? "Génération des métriques ·" : "Metrics generation ·", 
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
        void (async () => {
          try {
            const fi       = generateFeatureImportance(dataset.columns);
            const entities = generateEntities(safeSector);
            updateModelResults({ featureImportance: fi, topRiskyEntities: entities });
            const kpis = SECTOR_KPIS[safeSector] ?? [];
            updatePreferences({ visibleKPIs: kpis.map((k) => k.key) });
            await runInitialAnalyze();
            setDone(true);
            setTimeout(() => setPhase(2), 1200);
          } catch (error) {
            const message = error instanceof Error ? error.message : "Erreur inconnue";
            toast.error(`Echec du lancement: ${message}`);
            setLaunching(false);
            setCurrentStep(-1);
          }
        })();
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