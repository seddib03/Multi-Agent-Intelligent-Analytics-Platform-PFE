import { useEffect, useRef, useState } from "react";
import { useAppStore } from "@/stores/appStore";
import type { ChartStyle, AccentTheme, Density } from "@/types/app";
import { ACCENT_THEMES } from "@/types/app";
import { Check, Loader2 } from "lucide-react";
import { t } from "@/lib/i18n";
import { ChartPreviews } from "./usecase/ChartPreviews";
import type { Language } from "@/lib/i18n";
import { createProject, updateProject } from "@/lib/projectsApi";
import { detectSector } from "@/lib/sectorDetectionApi";

function getChartStyles(lang: Language): { key: ChartStyle; icon: string; label: string }[] {
  return [
    { key: "bar", icon: "📊", label: t("bars", lang) },
    { key: "line", icon: "📈", label: t("lines", lang) },
    { key: "pie", icon: "🍩", label: t("circular", lang) },
    { key: "area", icon: "📉", label: t("areas", lang) },
    { key: "heatmap", icon: "🔥", label: t("heatmap", lang) },
  ];
}

const ACCENT_SWATCHES: AccentTheme[] = ["royal-melon", "blue-gold", "midnight-peach", "melon-royal", "gold-blue", "sky-midnight"];

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function getPreferencesSignature(prefs: ReturnType<typeof useAppStore.getState>["userPreferences"]): string {
  return JSON.stringify({
    darkMode: prefs.darkMode,
    chartStyle: prefs.chartStyle,
    density: prefs.density,
    accentTheme: prefs.accentTheme,
    dashboardLayout: prefs.dashboardLayout,
    visibleKPIs: [...prefs.visibleKPIs].sort(),
    language: prefs.language,
  });
}

const SUPPORTED_SECTORS = ["finance", "transport", "retail", "manufacturing", "public"] as const;
type SupportedSector = typeof SUPPORTED_SECTORS[number];

