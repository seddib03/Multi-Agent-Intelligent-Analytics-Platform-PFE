import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, User, Mail, Building2, Camera, Save } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useAppStore } from "@/stores/appStore";
import { useDarkMode } from "@/hooks/useDarkMode";
import { t } from "@/lib/i18n";
import BrandLogo from "@/components/BrandLogo";
import { toast } from "sonner";

export default function Profile() {
  const navigate = useNavigate();
  const { user, updateProfile, usersDeleteMe } = useAuth();
  const [fullName, setFullName] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const lang = useAppStore((s) => s.userPreferences.language);
  useDarkMode();

  useEffect(() => {
    if (!user) return;
    const fullNameFromUser = user.user_metadata?.full_name || `${user.first_name || ""} ${user.last_name || ""}`.trim();
    setFullName(fullNameFromUser);
  }, [user]);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    const { error } = await updateProfile({ userId: user.id, fullName });
    setSaving(false);
    if (error) toast.error(error.message);
    else toast.success(t("profileSaved", lang));
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    const { error } = await usersDeleteMe();
    setDeleting(false);

    if (error) {
      toast.error(error.message);
      return;
    }

    toast.success(t("accountDeleted", lang));
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 h-16 bg-dxc-midnight px-4 text-white md:px-6">
        <div className="mx-auto flex h-full max-w-2xl items-center justify-center">
          <BrandLogo logoClassName="h-7" subtitleClassName="text-[13px] font-semibold" showSubtitle />
        </div>
      </header>

      <div className="max-w-2xl mx-auto py-6 px-4 md:px-6">
        <button
          onClick={() => navigate("/app")}
          className="mb-3 hover:text-dxc-peach transition-colors min-h-[44px] inline-flex items-center gap-2"
          aria-label={t("back", lang)}
        >
          <ArrowLeft size={20} />
          <span className="text-sm font-medium">Retour</span>
        </button>
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
              <Label htmlFor="company" className="text-foreground">{t("company", lang)}</Label>
              <div className="flex items-center gap-3 px-4 py-3 bg-muted rounded-lg">
                <Building2 size={16} className="text-primary" />
                <span className="text-foreground">{user?.company_name || "—"}</span>
              </div>
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
          <div className="space-y-3">
            <Button onClick={handleSave} disabled={saving || deleting} className="w-full">
              <Save size={16} className="mr-2" />
              {saving ? t("saving", lang) : t("saveChanges", lang)}
            </Button>

            <div className="rounded-xl border border-destructive/45 bg-destructive/10 p-4">
              <p className="text-sm font-bold text-destructive">{t("dangerZone", lang)}</p>
              <p className="mt-1 text-sm leading-relaxed text-foreground/85">{t("dangerZoneDesc", lang)}</p>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    type="button"
                    variant="destructive"
                    disabled={deleting || saving}
                    className="mt-3 w-full"
                  >
                    {deleting ? t("deletingAccount", lang) : t("deleteMyAccount", lang)}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t("deleteAccountTitle", lang)}</AlertDialogTitle>
                    <AlertDialogDescription>{t("deleteAccountConfirm", lang)}</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t("cancel", lang)}</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDeleteAccount}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      {t("confirm", lang)}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
