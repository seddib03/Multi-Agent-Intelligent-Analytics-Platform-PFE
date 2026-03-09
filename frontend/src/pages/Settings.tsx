import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Bell, Moon, Globe, Shield, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAppStore } from "@/stores/appStore";
import { useDarkMode } from "@/hooks/useDarkMode";
import { t } from "@/lib/i18n";
import type { Language } from "@/types/app";

export default function Settings() {
  const navigate = useNavigate();
  const { userPreferences, updatePreferences } = useAppStore();
  const [notifications, setNotifications] = useState(true);
  const [saving, setSaving] = useState(false);
  useDarkMode();

  const lang = userPreferences.language;

  const handleSave = async () => {
    setSaving(true);
    await new Promise((r) => setTimeout(r, 1000));
    setSaving(false);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-dxc-midnight text-dxc-white px-6 py-4 flex items-center gap-4">
        <button onClick={() => navigate("/app")} className="hover:text-dxc-peach transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center" aria-label={t("back", lang)}>
          <ArrowLeft size={20} />
        </button>
        <div>
          <span className="font-bold text-xl">DXC</span>
          <span className="text-dxc-peach text-xs ml-1">Insight Platform</span>
        </div>
      </header>

      <div className="max-w-2xl mx-auto py-10 px-6">
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
