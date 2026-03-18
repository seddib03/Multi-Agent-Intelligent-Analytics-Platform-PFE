import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { UserPlus, Eye, EyeOff, Mail, Lock, User, Building2, ArrowRight, CheckCircle2 } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuth } from "@/hooks/useAuth";
import { t } from "@/lib/i18n";
import BrandLogo from "@/components/BrandLogo";

const Register = () => {
  const navigate = useNavigate();
  const { signUp } = useAuth();
  const lang = useAppStore((s) => s.userPreferences.language);
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState((import.meta.env.VITE_DEFAULT_COMPANY_NAME as string | undefined) || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const passwordStrength = password.length === 0 ? 0 : password.length < 6 ? 1 : password.length < 10 ? 2 : 3;
  const strengthLabels = { 0: "", 1: t("passwordWeak", lang), 2: t("passwordMedium", lang), 3: t("passwordStrong", lang) };
  const strengthColors = { 0: "", 1: "bg-destructive", 2: "bg-dxc-gold", 3: "bg-green-500" };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) {
      toast.error(t("passwordTooShort", lang));
      return;
    }
    setLoading(true);
    const { error } = await signUp({
      email,
      password,
      options: { data: { full_name: fullName, company_name: companyName } },
    });
    setLoading(false);
    if (error) {
      toast.error(error.message);
    } else {
      toast.success(t("accountCreated", lang));
      // new user lands on dashboard immediately
      useAppStore.setState({ currentPhase: 2 });
      navigate("/app");
    }
  };

  const benefits = [
    "registerBenefit1" as const,
    "registerBenefit2" as const,
    "registerBenefit3" as const,
    "registerBenefit4" as const,
  ];

  return (
    <div className="flex min-h-screen">
      {/* Branding panel — LEFT side */}
      <div className="hidden lg:flex lg:w-[48%] bg-dxc-midnight relative overflow-hidden items-center px-12 py-10">
        {/* Decorative blurs */}
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-dxc-melon/15 blur-[120px]" />
        <div className="absolute bottom-0 left-0 w-72 h-72 rounded-full bg-dxc-royal/15 blur-[100px]" />

        <div className="relative z-10 flex h-full w-full max-w-md flex-col">
          {/* Logo */}
          <div className="text-center pt-6">
            <div className="inline-flex">
              <BrandLogo logoClassName="h-11" subtitleClassName="text-[17px] font-semibold" className="mb-3" />
            </div>
            <p className="mx-auto max-w-sm text-base leading-relaxed text-white/60">{t("registerBrandingSubtitle", lang)}</p>
          </div>

          {/* Benefits */}
          <div className="my-auto space-y-5 px-1">
            <p className="text-dxc-peach text-xs uppercase tracking-widest font-bold">{t("registerWhyJoin", lang)}</p>
            {benefits.map((key, i) => (
              <div key={i} className="flex items-center gap-3">
                <CheckCircle2 size={16} className="text-dxc-gold shrink-0" />
                <p className="text-white/70 text-sm leading-relaxed">{t(key, lang)}</p>
              </div>
            ))}
          </div>

          {/* CTA to login */}
          <div className="border-t border-white/10 pt-6 text-center">
            <p className="mb-4 text-base text-white/65">{t("alreadyAccount", lang)}</p>
            <div>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 rounded-lg border border-dxc-peach/25 bg-dxc-peach/10 px-6 py-3 text-base font-semibold text-dxc-peach transition-all hover:bg-dxc-peach/20"
              >
                {t("login", lang)} <ArrowRight size={15} />
              </Link>
            </div>
            <p className="mt-6 text-center text-xs text-white/30">© 2026 DXC Technology</p>
          </div>
        </div>
      </div>

      {/* Form panel — RIGHT side */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-background">
        <div className="w-full max-w-[430px]">
          <div className="mb-10 text-center">
            <h1 className="text-3xl font-bold text-foreground mb-2">{t("registerTitle", lang)}</h1>
            <p className="text-base text-muted-foreground">{t("registerSubtitle", lang)}</p>
          </div>

          {/* Form */}
          <form onSubmit={handleRegister} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="fullName" className="text-sm font-semibold text-foreground">{t("fullName", lang)}</Label>
              <div className="relative">
                <User size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input
                  id="fullName"
                  type="text"
                  placeholder={t("namePlaceholder", lang)}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="h-12 rounded-lg border-border bg-card pl-11 text-base focus:border-primary"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="companyName" className="text-sm font-semibold text-foreground">{t("company", lang)}</Label>
              <div className="relative">
                <Building2 size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input
                  id="companyName"
                  type="text"
                  placeholder={t("companyPlaceholder", lang)}
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  required
                  className="h-12 rounded-lg border-border bg-card pl-11 text-base focus:border-primary"
                />
              </div>
            </div>

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
                  placeholder={t("passwordPlaceholder", lang)}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
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
              {password.length > 0 && (
                <div className="space-y-1 pt-1">
                  <div className="flex gap-1">
                    {[1, 2, 3].map((level) => (
                      <div
                        key={level}
                        className={`h-1 flex-1 rounded-full transition-colors ${
                          passwordStrength >= level ? strengthColors[passwordStrength as keyof typeof strengthColors] : "bg-border"
                        }`}
                      />
                    ))}
                  </div>
                  <p className={`text-xs ${passwordStrength <= 1 ? "text-destructive" : passwordStrength === 2 ? "text-dxc-gold" : "text-green-600"}`}>
                    {strengthLabels[passwordStrength as keyof typeof strengthLabels]}
                  </p>
                </div>
              )}
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="mt-2 h-12 w-full gap-2 rounded-lg bg-dxc-melon text-base font-semibold text-white hover:bg-dxc-red"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <UserPlus size={16} />
              )}
              {loading ? t("creating", lang) : t("createAccountFree", lang)}
            </Button>
          </form>

          <div className="mt-10 border-t border-border pt-6 text-center">
            <p className="text-center text-sm text-muted-foreground">
              {t("alreadyAccount", lang)}{" "}
              <Link to="/login" className="font-semibold text-primary hover:underline inline-flex items-center gap-1">
                {t("login", lang)} <ArrowRight size={14} />
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;
