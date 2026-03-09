import { useState } from "react";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS, SECTOR_KPIS } from "@/lib/mockData";
import { ACCENT_THEMES, DXC_CHART_COLORS } from "@/types/app";
import type { AccentTheme, ChartStyle, Density, Language } from "@/types/app";
import { RefreshCw, Download, Settings, X, ArrowUp, ArrowDown, MessageSquare, Check, Globe } from "lucide-react";
import { AccountMenu } from "@/components/ui/AccountMenu";
import { useDarkMode } from "@/hooks/useDarkMode";
import { t } from "@/lib/i18n";
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const ACCENT_SWATCHES: AccentTheme[] = ["royal-melon", "blue-gold", "midnight-peach", "melon-royal", "gold-blue", "sky-midnight"];

function getChartStyles(lang: Language): { key: ChartStyle; label: string }[] {
  return [
    { key: "bar", label: `📊 ${t("bars", lang)}` },
    { key: "line", label: `📈 ${t("lines", lang)}` },
    { key: "pie", label: `🍩 ${t("circular", lang)}` },
    { key: "area", label: `📉 ${t("areas", lang)}` },
    { key: "heatmap", label: `🔥 ${t("heatmap", lang)}` },
  ];
}

function Sparkline({ color }: { color: string }) {
  const data = Array.from({ length: 7 }, () => ({ v: Math.random() * 40 + 30 }));
  return (
    <ResponsiveContainer width="100%" height={40}>
      <AreaChart data={data}><Area type="monotone" dataKey="v" stroke={color} fill={color} fillOpacity={0.15} strokeWidth={1.5} dot={false} /></AreaChart>
    </ResponsiveContainer>
  );
}

