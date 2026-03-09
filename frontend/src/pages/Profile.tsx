import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, User, Mail, Camera, Save } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAppStore } from "@/stores/appStore";
import { useDarkMode } from "@/hooks/useDarkMode";
import { t } from "@/lib/i18n";
import { toast } from "sonner";

export default function Profile() {
  const navigate = useNavigate();
  const { user, updateProfile } = useAuth();
  const [fullName, setFullName] = useState("");
  const [saving, setSaving] = useState(false);
  const lang = useAppStore((s) => s.userPreferences.language);
  useDarkMode();

  useEffect(() => {
    if (!user) return;
    setFullName(user.user_metadata?.full_name || "");
  }, [user]);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    const { error } = await updateProfile({ userId: user.id, fullName });
    setSaving(false);
    if (error) toast.error(error.message);
    else toast.success(t("profileSaved", lang));
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-dxc-midnight text-white px-4 md:px-6 py-4 flex items-center gap-4">
        <button onClick={() => navigate("/app")} className="hover:text-dxc-peach transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center" aria-label={t("back", lang)}><ArrowLeft size={20} /></button>
        <div>
          <span className="font-bold text-xl">DXC</span>
          <span className="text-dxc-peach text-xs ml-1">{t("insightPlatform", lang)}</span>
        </div>
      </header>

      <div className="max-w-2xl mx-auto py-10 px-4 md:px-6">
        <h1 className="text-2xl font-bold text-foreground mb-8">{t("myProfile", lang)}</h1>
        <div className="bg-card rounded-2xl shadow-sm p-6 md:p-8 space-y-8 border border-border">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center relative">
              <User size={32} className="text-primary" />
              <button className="absolute -bottom-1 -right-1 w-8 h-8 bg-accent text-accent-foreground rounded-full flex items-center justify-center hover:opacity-80 transition-opacity" aria-label={t("changeAvatar", lang)}><Camera size={14} /></button>
            </div>
            <div>
              <p className="text-foreground font-semibold">{user?.email || t("user", lang)}</p>
              <p className="text-muted-foreground text-sm">{t("memberSince", lang)}</p>
            </div>
          </div>
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="fullName" className="text-foreground">{t("fullName", lang)}</Label>
              <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder={t("enterName", lang)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-foreground">{t("email", lang)}</Label>
              <div className="flex items-center gap-3 px-4 py-3 bg-muted rounded-lg">
                <Mail size={16} className="text-primary" />
                <span className="text-foreground">{user?.email || "—"}</span>
              </div>
              <p className="text-xs text-muted-foreground">{t("emailNotEditable", lang)}</p>
            </div>
          </div>
          <Button onClick={handleSave} disabled={saving} className="w-full">
            <Save size={16} className="mr-2" />
            {saving ? t("saving", lang) : t("saveChanges", lang)}
          </Button>
        </div>
      </div>
    </div>
  );
}
