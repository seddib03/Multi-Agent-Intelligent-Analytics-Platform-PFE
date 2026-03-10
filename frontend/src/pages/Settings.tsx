import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Bell, Moon, Globe, Shield, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAppStore } from "@/stores/appStore";
import { useDarkMode } from "@/hooks/useDarkMode";
import { useAuth } from "@/hooks/useAuth";
import { t } from "@/lib/i18n";
import BrandLogo from "@/components/BrandLogo";
import type { Language } from "@/types/app";
import { toast } from "sonner";

export default function Settings() {
  const navigate = useNavigate();
  const { userPreferences, updatePreferences } = useAppStore();
  const { usersGetMe, updateMyPreferences } = useAuth();
  const [notifications, setNotifications] = useState(true);
  const [saving, setSaving] = useState(false);
  useDarkMode();

  const lang = userPreferences.language;

  useEffect(() => {
    let cancelled = false;

    const loadPreferences = async () => {
      const { data } = await usersGetMe();
      if (!data?.preferences || cancelled) return;

      updatePreferences({
        darkMode: data.preferences.dark_mode ?? userPreferences.darkMode,
        chartStyle: (data.preferences.chart_style as typeof userPreferences.chartStyle) ?? userPreferences.chartStyle,
        density: (data.preferences.density as typeof userPreferences.density) ?? userPreferences.density,
        accentTheme: (data.preferences.accent_theme as typeof userPreferences.accentTheme) ?? userPreferences.accentTheme,
        dashboardLayout: (data.preferences.dashboard_layout as typeof userPreferences.dashboardLayout) ?? userPreferences.dashboardLayout,
        visibleKPIs: data.preferences.visible_kpis ?? userPreferences.visibleKPIs,
        primaryColor: data.preferences.primary_color ?? userPreferences.primaryColor,
        secondaryColor: data.preferences.secondary_color ?? userPreferences.secondaryColor,
      });
    };

    void loadPreferences();

    return () => {
      cancelled = true;
    };
    // Load once on page mount to hydrate local preferences from backend.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const { error } = await updateMyPreferences({
      dark_mode: userPreferences.darkMode,
      chart_style: userPreferences.chartStyle,
      density: userPreferences.density,
      accent_theme: userPreferences.accentTheme,
      primary_color: userPreferences.primaryColor,
      secondary_color: userPreferences.secondaryColor,
      dashboard_layout: userPreferences.dashboardLayout,
      visible_kpis: userPreferences.visibleKPIs,
    });
    setSaving(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    toast.success(t("saveSettings", lang));
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-dxc-midnight text-dxc-white px-6 py-3">
        <div className="max-w-2xl mx-auto flex flex-col items-center gap-2">
          <BrandLogo logoClassName="h-8" subtitleClassName="text-[14px] font-semibold" showSubtitle />
        </div>
      </header>

      <div className="max-w-2xl mx-auto py-6 px-6">
        <button
          onClick={() => navigate("/app")}
          className="mb-3 hover:text-dxc-peach transition-colors min-h-[44px] inline-flex items-center gap-2"
          aria-label={t("back", lang)}
        >
          <ArrowLeft size={20} />
          <span className="text-sm font-medium">Retour</span>
        </button>
        <h1 className="text-2xl font-bold text-foreground mb-8">{t("settingsTitle", lang)}</h1>

        <div className="space-y-6">
          {/* Notifications */}
          <div className="bg-card rounded-2xl shadow-sm p-6 border border-border">
            <div className="flex items-center gap-3 mb-4">
              <Bell size={20} className="text-primary" />
              <h2 className="font-semibold text-foreground">{t("notifications", lang)}</h2>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-foreground">{t("emailNotifications", lang)}</Label>
                <p className="text-xs text-muted-foreground">{t("receiveAlerts", lang)}</p>
              </div>
              <Switch checked={notifications} onCheckedChange={setNotifications} />
            </div>
          </div>

          {/* Apparence */}
          <div className="bg-card rounded-2xl shadow-sm p-6 border border-border">
            <div className="flex items-center gap-3 mb-4">
              <Moon size={20} className="text-primary" />
              <h2 className="font-semibold text-foreground">{t("appearance", lang)}</h2>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-foreground">{t("darkMode", lang)}</Label>
                <p className="text-xs text-muted-foreground">{t("enableDarkTheme", lang)}</p>
              </div>
              <Switch 
                checked={userPreferences.darkMode} 
                onCheckedChange={(checked) => updatePreferences({ darkMode: checked })} 
              />
            </div>
          </div>

          {/* Langue */}
          <div className="bg-card rounded-2xl shadow-sm p-6 border border-border">
            <div className="flex items-center gap-3 mb-4">
              <Globe size={20} className="text-primary" />
              <h2 className="font-semibold text-foreground">{t("languageLabel", lang)}</h2>
            </div>
            <Select 
              value={userPreferences.language} 
              onValueChange={(value: Language) => updatePreferences({ language: value })}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="fr">🇫🇷 Français</SelectItem>
                <SelectItem value="en">🇬🇧 English</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Sécurité */}
          <div className="bg-card rounded-2xl shadow-sm p-6 border border-border">
            <div className="flex items-center gap-3 mb-4">
              <Shield size={20} className="text-primary" />
              <h2 className="font-semibold text-foreground">{t("security", lang)}</h2>
            </div>
            <Button variant="outline" className="w-full">
              {t("changePassword", lang)}
            </Button>
          </div>

          <Button
            onClick={handleSave}
            disabled={saving}
            className="w-full"
          >
            <Save size={16} className="mr-2" />
            {saving ? t("saving", lang) : t("saveSettings", lang)}
          </Button>
        </div>
      </div>
    </div>
  );
}
