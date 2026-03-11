import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS } from "@/lib/mockData";
import type { ColumnMetadata } from "@/types/app";
import { t } from "@/lib/i18n";

const TYPE_BADGES: Record<string, { color: string; bg: string; icon: string }> = {
  target: { color: "#FFFFFF", bg: "#FF7E51", icon: "🎯" },
  date: { color: "#FFFFFF", bg: "#004AAC", icon: "📅" },
  numeric: { color: "#FFFFFF", bg: "#4995FF", icon: "🔢" },
  category: { color: "#0E1020", bg: "#FFAE41", icon: "🏷️" },
  identifier: { color: "#FFFFFF", bg: "#888888", icon: "🆔" },
  ignore: { color: "#FFFFFF", bg: "#D14600", icon: "🚫" },
};

export function StepMetadata() {
  const { dataset, updateDataset, setOnboardingStep, userPreferences } = useAppStore();
  const lang = userPreferences.language;
  const { columns, detectedSector, businessRules } = dataset;
  const sectorInfo = SECTOR_LABELS[detectedSector] ?? { icon: "📊", label: detectedSector ?? "General" };

  const updateColumn = (idx: number, field: keyof ColumnMetadata, value: string) => {
    const updated = [...columns];
    updated[idx] = { ...updated[idx], [field]: value };
    updateDataset({ columns: updated });
  };

  const targetCol = columns.find((c) => c.semanticType === "target");

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <h2 className="text-xl font-bold text-primary mb-6">{t("metadataTitle", lang)}</h2>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-4">
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
                    <th className="px-3 py-2 text-left text-foreground font-semibold">{t("type", lang)}</th>
                    <th className="px-3 py-2 text-left text-foreground font-semibold">{t("unit", lang)}</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map((col, i) => {
                    const badge = TYPE_BADGES[col.semanticType] ?? TYPE_BADGES["ignore"];
                    return (
                      <tr key={col.originalName} className={`border-b border-border ${col.semanticType === "target" ? "bg-dxc-melon/10" : "bg-card"}`}>
                        <td className="px-3 py-2">
                          <span className="bg-muted text-foreground font-mono text-xs px-2 py-0.5 rounded">
                            {col.semanticType === "target" && "🎯 "}{col.originalName}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <input value={col.businessName} onChange={(e) => updateColumn(i, "businessName", e.target.value)} className="bg-transparent border-b border-primary/30 focus:border-primary outline-none text-foreground w-full py-1" />
                        </td>
                        <td className="px-3 py-2">
                          <select value={col.semanticType} onChange={(e) => updateColumn(i, "semanticType", e.target.value)} className="text-xs rounded px-2 py-1 font-semibold border-0" style={{ backgroundColor: badge.bg, color: badge.color }}>
                            {Object.entries(TYPE_BADGES).map(([key, b]) => (
                              <option key={key} value={key}>{b.icon} {key}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <input value={col.unit} onChange={(e) => updateColumn(i, "unit", e.target.value)} className="bg-transparent border-b border-primary/30 focus:border-primary outline-none text-foreground w-16 py-1" placeholder="—" />
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

        <div className="lg:col-span-2">
          <div className="bg-dxc-midnight rounded-xl p-5 space-y-3 sticky top-32">
            <h3 className="text-dxc-peach font-bold text-sm">{t("systemUnderstands", lang)}</h3>
            <div className="space-y-2 text-xs">
              {targetCol && (
                <p className="text-white">✅ {t("targetVariable", lang)} : "{targetCol.businessName}" →{" "}
                  <span className="bg-dxc-melon text-white px-1.5 py-0.5 rounded text-xs font-semibold">{t("binaryClassification", lang)}</span>
                </p>
              )}
              <p className="text-white">✅ {columns.filter((c) => c.semanticType !== "identifier" && c.semanticType !== "target" && c.semanticType !== "ignore").length} {t("usableFeatures", lang)}</p>
              <p className="text-white">✅ {columns.filter((c) => c.semanticType === "date").length} {t("temporalFeatures", lang)}</p>
              <p className="text-white">✅ {columns.filter((c) => c.semanticType === "category").length} {t("categoricalFeatures", lang)}</p>
              {columns.filter((c) => c.semanticType === "identifier").map((c) => (
                <p key={c.originalName} className="text-dxc-gold">⚠️ "{c.originalName}" {t("autoExcluded", lang)}</p>
              ))}
              {columns.filter((c) => (c.missingPercent ?? 0) > 5).map((c) => (
                <p key={c.originalName} className="text-dxc-gold">⚠️ {c.missingPercent}% {t("missingValues", lang)} "{c.originalName}" → {t("medianImputation", lang)}</p>
              ))}
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
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-6">
        <button onClick={() => setOnboardingStep(2)} className="px-6 py-2 text-primary border border-primary rounded-lg hover:bg-primary/5 transition-colors">
          ← {t("back", lang)}
        </button>
        <button onClick={() => setOnboardingStep(4)} className="px-8 py-3 rounded-lg font-semibold text-primary-foreground bg-primary hover:opacity-90 transition-colors">
          {t("next", lang)} →
        </button>
      </div>
    </div>
  );
}
