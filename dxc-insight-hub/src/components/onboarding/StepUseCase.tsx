import { useState } from "react";
import { useAppStore } from "@/stores/appStore";
import type { ChartStyle, AccentTheme, Density } from "@/types/app";
import { ACCENT_THEMES } from "@/types/app";
import { Check } from "lucide-react";

const ANALYSIS_TYPES = ["Prédiction", "Détection d'anomalies", "Segmentation", "Analyse de tendance", "Recommandation"];
const TIME_HORIZONS = ["7 jours", "30 jours", "90 jours", "Personnalisé"];

const CHART_STYLES: { key: ChartStyle; icon: string; label: string }[] = [
  { key: "bar", icon: "📊", label: "Barres" },
  { key: "line", icon: "📈", label: "Courbes" },
  { key: "pie", icon: "🍩", label: "Circulaire" },
  { key: "area", icon: "📉", label: "Aires" },
  { key: "heatmap", icon: "🔥", label: "Heatmap" },
];

const ACCENT_SWATCHES: AccentTheme[] = ["royal-melon", "blue-gold", "midnight-peach", "melon-royal", "gold-blue", "sky-midnight"];

function BarPreview() {
  return (
    <svg width="80" height="50" viewBox="0 0 80 50">
      <rect x="5" y="20" width="12" height="30" fill="#004AAC" rx="2" />
      <rect x="22" y="10" width="12" height="40" fill="#FF7E51" rx="2" />
      <rect x="39" y="25" width="12" height="25" fill="#FFAE41" rx="2" />
      <rect x="56" y="15" width="12" height="35" fill="#4995FF" rx="2" />
    </svg>
  );
}

function LinePreview() {
  return (
    <svg width="80" height="50" viewBox="0 0 80 50">
      <path d="M5 40 Q20 10 40 25 T75 15" stroke="#004AAC" strokeWidth="2.5" fill="none" />
    </svg>
  );
}

function PiePreview() {
  return (
    <svg width="50" height="50" viewBox="0 0 50 50">
      <circle cx="25" cy="25" r="20" fill="none" stroke="#004AAC" strokeWidth="8" strokeDasharray="50 76" strokeDashoffset="0" />
      <circle cx="25" cy="25" r="20" fill="none" stroke="#FF7E51" strokeWidth="8" strokeDasharray="30 96" strokeDashoffset="-50" />
      <circle cx="25" cy="25" r="20" fill="none" stroke="#FFAE41" strokeWidth="8" strokeDasharray="46 80" strokeDashoffset="-80" />
    </svg>
  );
}

function AreaPreview() {
  return (
    <svg width="80" height="50" viewBox="0 0 80 50">
      <path d="M0 50 L10 30 L30 35 L50 15 L70 20 L80 10 L80 50 Z" fill="#A1E6FF" opacity="0.5" />
      <path d="M0 50 L10 30 L30 35 L50 15 L70 20 L80 10" stroke="#A1E6FF" strokeWidth="2" fill="none" />
    </svg>
  );
}

function HeatPreview() {
  const colors = ["#FFC982", "#FFAE41", "#FF7E51", "#FFC982", "#FF7E51", "#D14600", "#FFAE41", "#FFC982", "#FF7E51"];
  return (
    <svg width="54" height="54" viewBox="0 0 54 54">
      {colors.map((c, i) => (
        <rect key={i} x={(i % 3) * 18} y={Math.floor(i / 3) * 18} width="16" height="16" rx="2" fill={c} />
      ))}
    </svg>
  );
}

const CHART_PREVIEWS: Record<ChartStyle, React.FC> = {
  bar: BarPreview,
  line: LinePreview,
  pie: PiePreview,
  area: AreaPreview,
  heatmap: HeatPreview,
};

