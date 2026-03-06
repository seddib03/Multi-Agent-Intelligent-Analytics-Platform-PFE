import { Link } from 'react-router-dom';
import { Upload, FileText, Cpu, BarChart2, Brain, Shield, Sliders, MessageSquare, Palette, Zap, TrendingUp, Truck, ShoppingBag, Settings, Building, ArrowRight } from 'lucide-react';
import BrandLogo from '@/components/BrandLogo';

const sectors = [' Finance', ' Transport', ' Retail', ' Manufacturing', ' Public'];

const steps = [
  { icon: Upload, title: 'Uploadez vos données', desc: 'CSV, Excel ou JSON — jusqu\'à 100 MB' },
  { icon: FileText, title: 'Décrivez votre besoin', desc: 'En langage naturel, sans jargon technique' },
  { icon: Cpu, title: 'Le système analyse', desc: 'Détection automatique du secteur + entraînement ML' },
  { icon: BarChart2, title: 'Obtenez vos insights', desc: 'Prédictions, explications et recommandations' },
];

const features = [
  { icon: Brain, title: 'Détection automatique du secteur', desc: 'Votre secteur est identifié sans configuration manuelle' },
  { icon: Shield, title: 'Données isolées par entreprise', desc: 'Chaque organisation a son espace sécurisé' },
  { icon: Sliders, title: 'Qualité des données intégrée', desc: 'Détection et correction des problèmes avant l\'analyse' },
  { icon: MessageSquare, title: 'Questions en langage naturel', desc: 'Interrogez vos données comme vous parleriez à un expert' },
  { icon: Palette, title: 'Dashboard 100% personnalisable', desc: 'Couleurs, graphiques, densité — tout s\'adapte à vous' },
  { icon: Zap, title: 'Résultats en quelques minutes', desc: 'Pipeline AutoML automatisé de bout en bout' },
];

const sectorCards = [
  { icon: TrendingUp, label: ' Finance', useCase: 'Prédiction de churn client' },
  { icon: Truck, label: ' Transport', useCase: 'Prévision des retards' },
  { icon: ShoppingBag, label: ' Retail', useCase: 'Recommandations produits' },
  { icon: Settings, label: ' Manufacturing', useCase: 'Maintenance prédictive' },
  { icon: Building, label: ' Public', useCase: 'Optimisation des délais' },
];

const heroBackgroundPath = '/images/back.png';

export default function Landing() {
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
              Se connecter
            </Link>
            <Link to="/register" className="bg-dxc-melon text-dxc-white px-5 py-2 rounded-lg text-sm font-bold hover:opacity-90 transition-opacity">
              Commencer gratuitement
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
            ✦ Plateforme IA Multi-Agents
          </div>
          <h1 className="text-4xl sm:text-[56px] font-bold leading-tight text-dxc-white mb-6">
            Transformez vos données en<br />
            décisions <span className="text-dxc-melon">intelligentes</span>
          </h1>
          <p className="text-lg text-dxc-white/70 max-w-2xl mx-auto mb-10 leading-relaxed">
            Uploadez vos données, décrivez votre besoin, et obtenez des prédictions, insights et explications métier en quelques minutes — sans compétences techniques.
          </p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <Link to="/register" className="bg-dxc-melon text-dxc-white px-8 py-4 rounded-[10px] text-base font-bold hover:opacity-90 transition-opacity inline-flex items-center gap-2">
               Démarrer maintenant
            </Link>
            <button className="border border-dxc-sky text-dxc-sky px-8 py-4 rounded-[10px] text-base font-medium hover:bg-dxc-sky/10 transition-colors inline-flex items-center gap-2">
              Voir une démo <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Scrolling sectors */}
        <div className="relative z-10 mt-16 overflow-hidden">
          <div className="bg-dxc-royal/15 py-3">
            <div className="flex animate-scroll-infinite whitespace-nowrap">
              {[...sectors, ...sectors, ...sectors, ...sectors].map((s, i) => (
                <span key={i} className="text-dxc-peach text-[13px] mx-6">{s}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="bg-dxc-canvas py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-dxc-midnight mb-16">En 4 étapes simples</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative">
            {/* Connecting line */}
            <div className="hidden md:block absolute top-12 left-[12.5%] right-[12.5%] h-0.5 border-t-2 border-dashed border-dxc-sky/40" />
            {steps.map((step, i) => (
              <div key={i} className="relative bg-card rounded-xl border-t-4 border-t-dxc-melon shadow-sm p-6 text-center">
                <div className="w-10 h-10 rounded-full bg-dxc-royal text-dxc-white flex items-center justify-center text-lg font-bold mx-auto -mt-11 mb-4 relative z-10">
                  {i + 1}
                </div>
                <step.icon className="h-8 w-8 text-dxc-royal mx-auto mb-3" />
                <h3 className="font-bold text-card-foreground mb-2">{step.title}</h3>
                <p className="text-sm text-muted-foreground">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="bg-dxc-midnight py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-dxc-white mb-16">Tout ce dont vous avez besoin</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <div key={i} className="glass-card rounded-xl p-6">
                <div className="w-12 h-12 rounded-full bg-dxc-melon/20 flex items-center justify-center mb-4">
                  <f.icon className="h-6 w-6 text-dxc-melon" />
                </div>
                <h3 className="font-bold text-dxc-white mb-2">{f.title}</h3>
                <p className="text-sm text-dxc-white/70">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Sectors */}
      <section className="bg-dxc-canvas py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-dxc-midnight mb-16">Une plateforme, tous vos secteurs</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {sectorCards.map((s, i) => (
              <div key={i} className="bg-card rounded-2xl shadow-sm p-6 text-center hover:border-t-[3px] hover:border-t-dxc-melon hover:scale-[1.02] transition-all cursor-default">
                <s.icon className="h-8 w-8 text-dxc-royal mx-auto mb-3" />
                <p className="font-bold text-card-foreground text-sm mb-2">{s.label}</p>
                <p className="text-xs text-muted-foreground italic">"{s.useCase}"</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-dxc-midnight py-20 px-6 text-center">
        <h2 className="text-3xl sm:text-[40px] font-bold text-dxc-white mb-4">Prêt à transformer vos données ?</h2>
        <p className="text-dxc-white/60 mb-10 text-lg">Rejoignez les équipes qui prennent de meilleures décisions grâce à l'IA</p>
        <Link to="/register" className="inline-block bg-dxc-melon text-dxc-white px-12 py-5 rounded-[10px] text-lg font-bold hover:opacity-90 transition-opacity">
          Créer mon compte gratuitement
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
            <a href="#" className="text-dxc-sky hover:underline">Politique de confidentialité</a>
            <span className="text-dxc-white/20">·</span>
            <a href="#" className="text-dxc-sky hover:underline">Conditions d'utilisation</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
