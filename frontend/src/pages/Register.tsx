import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { UserPlus, Eye, EyeOff, Mail, Lock, User, ArrowRight, CheckCircle2 } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuth } from "@/hooks/useAuth";
import { t } from "@/lib/i18n";
import BrandLogo from "@/components/BrandLogo";

const Register = () => {
  const navigate = useNavigate();
  const { signUp } = useAuth();
  const lang = useAppStore((s) => s.userPreferences.language);
  const [fullName, setFullName] = useState("");
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
      options: { data: { full_name: fullName } },
    });
    setLoading(false);
    if (error) {
      toast.error(error.message);
    } else {
      toast.success(t("accountCreated", lang));
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
      <div className="hidden lg:flex lg:w-[48%] bg-dxc-midnight relative overflow-hidden flex-col justify-start items-center pt-20 pb-12 px-12">
        {/* Decorative blurs */}
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-dxc-melon/15 blur-[120px]" />
        <div className="absolute bottom-0 left-0 w-72 h-72 rounded-full bg-dxc-royal/15 blur-[100px]" />

        <div className="relative z-10 max-w-md w-full space-y-10">
          {/* Logo */}
          <div className="text-center">
            <div className="inline-flex">
              <BrandLogo logoClassName="h-9" subtitleClassName="text-[15px] font-semibold" className="mb-2" />
            </div>
            <p className="text-white/40 text-sm leading-relaxed">{t("registerBrandingSubtitle", lang)}</p>
          </div>

          {/* Benefits */}
          <div className="space-y-4">
            <p className="text-dxc-peach text-xs uppercase tracking-widest font-bold">{t("registerWhyJoin", lang)}</p>
            {benefits.map((key, i) => (
              <div key={i} className="flex items-center gap-3">
                <CheckCircle2 size={16} className="text-dxc-gold shrink-0" />
                <p className="text-white/70 text-sm">{t(key, lang)}</p>
              </div>
            ))}
          </div>

          {/* CTA to login */}
          <div className="pt-6 border-t border-white/10">
            <p className="text-white/50 text-sm mb-3">{t("alreadyAccount", lang)}</p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-dxc-peach/10 border border-dxc-peach/25 text-dxc-peach text-sm font-semibold hover:bg-dxc-peach/20 transition-all"
            >
              {t("login", lang)} <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        {/* Footer */}
        <p className="absolute bottom-6 left-12 text-white/20 text-xs">© 2025 DXC Technology</p>
      </div>

      {/* Form panel — RIGHT side */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-background">
        <div className="w-full max-w-[380px]">
          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-10">
            <div className="inline-flex">
              <BrandLogo logoClassName="h-8" subtitleClassName="text-[14px] font-semibold" />
            </div>
          </div>

          {/* Heading */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground mb-2">{t("registerTitle", lang)}</h1>
            <p className="text-muted-foreground text-sm">{t("registerSubtitle", lang)}</p>
            <Link to="/" className="mt-3 inline-flex text-sm font-medium text-primary hover:underline">
              Retour a l'accueil
            </Link>
          </div>

          {/* Form */}
          <form onSubmit={handleRegister} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="fullName" className="text-xs font-semibold text-foreground">{t("fullName", lang)}</Label>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input
                  id="fullName"
                  type="text"
                  placeholder={t("namePlaceholder", lang)}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="pl-10 h-11 bg-card border-border focus:border-primary rounded-lg"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-xs font-semibold text-foreground">{t("email", lang)}</Label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input
                  id="email"
                  type="email"
                  placeholder={t("emailPlaceholder", lang)}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="pl-10 h-11 bg-card border-border focus:border-primary rounded-lg"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-xs font-semibold text-foreground">{t("password", lang)}</Label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder={t("passwordPlaceholder", lang)}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="pl-10 pr-10 h-11 bg-card border-border focus:border-primary rounded-lg"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/40 hover:text-foreground transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
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
              className="w-full h-11 gap-2 bg-dxc-melon text-white hover:bg-dxc-red font-semibold text-sm rounded-lg mt-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <UserPlus size={16} />
              )}
              {loading ? t("creating", lang) : t("createAccountFree", lang)}
            </Button>
          </form>

          {/* Mobile switch */}
          <div className="mt-8 pt-6 border-t border-border lg:hidden">
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