export function StepUseCase() {
  const { currentProjectId, onboarding, updateOnboarding, updateDataset, userPreferences, updatePreferences, setOnboardingStep } = useAppStore();
  const lang = userPreferences.language;
  const [desc, setDesc] = useState(onboarding.useCaseDescription);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const initialSnapshotRef = useRef<{ desc: string; preferencesSig: string } | null>(null);

  if (!initialSnapshotRef.current) {
    initialSnapshotRef.current = {
      desc: onboarding.useCaseDescription.trim(),
      preferencesSig: getPreferencesSignature(userPreferences),
    };
  }

  useEffect(() => {
    setDesc(onboarding.useCaseDescription);
  }, [onboarding.useCaseDescription]);

  const CHART_STYLES = getChartStyles(lang);

  const descTooShort = touched && desc.trim().length > 0 && desc.trim().length <= 10;
  const canProceed = desc.trim().length > 10;

  const handleNext = async () => {
    if (!canProceed || saving) return;

    const currentDesc = desc.trim();
    const hasChanges = Boolean(
      initialSnapshotRef.current &&
      (
        initialSnapshotRef.current.desc !== currentDesc ||
        initialSnapshotRef.current.preferencesSig !== getPreferencesSignature(userPreferences)
      )
    );

    const canUpdateExisting = Boolean(currentProjectId && isUuid(currentProjectId));

    if (canUpdateExisting && !hasChanges) {
      updateOnboarding({ useCaseDescription: desc });
      setOnboardingStep(2);
      return;
    }

    setTouched(true);
    setApiError(null);
    setSaving(true);

    try {
      const projectPayload = {
        name: desc.trim().slice(0, 60) || "Sans titre",
        use_case: desc.trim(),
        description: desc.trim(),
        visual_preferences: {
          darkMode: userPreferences.darkMode,
          chartStyle: userPreferences.chartStyle,
          density: userPreferences.density,
          accentTheme: userPreferences.accentTheme,
          dashboardLayout: userPreferences.dashboardLayout,
          visibleKPIs: userPreferences.visibleKPIs,
          language: userPreferences.language,
        },
      };

      const project = canUpdateExisting
        ? await updateProject(currentProjectId as string, projectPayload)
        : await createProject(projectPayload);

      // ── Détection de secteur — optionnelle, fallback silencieux ──────────
      let normalizedSector: SupportedSector = "finance";
      try {
        const sectorCtx = await detectSector(desc.trim());
        updateOnboarding({ useCaseDescription: desc, sectorContext: sectorCtx });
        normalizedSector = (SUPPORTED_SECTORS.includes(sectorCtx.sector as SupportedSector)
          ? sectorCtx.sector
          : "finance") as SupportedSector;
      } catch {
        // Service de détection indisponible → on continue avec le secteur par défaut
        console.warn("Sector detection service unavailable, using default sector.");
        updateOnboarding({ useCaseDescription: desc });
      }

      updateDataset({ detectedSector: normalizedSector });
      useAppStore.setState({ currentProjectId: project.id });
      setOnboardingStep(2);

    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Erreur lors de la création du projet");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 animate-fade-in">
      {/* Section A — Business Need */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-primary">{t("businessNeed", lang)}</h2>
        <textarea
          value={desc}
          onChange={(e) => { setDesc(e.target.value); setTouched(true); }}
          onBlur={() => setTouched(true)}
          rows={6}
          className={`w-full rounded-lg border-2 bg-card p-4 text-foreground placeholder:text-foreground/30 focus:border-primary focus:outline-none transition-colors resize-none ${descTooShort ? "border-destructive" : "border-border"}`}
          placeholder={t("useCasePlaceholder", lang)}
        />
        {descTooShort && (
          <p className="text-xs text-destructive font-medium">{t("useCaseTooShort", lang)}</p>
        )}
        <p className="text-xs italic text-muted-foreground">{t("sectorAutoDetect", lang)}</p>
      </div>

      <div className="border-t-2 border-accent/30" />

      {/* Section B — Preferences */}
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-primary">{t("customizeWorkspace", lang)}</h2>

        {/* Mode */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">{t("displayMode", lang)}</label>
          <div className="flex rounded-full overflow-hidden border border-border w-fit">
            <button
              onClick={() => updatePreferences({ darkMode: false })}
              className={`px-5 py-2 text-sm font-medium transition-all ${!userPreferences.darkMode ? "bg-foreground text-background" : "bg-muted text-muted-foreground"}`}
            >
              ☀️ {t("lightMode", lang)}
            </button>
            <button
              onClick={() => updatePreferences({ darkMode: true })}
              className={`px-5 py-2 text-sm font-medium transition-all ${userPreferences.darkMode ? "bg-foreground text-background" : "bg-muted text-muted-foreground"}`}
            >
              🌙 {t("darkModeLabel", lang)}
            </button>
          </div>
        </div>

        {/* Chart style */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">{t("preferredChartStyle", lang)}</label>
          <div className="flex gap-3 flex-wrap">
            {CHART_STYLES.map(({ key, icon, label }) => {
              const Preview = ChartPreviews[key];
              const selected = userPreferences.chartStyle === key;
              return (
                <button
                  key={key}
                  onClick={() => updatePreferences({ chartStyle: key })}
                  className={`w-[140px] sm:w-[160px] h-[100px] rounded-xl border-2 flex flex-col items-center justify-center gap-1 transition-all relative ${selected ? "border-dxc-melon bg-dxc-melon/10" : "border-border bg-card hover:border-primary/30"}`}
                >
                  {selected && (
                    <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-dxc-melon flex items-center justify-center">
                      <Check size={12} className="text-dxc-white" />
                    </div>
                  )}
                  <Preview />
                  <span className="text-xs font-medium text-foreground">{icon} {label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Density */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">{t("infoDensity", lang)}</label>
          <div className="space-y-3">
            {(["simplified", "standard", "expert"] as Density[]).map((d) => {
              const labels: Record<Density, { titleKey: "simplifiedTitle" | "standardTitle" | "expertTitle"; descKey: "simplifiedDesc" | "standardDesc" | "expertDesc" }> = {
                simplified: { titleKey: "simplifiedTitle", descKey: "simplifiedDesc" },
                standard: { titleKey: "standardTitle", descKey: "standardDesc" },
                expert: { titleKey: "expertTitle", descKey: "expertDesc" },
              };
              return (
                <button
                  key={d}
                  onClick={() => updatePreferences({ density: d })}
                  className={`w-full text-left px-4 py-3 rounded-lg border-2 transition-all ${userPreferences.density === d ? "border-dxc-melon bg-dxc-melon/10" : "border-border bg-card hover:border-primary/30"}`}
                >
                  <span className="font-semibold text-sm text-foreground">{t(labels[d].titleKey, lang)}</span>
                  <span className="text-xs text-muted-foreground ml-2">{t(labels[d].descKey, lang)}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Accent */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">{t("dashboardAccent", lang)}</label>
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
                    className={`w-8 h-8 rounded-full border-2 transition-all ${selected ? "ring-2 ring-foreground ring-offset-2 ring-offset-background" : "border-border"}`}
                    style={{ background: `linear-gradient(135deg, ${theme.primary} 50%, ${theme.secondary} 50%)` }}
                  >
                    {selected && (
                      <div className="w-full h-full flex items-center justify-center">
                        <Check size={14} className="text-dxc-white drop-shadow" />
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">{theme.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Error */}
      {apiError && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {apiError}
        </div>
      )}

      {/* Next */}
      <div className="flex justify-end pt-4">
        <button
          onClick={handleNext}
          disabled={!canProceed || saving}
          className="px-8 py-3 rounded-lg font-semibold text-primary-foreground bg-primary hover:opacity-90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {saving && <Loader2 size={16} className="animate-spin" />}
          {saving ? "Création..." : `${t("next", lang)} →`}
        </button>
      </div>
    </div>
  );
}