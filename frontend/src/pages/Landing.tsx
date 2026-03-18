import { Link } from "react-router-dom";
import {
  Upload,
  FileText,
  Cpu,
  BarChart2,
  Brain,
  Shield,
  Sliders,
  MessageSquare,
  Palette,
  Zap,
  TrendingUp,
  Truck,
  ShoppingBag,
  Settings,
  Building,
  ArrowRight,
} from "lucide-react";
import BrandLogo from "@/components/BrandLogo";
import { useAppStore } from "@/stores/appStore";
import { t } from "@/lib/i18n";

const heroBackgroundPath = "/images/hero-analytics.png";

const stepIcons = [Upload, FileText, Cpu, BarChart2];
const featureIcons = [Brain, Shield, Sliders, MessageSquare, Palette, Zap];
const sectorIcons = [TrendingUp, Truck, ShoppingBag, Settings, Building];

const stepKeys = [
  { title: "step1Title", desc: "step1Desc" },
  { title: "step2Title", desc: "step2Desc" },
  { title: "step3Title", desc: "step3Desc" },
  { title: "step4Title", desc: "step4Desc" },
] as const;

const featureKeys = [
  { title: "featAutoSector", desc: "featAutoSectorDesc" },
  { title: "featIsolation", desc: "featIsolationDesc" },
  { title: "featQuality", desc: "featQualityDesc" },
  { title: "featNLQ", desc: "featNLQDesc" },
  { title: "featDashboard", desc: "featDashboardDesc" },
  { title: "featFast", desc: "featFastDesc" },
] as const;

const sectorKeys = [
  { label: "sectorFinance", useCase: "sectorFinanceUse" },
  { label: "sectorTransport", useCase: "sectorTransportUse" },
  { label: "sectorRetail", useCase: "sectorRetailUse" },
  { label: "sectorManufacturing", useCase: "sectorManufacturingUse" },
  { label: "sectorPublic", useCase: "sectorPublicUse" },
] as const;

export default function Landing() {
  const lang = useAppStore((s) => s.userPreferences.language);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="fixed top-0 w-full bg-dxc-midnight z-50 transition-shadow" id="landing-header">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BrandLogo logoClassName="h-7" subtitleClassName="text-[13px]" />
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="border border-dxc-sky text-dxc-sky px-5 py-2 rounded-lg text-sm font-medium hover:bg-dxc-sky/10 transition-colors">
              {t("login", lang)}
            </Link>
            <Link to="/register" className="bg-dxc-melon text-dxc-white px-5 py-2 rounded-lg text-sm font-bold hover:opacity-90 transition-opacity">
              {t("getStartedFree", lang)}
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section
        className="relative pt-32 pb-20 px-6 bg-cover bg-center"
        style={{ backgroundImage: `url(${heroBackgroundPath})` }}
      >
        <div className="absolute inset-0 bg-dxc-midnight/70" />

        <div className="relative z-10 max-w-4xl mx-auto text-center">
          <div className="inline-block mb-8 px-4 py-1 rounded-full bg-dxc-royal/30 border border-dxc-royal/40 text-dxc-sky text-sm">
            {t("heroTag", lang)}
          </div>
          <h1 className="text-4xl sm:text-[56px] font-bold leading-tight text-dxc-white mb-6">
            {t("heroTitle1", lang)}
            <br />
            <span className="text-dxc-melon">{t("heroHighlight", lang)}</span>
          </h1>
          <p className="text-lg text-dxc-white/70 max-w-2xl mx-auto mb-10 leading-relaxed">
            {t("heroSubtitle", lang)}
          </p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <Link to="/register" className="bg-dxc-melon text-dxc-white px-8 py-4 rounded-[10px] text-base font-bold hover:opacity-90 transition-opacity inline-flex items-center gap-2">
               {t("startNow", lang)}
            </Link>
            <button className="border border-dxc-sky text-dxc-sky px-8 py-4 rounded-[10px] text-base font-medium hover:bg-dxc-sky/10 transition-colors inline-flex items-center gap-2">
              {t("watchDemo", lang)} <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

      </section>

      {/* How it works */}
      <section className="bg-dxc-canvas py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-dxc-midnight mb-16">{t("stepsTitle", lang)}</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative">
            {/* Connecting line */}
            <div className="hidden md:block absolute top-12 left-[12.5%] right-[12.5%] h-0.5 border-t-2 border-dashed border-dxc-sky/40" />
            {stepKeys.map((step, i) => {
              const Icon = stepIcons[i];
              return (
              <div key={i} className="relative bg-card rounded-xl border-t-4 border-t-dxc-melon shadow-sm p-6 text-center">
                <div className="w-10 h-10 rounded-full bg-dxc-royal text-dxc-white flex items-center justify-center text-lg font-bold mx-auto -mt-11 mb-4 relative z-10">
                  {i + 1}
                </div>
                <Icon className="h-8 w-8 text-dxc-royal mx-auto mb-3" />
                <h3 className="font-bold text-card-foreground mb-2">{t(step.title, lang)}</h3>
                <p className="text-sm text-muted-foreground">{t(step.desc, lang)}</p>
              </div>
            );
            })}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="bg-dxc-midnight py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-dxc-white mb-16">{t("featuresTitle", lang)}</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {featureKeys.map((feature, i) => {
              const Icon = featureIcons[i];
              return (
              <div key={i} className="glass-card rounded-xl p-6">
                <div className="w-12 h-12 rounded-full bg-dxc-melon/20 flex items-center justify-center mb-4">
                  <Icon className="h-6 w-6 text-dxc-melon" />
                </div>
                <h3 className="font-bold text-dxc-white mb-2">{t(feature.title, lang)}</h3>
                <p className="text-sm text-dxc-white/70">{t(feature.desc, lang)}</p>
              </div>
            );
            })}
          </div>
        </div>
      </section>

      {/* Sectors */}
      <section className="bg-dxc-canvas py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-dxc-midnight mb-16">{t("sectorsTitle", lang)}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {sectorKeys.map((sector, i) => {
              const Icon = sectorIcons[i];
              return (
              <div key={i} className="bg-card rounded-2xl shadow-sm p-6 text-center hover:border-t-[3px] hover:border-t-dxc-melon hover:scale-[1.02] transition-all cursor-default">
                <Icon className="h-8 w-8 text-dxc-royal mx-auto mb-3" />
                <p className="font-bold text-card-foreground text-sm mb-2">{t(sector.label, lang)}</p>
                <p className="text-xs text-muted-foreground italic">"{t(sector.useCase, lang)}"</p>
              </div>
            );
            })}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-dxc-midnight py-20 px-6 text-center">
        <h2 className="text-3xl sm:text-[40px] font-bold text-dxc-white mb-4">{t("ctaTitle", lang)}</h2>
        <p className="text-dxc-white/60 mb-10 text-lg">{t("ctaSubtitle", lang)}</p>
        <Link to="/register" className="inline-block bg-dxc-melon text-dxc-white px-12 py-5 rounded-[10px] text-lg font-bold hover:opacity-90 transition-opacity">
          {t("createAccountFree", lang)}
        </Link>
      </section>

      {/* Footer */}
      <footer className="bg-dxc-midnight border-t border-dxc-royal/20 py-6 px-6">
        <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <BrandLogo showSubtitle={false} logoClassName="h-5" />
            <span className="text-dxc-white/40 text-xs">© 2026 Intelligent Analytics Platform</span>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <a href="#" className="text-dxc-sky hover:underline">{t("privacy", lang)}</a>
            <span className="text-dxc-white/20">·</span>
            <a href="#" className="text-dxc-sky hover:underline">{t("terms", lang)}</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
