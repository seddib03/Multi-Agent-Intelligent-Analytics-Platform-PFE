import { useState, useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { AlertTriangle, Check, Copy, Trash2, Eye, EyeOff, ArrowRight, Loader2 } from "lucide-react";
import { t } from "@/lib/i18n";

interface Anomaly {
  id: string;
  type: "duplicates" | "missing" | "outliers" | "format";
  column?: string;
  count: number;
  severity: "high" | "medium" | "low";
  description: string;
  options: { key: string; label: string; icon: React.ReactNode }[];
  selectedOption?: string;
}

const ANOMALY_ICONS = {
  duplicates: <Copy size={16} />,
  missing: <EyeOff size={16} />,
  outliers: <AlertTriangle size={16} />,
  format: <AlertTriangle size={16} />,
};

const SEVERITY_COLORS = {
  high: "bg-destructive/10 text-destructive border-destructive/30",
  medium: "bg-dxc-gold/10 text-dxc-gold border-dxc-gold/30",
  low: "bg-primary/10 text-primary border-primary/30",
};

export function StepAnomalyReview() {
  const { dataset, setOnboardingStep, userPreferences } = useAppStore();
  const lang = userPreferences.language;
  const [analyzing, setAnalyzing] = useState(true);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [resolved, setResolved] = useState<Set<string>>(new Set());

  useEffect(() => {
    const timer = setTimeout(() => {
      const mockAnomalies: Anomaly[] = [
        {
          id: "dup-1", type: "duplicates",
          count: Math.floor(dataset.rowCount * 0.02) || 45, severity: "medium",
          description: `${Math.floor(dataset.rowCount * 0.02) || 45} ${t("duplicateRowsDetected", lang)}`,
          options: [
            { key: "remove", label: t("removeDuplicates", lang), icon: <Trash2 size={12} /> },
            { key: "keep", label: t("keepAll", lang), icon: <Check size={12} /> },
            { key: "ignore", label: t("ignore", lang), icon: <EyeOff size={12} /> },
          ],
        },
        {
          id: "missing-1", type: "missing",
          column: dataset.columns[0]?.originalName || "revenue",
          count: Math.floor(dataset.rowCount * 0.05) || 120, severity: "high",
          description: `${Math.floor(dataset.rowCount * 0.05) || 120} ${t("missingValuesIn", lang)} "${dataset.columns[0]?.originalName || "revenue"}"`,
          options: [
            { key: "median", label: t("medianImputationLabel", lang), icon: <Check size={12} /> },
            { key: "mean", label: t("meanImputation", lang), icon: <Check size={12} /> },
            { key: "remove", label: t("removeRows", lang), icon: <Trash2 size={12} /> },
            { key: "ignore", label: t("ignore", lang), icon: <EyeOff size={12} /> },
          ],
        },
        {
          id: "outliers-1", type: "outliers",
          column: dataset.columns[1]?.originalName || "amount",
          count: 23, severity: "low",
          description: `23 ${t("outliersDetectedIn", lang)} "${dataset.columns[1]?.originalName || "amount"}"`,
          options: [
            { key: "cap", label: t("capWinsorize", lang), icon: <Check size={12} /> },
            { key: "remove", label: t("remove", lang), icon: <Trash2 size={12} /> },
            { key: "keep", label: t("keep", lang), icon: <Eye size={12} /> },
          ],
        },
        {
          id: "format-1", type: "format",
          column: "date_transaction", count: 89, severity: "medium",
          description: `89 ${t("inconsistentFormatsIn", lang)} "date_transaction"`,
          options: [
            { key: "standardize", label: t("standardizeIso", lang), icon: <Check size={12} /> },
            { key: "ignore", label: t("ignore", lang), icon: <EyeOff size={12} /> },
          ],
        },
      ];
      setAnomalies(mockAnomalies);
      setAnalyzing(false);
    }, 2500);
    return () => clearTimeout(timer);
  }, [dataset, lang]);

  const handleSelectOption = (anomalyId: string, optionKey: string) => {
    setAnomalies((prev) => prev.map((a) => (a.id === anomalyId ? { ...a, selectedOption: optionKey } : a)));
    setResolved((prev) => new Set([...prev, anomalyId]));
  };

  const allResolved = anomalies.length > 0 && resolved.size === anomalies.length;

  if (analyzing) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16">
        <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <Loader2 className="w-8 h-8 text-primary animate-spin" />
        </div>
        <h2 className="text-xl font-bold text-foreground mb-2">{t("analyzing", lang)}</h2>
        <p className="text-muted-foreground text-sm">{t("detectingAnomalies", lang)}</p>
        <div className="mt-8 flex justify-center gap-2 flex-wrap">
          {[t("duplicates", lang), t("missingValuesLabel", lang), t("outliers", lang), t("formats", lang)].map((step, i) => (
            <div key={step} className="px-3 py-1.5 rounded-full text-xs bg-muted text-muted-foreground animate-pulse" style={{ animationDelay: `${i * 0.2}s` }}>
              {step}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-xl font-bold text-foreground mb-2">{t("anomaliesDetected", lang)}</h2>
        <p className="text-muted-foreground text-sm">
          {anomalies.length} {t("issuesDetected", lang)}
        </p>
      </div>

      <div className="space-y-4">
        {anomalies.map((anomaly) => {
          const isResolved = resolved.has(anomaly.id);
          return (
            <div key={anomaly.id} className={`bg-card rounded-xl border-2 transition-all ${isResolved ? (anomaly.selectedOption === "ignore" ? "border-dxc-gold/50 bg-dxc-gold/5" : "border-green-500/50 bg-green-500/5") : "border-border"}`}>
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${SEVERITY_COLORS[anomaly.severity]}`}>
                    {ANOMALY_ICONS[anomaly.type]}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`text-xs uppercase font-bold px-2 py-0.5 rounded ${SEVERITY_COLORS[anomaly.severity]}`}>
                        {anomaly.severity === "high" ? t("severityHigh", lang) : anomaly.severity === "medium" ? t("severityMedium", lang) : t("severityLow", lang)}
                      </span>
                      {isResolved && (
                        <span className={`text-xs uppercase font-bold px-2 py-0.5 rounded ${anomaly.selectedOption === "ignore" ? "bg-dxc-gold/10 text-dxc-gold" : "bg-green-500/10 text-green-600"}`}>
                          <Check size={10} className="inline mr-1" />{t("resolved", lang)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-medium text-foreground">{anomaly.description}</p>
                    {anomaly.column && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {t("column", lang)}: <code className="bg-muted px-1 rounded">{anomaly.column}</code>
                      </p>
                    )}
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {anomaly.options.map((option) => {
                    const isSelected = anomaly.selectedOption === option.key;
                    return (
                      <button
                        key={option.key}
                        onClick={() => handleSelectOption(anomaly.id, option.key)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                          isSelected ? "bg-primary text-primary-foreground" : "bg-muted text-foreground hover:bg-primary/10"
                        }`}
                      >
                        {option.icon}{option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-between items-center pt-6 flex-wrap gap-3">
        <button onClick={() => setOnboardingStep(3)} className="text-sm text-muted-foreground hover:text-foreground">
          ← {t("backToMetadata", lang)}
        </button>
        <div className="flex gap-3">
          <button
            onClick={() => { anomalies.forEach((a) => { if (!resolved.has(a.id)) handleSelectOption(a.id, "ignore"); }); }}
            className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            {t("ignoreAll", lang)}
          </button>
          {/* if the review step is ever reached it should behave like launch since quality is disabled */}
          <button
            onClick={() => setOnboardingStep(4)}
            disabled={!allResolved}
            className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium hover:opacity-90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t("continue", lang)} <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