export function StepUseCase() {
  const { onboarding, updateOnboarding, userPreferences, updatePreferences, setOnboardingStep } = useAppStore();
  const [desc, setDesc] = useState(onboarding.useCaseDescription);
  const [types, setTypes] = useState<string[]>(onboarding.analysisTypes);
  const [horizon, setHorizon] = useState(onboarding.timeHorizon);

  const toggleType = (t: string) => setTypes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));

  const canProceed = desc.trim().length > 10 && types.length > 0;

  const handleNext = () => {
    updateOnboarding({ useCaseDescription: desc, analysisTypes: types, timeHorizon: horizon });
    setOnboardingStep(2);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 animate-fade-in">
      {/* Section A — Besoin métier */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-dxc-royal">Votre besoin métier</h2>
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          rows={6}
          className="w-full rounded-lg border-2 border-dxc-canvas bg-dxc-white p-4 text-dxc-midnight placeholder:text-dxc-royal/40 focus:border-dxc-royal focus:outline-none transition-colors resize-none"
          placeholder="Décrivez votre objectif métier... Ex: Je veux identifier quels clients risquent de se désabonner dans les 30 prochains jours, afin de déclencher des actions de rétention ciblées."
        />
        <p className="text-xs italic text-dxc-royal/60">Le secteur sera détecté automatiquement à partir de votre description</p>

        <div className="space-y-2">
          <label className="text-sm font-semibold text-dxc-midnight">Type d'analyse</label>
          <div className="flex flex-wrap gap-2">
            {ANALYSIS_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                  types.includes(t)
                    ? "bg-dxc-royal text-dxc-white border-dxc-royal"
                    : "bg-dxc-white text-dxc-royal border-dxc-royal/30 hover:border-dxc-royal"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-semibold text-dxc-midnight">Horizon temporel</label>
          <div className="flex gap-2">
            {TIME_HORIZONS.map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  horizon === h
                    ? "bg-dxc-melon text-dxc-white"
                    : "bg-dxc-white text-dxc-midnight border border-dxc-canvas hover:border-dxc-melon"
                }`}
              >
                {h}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t-2 border-dxc-peach/30" />

      {/* Section B — Préférences */}
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-dxc-royal">Personnalisez votre espace de travail</h2>

        {/* Mode */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-dxc-midnight">Mode d'affichage</label>
          <div className="flex rounded-full overflow-hidden border border-dxc-canvas w-fit">
            <button
              onClick={() => updatePreferences({ darkMode: false })}
              className={`px-5 py-2 text-sm font-medium transition-all ${
                !userPreferences.darkMode ? "bg-dxc-midnight text-dxc-peach" : "bg-dxc-canvas text-dxc-midnight"
              }`}
            >
              ☀️ Mode Clair
            </button>
            <button
              onClick={() => updatePreferences({ darkMode: true })}
              className={`px-5 py-2 text-sm font-medium transition-all ${
                userPreferences.darkMode ? "bg-dxc-midnight text-dxc-peach" : "bg-dxc-canvas text-dxc-midnight"
              }`}
            >
              🌙 Mode Sombre
            </button>
          </div>
        </div>

        {/* Chart style */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-dxc-midnight">Style de graphiques préféré</label>
          <div className="flex gap-3 flex-wrap">
            {CHART_STYLES.map(({ key, icon, label }) => {
              const Preview = CHART_PREVIEWS[key];
              const selected = userPreferences.chartStyle === key;
              return (
                <button
                  key={key}
                  onClick={() => updatePreferences({ chartStyle: key })}
                  className={`w-[160px] h-[100px] rounded-xl border-2 flex flex-col items-center justify-center gap-1 transition-all relative ${
                    selected ? "border-dxc-melon bg-[#FFF3EE]" : "border-dxc-canvas bg-dxc-white hover:border-dxc-royal/30"
                  }`}
                >
                  {selected && (
                    <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-dxc-melon flex items-center justify-center">
                      <Check size={12} className="text-dxc-white" />
                    </div>
                  )}
                  <Preview />
                  <span className="text-xs font-medium text-dxc-midnight">{icon} {label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Density */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-dxc-midnight">Densité d'information</label>
          <div className="space-y-3">
            {(["simplified", "standard", "expert"] as Density[]).map((d) => {
              const labels: Record<Density, { title: string; desc: string }> = {
                simplified: { title: "Simplifié", desc: "L'essentiel en un coup d'œil" },
                standard: { title: "Standard", desc: "Équilibre métriques et lisibilité" },
                expert: { title: "Expert", desc: "Toutes les métriques et diagnostics" },
              };
              return (
                <button
                  key={d}
                  onClick={() => updatePreferences({ density: d })}
                  className={`w-full text-left px-4 py-3 rounded-lg border-2 transition-all ${
                    userPreferences.density === d
                      ? "border-dxc-melon bg-[#FFF3EE]"
                      : "border-dxc-canvas bg-dxc-white hover:border-dxc-royal/30"
                  }`}
                >
                  <span className="font-semibold text-sm text-dxc-midnight">{labels[d].title}</span>
                  <span className="text-xs text-dxc-royal/60 ml-2">{labels[d].desc}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Accent */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-dxc-midnight">Accent couleur du dashboard</label>
          <div className="flex gap-3 flex-wrap">
            {ACCENT_SWATCHES.map((key) => {
              const theme = ACCENT_THEMES[key];
              const selected = userPreferences.accentTheme === key;
              return (
                <button
                  key={key}
                  onClick={() => updatePreferences({ accentTheme: key })}
                  className="relative flex flex-col items-center gap-1"
                  title={theme.label}
                >
                  <div
                    className={`w-8 h-8 rounded-full border-2 transition-all ${selected ? "ring-2 ring-dxc-midnight ring-offset-2" : "border-dxc-canvas"}`}
                    style={{ background: `linear-gradient(135deg, ${theme.primary} 50%, ${theme.secondary} 50%)` }}
                  >
                    {selected && (
                      <div className="w-full h-full flex items-center justify-center">
                        <Check size={14} className="text-dxc-white drop-shadow" />
                      </div>
                    )}
                  </div>
                  <span className="text-[10px] text-dxc-midnight/60">{theme.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Next */}
      <div className="flex justify-end pt-4">
        <button
          onClick={handleNext}
          disabled={!canProceed}
          className="px-8 py-3 rounded-lg font-semibold text-dxc-white bg-dxc-royal hover:bg-dxc-blue transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Suivant →
        </button>
      </div>
    </div>
  );
}
