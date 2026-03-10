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
    setLoading(false);
    if (error) {
      toast.error(error.message);
    } else {
      toast.success(t("loginSuccess", lang));
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
      <div className="hidden lg:flex lg:w-[48%] bg-dxc-midnight relative overflow-hidden flex-col justify-start items-center pt-20 pb-12 px-12">
        {/* Decorative blurs */}
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-dxc-royal/20 blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-72 h-72 rounded-full bg-dxc-melon/10 blur-[100px]" />

        <div className="relative z-10 max-w-md w-full space-y-10">
          {/* Logo */}
          <div className="text-center">
            <div className="inline-flex">
              <BrandLogo logoClassName="h-9" subtitleClassName="text-[15px] font-semibold" className="mb-2" />
            </div>
            <p className="text-white/40 text-sm leading-relaxed">{t("loginBrandingSubtitle", lang)}</p>
          </div>

          {/* Features */}
          <div className="space-y-5">
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
          <div className="pt-6 border-t border-white/10">
            <p className="text-white/50 text-sm mb-3">{t("noAccount", lang)}</p>
            <Link
              to="/register"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-dxc-peach/10 border border-dxc-peach/25 text-dxc-peach text-sm font-semibold hover:bg-dxc-peach/20 transition-all"
            >
              {t("createAnAccount", lang)} <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        {/* Footer */}
        <p className="absolute bottom-6 left-12 text-white/20 text-xs">© 2025 DXC Technology</p>
      </div>

      {/* Form panel — LEFT side */}
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
            <h1 className="text-2xl font-bold text-foreground mb-2">{t("loginTitle", lang)}</h1>
            <p className="text-muted-foreground text-sm">{t("loginSubtitle", lang)}</p>
            <Link to="/" className="mt-3 inline-flex text-sm font-medium text-primary hover:underline">
              Retour a l'accueil
            </Link>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-5">
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
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
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
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 gap-2 bg-primary text-primary-foreground hover:bg-primary/90 font-semibold text-sm rounded-lg mt-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
              ) : (
                <LogIn size={16} />
              )}
              {loading ? t("loggingIn", lang) : t("login", lang)}
            </Button>
          </form>

          {/* Mobile switch */}
          <div className="mt-8 pt-6 border-t border-border lg:hidden">
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