function DashboardChart({ chartStyle, primaryColor, lang }: { chartStyle: ChartStyle; primaryColor: string; lang: Language }) {
  const featureImportance = useAppStore((s) => s.modelResults.featureImportance).slice(0, 6);
  const timeData = Array.from({ length: 8 }, (_, i) => ({ name: `S${i + 1}`, [t("current", lang)]: Math.round(Math.random() * 25 + 65), [t("predicted", lang)]: Math.round(Math.random() * 25 + 60) }));

  const renderChart = (data: Record<string, unknown>[], keys: string[], title: string) => {
    const style = chartStyle === "heatmap" ? "bar" : chartStyle;
    return (
      <div className="bg-card rounded-xl p-4 border border-border">
        <h4 className="text-xs font-semibold mb-3" style={{ color: primaryColor }}>{title}</h4>
        <ResponsiveContainer width="100%" height={220}>
          {style === "bar" ? (
            <BarChart data={data}><CartesianGrid strokeDasharray="3 3" className="stroke-border" /><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip />{keys.map((k, i) => (<Bar key={k} dataKey={k} fill={DXC_CHART_COLORS[i]} radius={[4, 4, 0, 0]} />))}</BarChart>
          ) : style === "line" ? (
            <LineChart data={data}><CartesianGrid strokeDasharray="3 3" className="stroke-border" /><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip /><Legend />{keys.map((k, i) => (<Line key={k} type="monotone" dataKey={k} stroke={DXC_CHART_COLORS[i]} strokeWidth={2} dot={false} />))}</LineChart>
          ) : style === "area" ? (
            <AreaChart data={data}><CartesianGrid strokeDasharray="3 3" className="stroke-border" /><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip />{keys.map((k, i) => (<Area key={k} type="monotone" dataKey={k} fill={DXC_CHART_COLORS[i]} fillOpacity={0.3} stroke={DXC_CHART_COLORS[i]} />))}</AreaChart>
          ) : (
            <PieChart><Pie data={data} dataKey={keys[0]} nameKey="name" cx="50%" cy="50%" innerRadius={40} outerRadius={80}>{data.map((_, i) => (<Cell key={i} fill={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} />))}</Pie><Tooltip /><Legend /></PieChart>
          )}
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {renderChart(featureImportance.map((f) => ({ name: f.feature, importance: f.importance })), ["importance"], t("factorImportance", lang))}
      {renderChart(timeData, [t("current", lang), t("predicted", lang)], t("timeEvolution", lang))}
    </div>
  );
}

export function Dashboard() {
  const { dataset, modelResults, userPreferences, updatePreferences, pinnedInsights, togglePin, setPhase } = useAppStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  useDarkMode();

  const sector = dataset.detectedSector;
  const sectorInfo = SECTOR_LABELS[sector];
  const kpis = SECTOR_KPIS[sector];
  const { chartStyle, density, accentTheme, visibleKPIs, primaryColor, secondaryColor, language } = userPreferences;

  const visibleKPIList = kpis.filter((k) => visibleKPIs.includes(k.key));
  const kpiCount = density === "simplified" ? 4 : density === "standard" ? 6 : 8;
  const displayKPIs = visibleKPIList.slice(0, kpiCount);
  const gridCols = density === "simplified" ? "grid-cols-1 sm:grid-cols-2" : density === "standard" ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-4";

  const now = new Date();
  const timeStr = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
  const CHART_STYLES = getChartStyles(language);

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <div className="bg-dxc-midnight px-4 md:px-6 py-4 flex items-center justify-between flex-wrap gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <img src="/images/logo.png" alt="Logo" className="h-6 w-6 object-contain" />
            <span className="text-dxc-peach text-xs font-semibold">Intelligent Analytics</span>
          </div>
          <h1 className="text-dxc-peach font-bold text-base md:text-lg truncate">
            {t("dashboardTitle", language)} — {useAppStore.getState().onboarding.useCaseDescription.slice(0, 50)}...
          </h1>
          <p className="text-white/80 text-xs mt-0.5">{sectorInfo.icon} {sectorInfo.label} · {t("binaryClassification", language)} · {t("updatedAt", language)} {timeStr}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => setPhase(2)} className="text-xs border border-dxc-sky text-dxc-sky px-3 py-1.5 rounded-lg hover:bg-dxc-sky/10 transition-colors flex items-center gap-1"><MessageSquare size={12} /> {t("chat", language)}</button>
          <button className="text-xs border border-dxc-sky text-dxc-sky px-3 py-1.5 rounded-lg hover:bg-dxc-sky/10 transition-colors flex items-center gap-1"><RefreshCw size={12} /> {t("refresh", language)}</button>
          <button className="text-xs border border-dxc-peach text-dxc-peach px-3 py-1.5 rounded-lg hover:bg-dxc-peach/10 transition-colors flex items-center gap-1"><Download size={12} /> {t("export", language)}</button>
          <button onClick={() => setDrawerOpen(true)} className="text-xs bg-dxc-melon text-white px-3 py-1.5 rounded-lg hover:bg-dxc-red transition-colors flex items-center gap-1"><Settings size={12} /> {t("customize", language)}</button>
          <AccountMenu variant="dark" position="top" />
        </div>
      </div>

      <div className="p-4 md:p-6 space-y-6">
        <div className={`grid ${gridCols} gap-4`}>
          {displayKPIs.map((kpi) => (
            <div key={kpi.key} className="bg-card rounded-xl p-4 border-l-4 transition-all" style={{ borderColor: primaryColor }}>
              <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: primaryColor }}>{kpi.label}</p>
              <p className="text-3xl font-bold mt-1" style={{ color: primaryColor }}>{kpi.value}</p>
              <div className="flex items-center gap-1 mt-1">
                {kpi.variation > 0 ? <ArrowUp size={12} className="text-dxc-gold" /> : <ArrowDown size={12} className="text-destructive" />}
                <span className={`text-xs font-semibold ${kpi.variation > 0 ? "text-dxc-gold" : "text-destructive"}`}>{Math.abs(kpi.variation)}%</span>
              </div>
              <div className="mt-2"><Sparkline color={secondaryColor} /></div>
            </div>
          ))}
        </div>

        <DashboardChart chartStyle={chartStyle} primaryColor={primaryColor} lang={language} />

        {density === "expert" && (
          <div className="bg-card rounded-xl p-5 border border-border space-y-3">
            <h3 className="text-sm font-bold" style={{ color: primaryColor }}>{t("modelDiagnostics", language)}</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[{ label: "AUC", value: modelResults.auc }, { label: "F1 Score", value: modelResults.f1Score }, { label: "Precision", value: modelResults.precision }, { label: "Recall", value: modelResults.recall }, { label: "Accuracy", value: modelResults.accuracy }, { label: "Gini", value: modelResults.gini }, { label: "RMSE", value: modelResults.rmse }, { label: "LogLoss", value: modelResults.logLoss }].map((m) => (
                <div key={m.label} className="text-center p-3 rounded-lg bg-background">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">{m.label}</p>
                  <p className="text-xl font-bold" style={{ color: primaryColor }}>{m.value}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {(density === "standard" || density === "expert") && (
          <div className="bg-card rounded-xl overflow-hidden border border-border">
            <div className="px-4 py-3 border-b border-border"><h3 className="text-sm font-bold" style={{ color: primaryColor }}>{t("topEntities", language)}</h3></div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr className="bg-dxc-midnight">
                  <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("name", language)}</th>
                  <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("score", language)}</th>
                  <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("factor", language)}</th>
                  <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("trend", language)}</th>
                </tr></thead>
                <tbody>
                  {modelResults.topRiskyEntities.slice(0, density === "expert" ? 10 : 5).map((e, i) => (
                    <tr key={e.id} className={i % 2 === 0 ? "bg-card" : "bg-background"}>
                      <td className="px-3 py-2 font-medium">{e.name}</td>
                      <td className="px-3 py-2"><div className="flex items-center gap-2"><div className="w-16 h-1.5 bg-background rounded-full overflow-hidden"><div className="h-full rounded-full" style={{ width: `${e.riskScore}%`, background: e.riskScore > 80 ? "#D14600" : "#FF7E51" }} /></div><span className="font-semibold">{e.riskScore}%</span></div></td>
                      <td className="px-3 py-2">{e.mainFactor}</td>
                      <td className="px-3 py-2">{e.trend === "up" ? <ArrowUp size={12} className="text-destructive" /> : e.trend === "down" ? <ArrowDown size={12} className="text-dxc-gold" /> : <span className="text-primary">→</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <h3 className="text-sm font-bold" style={{ color: primaryColor }}>{t("pinnedInsights", language)}</h3>
          {pinnedInsights.length === 0 ? (
            <p className="text-xs text-muted-foreground">{t("pinFromConversations", language)}</p>
          ) : (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {pinnedInsights.map((msg) => (
                <div key={msg.id} className="bg-card border border-dxc-gold rounded-xl p-3 min-w-[280px] max-w-[320px] shrink-0 relative">
                  <button onClick={() => togglePin(msg.id)} className="absolute top-2 right-2 text-foreground/50 hover:text-destructive transition-colors min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("unpin", language)}><X size={14} /></button>
                  <p className="text-xs italic" style={{ color: primaryColor }}>{useAppStore.getState().messages.find((m) => m.role === "user" && new Date(m.timestamp).getTime() < new Date(msg.timestamp).getTime())?.content?.slice(0, 60) || "Question"}</p>
                  <div className="mt-2 h-20">{msg.charts?.[0] && (<ResponsiveContainer width={160} height={80}><BarChart data={msg.charts[0].data.slice(0, 4)}><Bar dataKey={msg.charts[0].dataKeys[0]} fill={primaryColor} radius={[2, 2, 0, 0]} /></BarChart></ResponsiveContainer>)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Customization Drawer */}
      {drawerOpen && (
        <>
          <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setDrawerOpen(false)} />
          <div className="fixed right-0 top-0 bottom-0 w-[300px] sm:w-[320px] bg-dxc-midnight z-50 animate-slide-in-right overflow-y-auto">
            <div className="p-5 space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-dxc-peach font-bold">{t("customizeDashboard", language)}</h3>
                <button onClick={() => setDrawerOpen(false)} className="text-white/70 hover:text-white min-w-[44px] min-h-[44px] flex items-center justify-center" aria-label={t("close", language)}><X size={18} /></button>
              </div>

              <div className="space-y-2">
                <label className="text-white/60 text-xs font-semibold flex items-center gap-2"><Globe size={14} /> {t("language", language)}</label>
                <div className="flex rounded-full overflow-hidden border border-dxc-royal/30">
                  <button onClick={() => updatePreferences({ language: "fr" })} className={`flex-1 py-2 text-xs font-medium ${language === "fr" ? "bg-dxc-peach text-dxc-midnight" : "text-white/60"}`}>🇫🇷 Français</button>
                  <button onClick={() => updatePreferences({ language: "en" })} className={`flex-1 py-2 text-xs font-medium ${language === "en" ? "bg-dxc-peach text-dxc-midnight" : "text-white/60"}`}>🇬🇧 English</button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-white/60 text-xs font-semibold">{t("mode", language)}</label>
                <div className="flex rounded-full overflow-hidden border border-dxc-royal/30">
                  <button onClick={() => updatePreferences({ darkMode: false })} className={`flex-1 py-2 text-xs font-medium ${!userPreferences.darkMode ? "bg-dxc-peach text-dxc-midnight" : "text-white/60"}`}>☀️ {t("light", language)}</button>
                  <button onClick={() => updatePreferences({ darkMode: true })} className={`flex-1 py-2 text-xs font-medium ${userPreferences.darkMode ? "bg-dxc-peach text-dxc-midnight" : "text-white/60"}`}>🌙 {t("dark", language)}</button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-white/60 text-xs font-semibold">{t("accentColor", language)}</label>
                <div className="flex gap-3 flex-wrap">
                  {ACCENT_SWATCHES.map((key) => {
                    const theme = ACCENT_THEMES[key];
                    const selected = accentTheme === key;
                    return (
                      <button key={key} onClick={() => updatePreferences({ accentTheme: key })} className="relative" aria-label={`${t("accentColor", language)}: ${theme.label}`}>
                        <div className={`w-8 h-8 rounded-full border-2 ${selected ? "ring-2 ring-dxc-peach ring-offset-2 ring-offset-dxc-midnight" : "border-dxc-royal/30"}`} style={{ background: `linear-gradient(135deg, ${theme.primary} 50%, ${theme.secondary} 50%)` }}>
                          {selected && <Check size={12} className="text-white mx-auto mt-1.5 drop-shadow" />}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-white/60 text-xs font-semibold">{t("chartStyle", language)}</label>
                <div className="flex flex-wrap gap-1.5">
                  {CHART_STYLES.map(({ key, label }) => (
                    <button key={key} onClick={() => updatePreferences({ chartStyle: key })} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${chartStyle === key ? "bg-dxc-melon text-white" : "bg-dxc-royal/20 text-white/60 hover:bg-dxc-royal/30"}`}>{label}</button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-white/60 text-xs font-semibold">{t("density", language)}</label>
                {(["simplified", "standard", "expert"] as Density[]).map((d) => (
                  <button key={d} onClick={() => updatePreferences({ density: d })} className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all ${density === d ? "bg-dxc-melon text-white" : "text-white/60 hover:bg-dxc-royal/20"}`}>
                    {d === "simplified" ? t("simplified", language) : d === "standard" ? t("standard", language) : t("expert", language)}
                  </button>
                ))}
              </div>

              <div className="space-y-2">
                <label className="text-white/60 text-xs font-semibold">{t("visibleKpis", language)}</label>
                {kpis.map((kpi) => (
                  <label key={kpi.key} className="flex items-center gap-2 text-white/70 text-xs cursor-pointer">
                    <input type="checkbox" checked={visibleKPIs.includes(kpi.key)} onChange={(e) => { const next = e.target.checked ? [...visibleKPIs, kpi.key] : visibleKPIs.filter((k) => k !== kpi.key); updatePreferences({ visibleKPIs: next }); }} className="rounded border-dxc-royal accent-dxc-melon" />
                    {kpi.label}
                  </label>
                ))}
              </div>

              <button onClick={() => updatePreferences({ darkMode: false, chartStyle: "bar", density: "standard", accentTheme: "royal-melon", visibleKPIs: kpis.map((k) => k.key), language: "fr" })} className="w-full border border-dxc-red text-dxc-red py-2 rounded-lg text-xs font-medium hover:bg-dxc-red/10 transition-colors">
                {t("reset", language)}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
