import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS } from "@/lib/mockData";
import type { ColumnMetadata } from "@/types/app";

const TYPE_BADGES: Record<string, { color: string; bg: string; icon: string }> = {
  target: { color: "#FFFFFF", bg: "#FF7E51", icon: "🎯" },
  date: { color: "#FFFFFF", bg: "#004AAC", icon: "📅" },
  numeric: { color: "#FFFFFF", bg: "#4995FF", icon: "🔢" },
  category: { color: "#0E1020", bg: "#FFAE41", icon: "🏷️" },
  identifier: { color: "#FFFFFF", bg: "#888888", icon: "🆔" },
  ignore: { color: "#FFFFFF", bg: "#D14600", icon: "🚫" },
};

export function StepMetadata() {
  const { dataset, updateDataset, setOnboardingStep } = useAppStore();
  const { columns, detectedSector, businessRules } = dataset;
  const sectorInfo = SECTOR_LABELS[detectedSector];

  const updateColumn = (idx: number, field: keyof ColumnMetadata, value: string) => {
    const updated = [...columns];
    updated[idx] = { ...updated[idx], [field]: value };
    updateDataset({ columns: updated });
  };

  const targetCol = columns.find((c) => c.semanticType === "target");

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <h2 className="text-xl font-bold text-dxc-royal mb-6">Métadonnées & Compréhension</h2>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left — 60% */}
        <div className="lg:col-span-3 space-y-4">
          <div className="rounded-xl overflow-hidden border border-dxc-canvas shadow-sm">
            <div className="bg-dxc-midnight px-4 py-2">
              <span className="text-dxc-peach font-semibold text-sm">Décrivez vos données</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-dxc-canvas">
                    <th className="px-3 py-2 text-left text-dxc-midnight font-semibold">Nom original</th>
                    <th className="px-3 py-2 text-left text-dxc-midnight font-semibold">Nom métier</th>
                    <th className="px-3 py-2 text-left text-dxc-midnight font-semibold">Type</th>
                    <th className="px-3 py-2 text-left text-dxc-midnight font-semibold">Unité</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map((col, i) => {
                    const badge = TYPE_BADGES[col.semanticType];
                    return (
                      <tr key={col.originalName} className={`border-b border-dxc-canvas ${col.semanticType === "target" ? "bg-[#FFF3EE]" : "bg-dxc-white"}`}>
                        <td className="px-3 py-2">
                          <span className="bg-dxc-canvas text-dxc-midnight font-mono text-[11px] px-2 py-0.5 rounded">
                            {col.semanticType === "target" && "🎯 "}{col.originalName}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={col.businessName}
                            onChange={(e) => updateColumn(i, "businessName", e.target.value)}
                            className="bg-transparent border-b border-dxc-royal/30 focus:border-dxc-royal outline-none text-dxc-midnight w-full py-1"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={col.semanticType}
                            onChange={(e) => updateColumn(i, "semanticType", e.target.value)}
                            className="text-[11px] rounded px-2 py-1 font-semibold border-0"
                            style={{ backgroundColor: badge.bg, color: badge.color }}
                          >
                            {Object.entries(TYPE_BADGES).map(([key, b]) => (
                              <option key={key} value={key}>{b.icon} {key}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={col.unit}
                            onChange={(e) => updateColumn(i, "unit", e.target.value)}
                            className="bg-transparent border-b border-dxc-royal/30 focus:border-dxc-royal outline-none text-dxc-midnight w-16 py-1"
                            placeholder="—"
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Business rules */}
          <div className="space-y-2">
            <label className="text-sm font-semibold text-dxc-midnight">Règles métier</label>
            <textarea
              value={businessRules}
              onChange={(e) => updateDataset({ businessRules: e.target.value })}
              rows={3}
              className="w-full rounded-lg border border-dxc-sky bg-dxc-canvas p-3 text-dxc-midnight text-sm placeholder:text-dxc-royal/40 focus:border-dxc-royal focus:outline-none"
              placeholder="Ajoutez des contraintes métier... Ex: Un client avec moins de 3 mois d'ancienneté ne peut pas churner."
            />
          </div>
        </div>

        {/* Right — 40% */}
        <div className="lg:col-span-2">
          <div className="bg-dxc-midnight rounded-xl p-5 space-y-3 sticky top-32">
            <h3 className="text-dxc-peach font-bold text-sm">Ce que le système comprend</h3>
            <div className="space-y-2 text-xs">
              {targetCol && (
                <p className="text-dxc-white">✅ Variable cible : "{targetCol.businessName}" →{" "}
                  <span className="bg-dxc-melon text-dxc-white px-1.5 py-0.5 rounded text-[10px] font-semibold">Classification binaire</span>
                </p>
              )}
              <p className="text-dxc-white">✅ {columns.filter((c) => c.semanticType !== "identifier" && c.semanticType !== "target" && c.semanticType !== "ignore").length} features utilisables détectées</p>
              <p className="text-dxc-white">✅ {columns.filter((c) => c.semanticType === "date").length} features temporelles</p>
              <p className="text-dxc-white">✅ {columns.filter((c) => c.semanticType === "category").length} features catégorielles</p>
              {columns.filter((c) => c.semanticType === "identifier").map((c) => (
                <p key={c.originalName} className="text-dxc-gold">⚠️ "{c.originalName}" exclu automatiquement</p>
              ))}
              {columns.filter((c) => c.missingPercent > 5).map((c) => (
                <p key={c.originalName} className="text-dxc-gold">⚠️ {c.missingPercent}% valeurs manquantes sur "{c.originalName}" → Imputation par médiane</p>
              ))}
              <p className="text-dxc-sky">💡 Tâche ML : Classification binaire</p>
              <p className="text-dxc-sky">💡 Modèles candidats : XGBoost · LightGBM</p>
              <p className="text-dxc-peach">⏱ Durée estimée : ~3-4 minutes</p>
            </div>

            {/* Detected sector */}
            <div className="mt-4 pt-4 border-t border-dxc-royal/30 text-center space-y-1">
              <div className="inline-block bg-dxc-royal text-dxc-white px-4 py-2 rounded-lg font-semibold text-sm">
                {sectorInfo.icon} Secteur détecté : {sectorInfo.label}
              </div>
              <p className="text-dxc-sky/70 text-[10px]">Détecté automatiquement — non modifiable</p>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-6">
        <button onClick={() => setOnboardingStep(2)} className="px-6 py-2 text-dxc-royal border border-dxc-royal rounded-lg hover:bg-dxc-canvas transition-colors">
          ← Retour
        </button>
        <button
          onClick={() => setOnboardingStep(4)}
          className="px-8 py-3 rounded-lg font-semibold text-dxc-white bg-dxc-royal hover:bg-dxc-blue transition-colors"
        >
          Suivant →
        </button>
      </div>
    </div>
  );
}
