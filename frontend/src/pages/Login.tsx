import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { LogIn, Eye, EyeOff, Mail, Lock, ArrowRight, BarChart3, Shield, Zap } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuth } from "@/hooks/useAuth";
import { t } from "@/lib/i18n";
import BrandLogo from "@/components/BrandLogo";
import { getProjectSectorContext, getProjectStoredMessages, isProjectDashboardGenerated, listProjects, type Project } from "@/lib/projectsApi";

const SUPPORTED_SECTORS = ["finance", "transport", "retail", "manufacturing", "public"] as const;

function normalizeSector(value: string | null | undefined): (typeof SUPPORTED_SECTORS)[number] {
  if (value && (SUPPORTED_SECTORS as readonly string[]).includes(value)) {
    return value as (typeof SUPPORTED_SECTORS)[number];
  }
  return "public";
}

const Login = () => {
  const navigate = useNavigate();
  const { signInWithPassword } = useAuth();
  const lang = useAppStore((s) => s.userPreferences.language);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const { error } = await signInWithPassword({ email, password });
    if (error) {
      setLoading(false);
      toast.error(error.message);
    } else {
      toast.success(t("loginSuccess", lang));

      try {
        const projects = await listProjects();
        const state = useAppStore.getState();
        const byUpdatedAtDesc = [...projects].sort(
          (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        );

        const targetProject: Project | undefined =
          byUpdatedAtDesc.find((p) => p.id === state.currentProjectId) ?? byUpdatedAtDesc[0];

        if (targetProject) {
          const restoredMessages = getProjectStoredMessages(targetProject);
          useAppStore.setState((s) => ({
            currentProjectId: targetProject.id,
            // show dashboard first after login
            currentPhase: 2,
            onboardingStep: 4,
            onboarding: {
              ...s.onboarding,
              useCaseDescription: targetProject.use_case ?? s.onboarding.useCaseDescription,
              sectorContext: getProjectSectorContext(targetProject) ?? s.onboarding.sectorContext,
            },
            dataset: {
              ...s.dataset,
              detectedSector: normalizeSector(targetProject.detected_sector),
              businessRules: targetProject.business_rules ?? s.dataset.businessRules,
              dashboardGenerated: isProjectDashboardGenerated(targetProject),
            },
            messages: restoredMessages,
            pinnedInsights: restoredMessages.filter((m) => m.pinned),
          }));
        } else {
          useAppStore.setState((s) => ({
            currentProjectId: null,
            currentPhase: 1,
            onboardingStep: 1,
            onboarding: {
              ...s.onboarding,
              useCaseDescription: "",
              sectorContext: null,
            },
            dataset: {
              ...s.dataset,
              fileName: "",
              rowCount: 0,
              columnCount: 0,
              columns: [],
              qualityScore: 0,
              businessRules: "",
              detectedSector: "finance",
              dashboardGenerated: false,
              previewData: [],
            },
            messages: [],
            pinnedInsights: [],
          }));
        }
      } catch {
        // If project listing fails, fallback to regular app route.
      }

      setLoading(false);
      navigate("/app");
    }
  };

  const features = [
    { icon: <BarChart3 size={18} />, titleKey: "loginFeature1Title" as const, descKey: "loginFeature1Desc" as const },
    { icon: <Shield size={18} />, titleKey: "loginFeature2Title" as const, descKey: "loginFeature2Desc" as const },
    { icon: <Zap size={18} />, titleKey: "loginFeature3Title" as const, descKey: "loginFeature3Desc" as const },
  ];

  return (
    <div className="flex min-h-screen flex-row-reverse">
      {/* Branding panel — RIGHT side */}
      <div className="hidden lg:flex lg:w-[48%] bg-dxc-midnight relative overflow-hidden items-center px-12 py-10">
        {/* Decorative blurs */}
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-dxc-royal/20 blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-72 h-72 rounded-full bg-dxc-melon/10 blur-[100px]" />

        <div className="relative z-10 flex h-full w-full max-w-md flex-col">
          {/* Logo */}
          <div className="text-center pt-6">
            <div className="inline-flex">
              <BrandLogo logoClassName="h-11" subtitleClassName="text-[17px] font-semibold" className="mb-3" />
            </div>
            <p className="mx-auto max-w-sm text-base leading-relaxed text-white/60">{t("loginBrandingSubtitle", lang)}</p>
          </div>

          {/* Features */}
          <div className="my-auto space-y-5 px-1">
            {features.map((f, i) => (
              <div key={i} className="flex items-start gap-4 group">
                <div className="w-9 h-9 rounded-lg bg-dxc-royal/25 flex items-center justify-center text-dxc-peach shrink-0 group-hover:bg-dxc-royal/40 transition-colors">
                  {f.icon}
                </div>
                <div>
                  <p className="text-white font-semibold text-sm leading-tight">{t(f.titleKey, lang)}</p>
                  <p className="text-white/40 text-xs mt-1 leading-relaxed">{t(f.descKey, lang)}</p>
                </div>
              </div>
            ))}
          </div>

          {/* CTA to register */}
          <div className="border-t border-white/10 pt-6 text-center">
            <p className="mb-4 text-base text-white/65">{t("noAccount", lang)}</p>
            <div>
              <Link
                to="/register"
                className="inline-flex items-center gap-2 rounded-lg border border-dxc-peach/25 bg-dxc-peach/10 px-6 py-3 text-base font-semibold text-dxc-peach transition-all hover:bg-dxc-peach/20"
              >
                {t("createAnAccount", lang)} <ArrowRight size={15} />
              </Link>
            </div>
            <p className="mt-6 text-center text-xs text-white/30">© 2026 DXC Technology</p>
          </div>
        </div>
      </div>

      {/* Form panel — LEFT side */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-background">
        <div className="w-full max-w-[430px]">
          <div className="mb-10 text-center">
            <h1 className="text-3xl font-bold text-foreground mb-2">{t("loginTitle", lang)}</h1>
            <p className="text-base text-muted-foreground">{t("loginSubtitle", lang)}</p>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-semibold text-foreground">{t("email", lang)}</Label>
              <div className="relative">
                <Mail size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input
                  id="email"
                  type="email"
                  placeholder={t("emailPlaceholder", lang)}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-12 rounded-lg border-border bg-card pl-11 text-base focus:border-primary"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-semibold text-foreground">{t("password", lang)}</Label>
              <div className="relative">
                <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-12 rounded-lg border-border bg-card pl-11 pr-11 text-base focus:border-primary"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground/40 transition-colors hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="mt-2 h-12 w-full gap-2 rounded-lg bg-primary text-base font-semibold text-primary-foreground hover:bg-primary/90"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
              ) : (
                <LogIn size={16} />
              )}
              {loading ? t("loggingIn", lang) : t("login", lang)}
            </Button>
          </form>

          <div className="mt-10 border-t border-border pt-6 text-center">
            <p className="text-center text-sm text-muted-foreground">
              {t("noAccount", lang)}{" "}
              <Link to="/register" className="font-semibold text-primary hover:underline inline-flex items-center gap-1">
                {t("createAnAccount", lang)} <ArrowRight size={14} />
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
