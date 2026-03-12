import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS } from "@/lib/mockData";
import type { ColumnMetadata } from "@/types/app";
import { t } from "@/lib/i18n";

type SemanticType = "numeric" | "date" | "category" | "target" | "identifier" | "ignore";

const TYPE_BADGES: Record<SemanticType, { color: string; bg: string; icon: string; label: string }> = {
  numeric:    { color: "#FFFFFF", bg: "#004AAC", icon: "🔢", label: "Numérique" },
  category:   { color: "#0E1020", bg: "#FFAE41", icon: "🔤", label: "Texte" },
  date:       { color: "#FFFFFF", bg: "#4995FF", icon: "📅", label: "Date / Heure" },
  target:     { color: "#FFFFFF", bg: "#FF7E51", icon: "🎯", label: "Cible" },
  identifier: { color: "#FFFFFF", bg: "#666666", icon: "🆔", label: "Identifiant" },
  ignore:     { color: "#FFFFFF", bg: "#D14600", icon: "🚫", label: "Ignorer" },
};

export function StepMetadata() {
  const { dataset, onboarding, updateDataset, setOnboardingStep, userPreferences } = useAppStore();
  const lang = userPreferences.language;
  const { detectedSector, businessRules } = dataset;
  const sectorContext = onboarding.sectorContext;

  const uploadedDatasets: { fileName: string; columns: ColumnMetadata[] }[] =
    (dataset as never as { uploadedDatasets?: { fileName: string; columns: ColumnMetadata[] }[] })
      .uploadedDatasets ?? [{ fileName: dataset.fileName, columns: dataset.columns }];

  const [activeDsIdx, setActiveDsIdx] = useState(0);
  const [localDatasets, setLocalDatasets] = useState(uploadedDatasets);

  const sectorInfo = SECTOR_LABELS[detectedSector] ?? { icon: "📊", label: detectedSector ?? "Général" };
  const activeDs   = localDatasets[activeDsIdx] ?? { fileName: "", columns: [] };
  const columns    = activeDs.columns;

  const updateColumn = (colIdx: number, field: keyof ColumnMetadata, value: string) => {
    setLocalDatasets((prev) => {
      const next = prev.map((ds, di) => {
        if (di !== activeDsIdx) return ds;
        const updatedCols = ds.columns.map((col, ci) =>
          ci === colIdx ? { ...col, [field]: value } : col
        );
        return { ...ds, columns: updatedCols };
      });
      updateDataset({ columns: next[0].columns, uploadedDatasets: next } as never);
      return next;
    });
  };

  const targetCol = columns.find((c) => c.semanticType === "target");

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <h2 className="text-xl font-bold text-primary mb-6">{t("metadataTitle", lang)}</h2>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-4">

          {/* ── Sélecteur de dataset si plusieurs ── */}
          {localDatasets.length > 1 && (
            <div className="flex items-center gap-3 bg-muted rounded-lg px-4 py-2">
              <button
                onClick={() => setActiveDsIdx((i) => Math.max(0, i - 1))}
                disabled={activeDsIdx === 0}
                className="p-1 rounded hover:bg-primary/10 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={18} className="text-primary" />
              </button>
              <div className="flex-1 text-center">
                <span className="text-sm font-semibold text-foreground">{activeDs.fileName}</span>
                <span className="text-xs text-muted-foreground ml-2">({activeDsIdx + 1} / {localDatasets.length})</span>
              </div>
              <button
                onClick={() => setActiveDsIdx((i) => Math.min(localDatasets.length - 1, i + 1))}
                disabled={activeDsIdx === localDatasets.length - 1}
                className="p-1 rounded hover:bg-primary/10 disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={18} className="text-primary" />
              </button>
            </div>
          )}

          {/* ── Tableau des colonnes ── */}
          <div className="rounded-xl overflow-hidden border border-border shadow-sm">
            <div className="bg-dxc-midnight px-4 py-2">
              <span className="text-dxc-peach font-semibold text-sm">{t("describeData", lang)}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted">
                    <th className="px-3 py-2 text-left text-foreground font-semibold">{t("originalName", lang)}</th>
                    <th className="px-3 py-2 text-left text-foreground font-semibold">{t("businessName", lang)}</th>
                    <th className="px-3 py-2 text-left text-foreground font-semibold">Type</th>
                    <th className="px-3 py-2 text-left text-foreground font-semibold">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map((col, i) => {
                    const semType = (col.semanticType as SemanticType) ?? "category";
                    const badge   = TYPE_BADGES[semType] ?? TYPE_BADGES["category"];
                    return (
                      <tr key={col.originalName} className={`border-b border-border ${semType === "target" ? "bg-dxc-melon/10" : "bg-card"}`}>
                        <td className="px-3 py-2">
                          <span className="bg-muted text-foreground font-mono text-xs px-2 py-0.5 rounded">
                            {semType === "target" && "🎯 "}{col.originalName}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={col.businessName}
                            onChange={(e) => updateColumn(i, "businessName", e.target.value)}
                            className="bg-transparent border-b border-primary/30 focus:border-primary outline-none text-foreground w-full py-1"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={semType}
                            onChange={(e) => updateColumn(i, "semanticType", e.target.value)}
                            className="text-xs rounded px-2 py-1 font-semibold border-0 cursor-pointer"
                            style={{ backgroundColor: badge.bg, color: badge.color }}
                          >
                            {(Object.entries(TYPE_BADGES) as [SemanticType, typeof TYPE_BADGES[SemanticType]][]).map(([key, b]) => (
                              <option key={key} value={key}>{b.icon} {b.label}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={(col as never as { description?: string }).description ?? ""}
                            onChange={(e) => updateColumn(i, "description" as keyof ColumnMetadata, e.target.value)}
                            className="bg-transparent border-b border-primary/30 focus:border-primary outline-none text-foreground w-full py-1"
                            placeholder="Description…"
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">{t("businessRules", lang)}</label>
            <textarea
              value={businessRules}
              onChange={(e) => updateDataset({ businessRules: e.target.value })}
              rows={3}
              className="w-full rounded-lg border border-border bg-muted p-3 text-foreground text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none"
              placeholder={t("businessRulesPlaceholder", lang)}
            />
          </div>
        </div>

        {/* ── Panneau récapitulatif (sans qualité) ── */}
        <div className="lg:col-span-2">
          <div className="bg-dxc-midnight rounded-xl p-5 space-y-3 sticky top-32">
            <h3 className="text-dxc-peach font-bold text-sm">{t("systemUnderstands", lang)}</h3>
            <div className="space-y-2 text-xs">
              {targetCol && (
                <p className="text-white">✅ {t("targetVariable", lang)} : "{targetCol.businessName}" →{" "}
                  <span className="bg-dxc-melon text-white px-1.5 py-0.5 rounded text-xs font-semibold">{t("binaryClassification", lang)}</span>
                </p>
              )}
              <p className="text-white">✅ {columns.filter((c) => !["identifier", "target", "ignore"].includes(c.semanticType)).length} {t("usableFeatures", lang)}</p>
              <p className="text-white">✅ {columns.filter((c) => c.semanticType === "date").length} {t("temporalFeatures", lang)}</p>
              <p className="text-white">✅ {columns.filter((c) => c.semanticType === "numeric").length} colonnes numériques</p>
              <p className="text-white">✅ {columns.filter((c) => c.semanticType === "category").length} colonnes texte / catégorie</p>
              {columns.filter((c) => c.semanticType === "identifier").map((c) => (
                <p key={c.originalName} className="text-dxc-gold">⚠️ "{c.originalName}" {t("autoExcluded", lang)}</p>
              ))}
              {localDatasets.length > 1 && (
                <p className="text-dxc-sky">📊 {localDatasets.length} sources de données</p>
              )}
              <p className="text-dxc-sky">💡 {t("mlTask", lang)}</p>
              <p className="text-dxc-sky">💡 {t("candidateModels", lang)}</p>
              <p className="text-dxc-peach">⏱ {t("estimatedDuration", lang)}</p>
            </div>

            <div className="mt-4 pt-4 border-t border-dxc-royal/30 text-center space-y-1">
              <div className="inline-block bg-dxc-royal text-white px-4 py-2 rounded-lg font-semibold text-sm">
                {sectorInfo.icon} {t("detectedSector", lang)} : {sectorInfo.label}
              </div>
              <p className="text-dxc-sky text-xs">{t("autoDetectedNoEdit", lang)}</p>
            </div>

            {sectorContext && (
              <div className="mt-4 pt-4 border-t border-dxc-royal/30 space-y-2 text-left">
                <p className="text-dxc-peach text-xs font-semibold">Sector Detection Agent</p>
                <p className="text-white text-xs">
                  Confidence: {(sectorContext.confidence * 100).toFixed(1)}%
                </p>
                <p className="text-white text-xs">
                  Routing target: {sectorContext.routing_target}
                </p>
                <p className="text-dxc-sky text-xs">
                  Focus: {sectorContext.dashboard_focus}
                </p>
                {sectorContext.kpis.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-dxc-peach text-xs">Top KPIs:</p>
                    {sectorContext.kpis.slice(0, 3).map((kpi) => (
                      <p key={kpi.name} className="text-white text-xs">• {kpi.name} ({kpi.unit})</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-6">
        <button onClick={() => setOnboardingStep(2)} className="px-6 py-2 text-primary border border-primary rounded-lg hover:bg-primary/5 transition-colors">
          ← {t("back", lang)}
        </button>
        <button
          onClick={() => setOnboardingStep(4)}
          className="px-8 py-3 rounded-lg font-semibold text-primary-foreground bg-primary hover:opacity-90 transition-colors"
        >
          {t("next", lang)} →
        </button>
      </div>
    </div>
  );
}