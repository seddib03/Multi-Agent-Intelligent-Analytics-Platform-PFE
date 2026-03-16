import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS, getSuggestedQuestions, generateMockResponse } from "@/lib/mockData";
import { DXC_CHART_COLORS } from "@/types/app";
import {
  Send, Download, BarChart3, Pin, Plus, MessageSquare,
  Lightbulb, History, Menu, X, User, Settings,
} from "lucide-react";
import { ChatHistoryDrawer } from "@/components/chat/ChatHistoryDrawer";
import { AccountMenu } from "@/components/ui/AccountMenu";
import BrandLogo from "@/components/BrandLogo";
import { t } from "@/lib/i18n";
import { toast } from "sonner";
import { useDarkMode } from "@/hooks/useDarkMode";
import { useIsMobile } from "@/hooks/use-mobile";
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { ChartData, Message, Entity } from "@/types/app";

// ── Chart renderer ─────────────────────────────────────────────────────────
function DXCChart({ chart, style }: { chart: ChartData; style: string }) {
  const effectiveType =
    style === "heatmap" ? "bar"
    : style === "pie" && chart.dataKeys.length > 1 ? "bar"
    : style;
  const type = effectiveType as string;
  return (
    <div className="bg-card rounded-xl p-4 border border-border">
      <h4 className="text-xs font-semibold text-primary mb-3">{chart.title}</h4>
      <ResponsiveContainer width="100%" height={180}>
        {type === "bar" ? (
          <BarChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            {chart.dataKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        ) : type === "line" ? (
          <LineChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip /><Legend />
            {chart.dataKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} strokeWidth={2} dot={false} />
            ))}
          </LineChart>
        ) : type === "area" ? (
          <AreaChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            {chart.dataKeys.map((key, i) => (
              <Area key={key} type="monotone" dataKey={key} fill={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} fillOpacity={0.3} stroke={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} />
            ))}
          </AreaChart>
        ) : (
          <PieChart>
            <Pie data={chart.data} dataKey={chart.dataKeys[0]} nameKey="name" cx="50%" cy="50%" innerRadius={30} outerRadius={60}>
              {chart.data.map((_, i) => (<Cell key={i} fill={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} />))}
            </Pie>
            <Tooltip />
          </PieChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

// ── Prediction table ────────────────────────────────────────────────────────
function PredictionTable({ predictions, lang }: { predictions: Entity[]; lang: "fr" | "en" }) {
  return (
    <div className="rounded-xl overflow-hidden border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-dxc-midnight">
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("name", lang)}</th>
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("score", lang)}</th>
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("factor", lang)}</th>
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">{t("trend", lang)}</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((e, i) => (
            <tr key={e.id} className={i % 2 === 0 ? "bg-card" : "bg-muted"}>
              <td className="px-3 py-2 text-foreground font-medium">{e.name}</td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full origin-left ${
                        e.riskScore > 80
                          ? "bg-dxc-red scale-x-100"
                          : e.riskScore > 60
                            ? "bg-dxc-melon scale-x-75"
                            : "bg-dxc-blue scale-x-50"
                      }`}
                    />
                  </div>
                  <span className="text-foreground font-semibold">{e.riskScore}%</span>
                </div>
              </td>
              <td className="px-3 py-2 text-foreground">{e.mainFactor}</td>
              <td className="px-3 py-2">
                <span className={e.trend === "up" ? "text-destructive" : e.trend === "down" ? "text-dxc-gold" : "text-primary"}>
                  {e.trend === "up" ? "↑" : e.trend === "down" ? "↓" : "→"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Processing indicator ────────────────────────────────────────────────────
function ProcessingIndicator() {
  const steps = ["NLQ Agent", "Intent", "Orchestrateur", "Agent Métier", "Insight"];
  const [active, setActive] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => {
      setActive((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, 300);
    return () => clearInterval(interval);
  }, []);
  return (
    <div className="flex items-center gap-1 py-3" role="status" aria-live="polite" aria-label="Traitement en cours">
      {steps.map((s, i) => (
        <div key={s} className="flex items-center gap-1">
          <div className="text-center">
            <div className={`w-2.5 h-2.5 rounded-full mx-auto transition-colors ${i < active ? "bg-primary" : i === active ? "bg-dxc-melon animate-pulse-dot" : "bg-muted"}`} />
            <span className="text-xs text-muted-foreground mt-0.5 block">{s}</span>
          </div>
          {i < steps.length - 1 && <span className="text-muted text-xs mb-3">──→</span>}
        </div>
      ))}
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────
export function NLQInterface() {
  const {
    dataset, onboarding, messages, addMessage, togglePin,
    setPhase, userPreferences, resetProject, clearMessages,
  } = useAppStore();
  const navigate   = useNavigate();
  const lang       = userPreferences.language;
  const [input, setInput]                     = useState("");
  const [processing, setProcessing]           = useState(false);
  const [historyOpen, setHistoryOpen]         = useState(false);
  const [sidebarOpen, setSidebarOpen]         = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [analysisFile, setAnalysisFile] = useState<File | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const isMobile   = useIsMobile();
  useDarkMode();

  const rawSector         = dataset.detectedSector;
  const safeSector        = rawSector && rawSector in SECTOR_LABELS ? rawSector : undefined;
  const sectorInfo        = safeSector ? SECTOR_LABELS[safeSector] : undefined;
  const apiDetectedSector = onboarding.sectorContext?.sector?.trim();
  const detectedSectorLabel = apiDetectedSector
    ? apiDetectedSector
    : rawSector && rawSector !== "public"
    ? (SECTOR_LABELS[rawSector]?.label ?? rawSector)
    : "";
  const suggestions  = safeSector ? getSuggestedQuestions(safeSector) ?? [] : [];
  const chartStyle   = userPreferences.chartStyle;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (text: string) => {
    if (!text.trim()) return;
    const userMsg: Message = { id: `u-${Date.now()}`, role: "user", content: text, timestamp: new Date() };
    addMessage(userMsg);
    setInput("");
    setProcessing(true);
    setTimeout(() => {
      if (!safeSector) {
        addMessage({
          id: `s-${Date.now()}`,
          role: "system",
          content: "Le secteur n'a pas encore ete detecte. Veuillez revenir a l'etape 1.",
          timestamp: new Date(),
        });
        setProcessing(false);
        return;
      }
      const { text: responseText, charts, predictions } = generateMockResponse(text, safeSector);
      addMessage({ id: `s-${Date.now()}`, role: "system", content: responseText, charts, predictions, timestamp: new Date() });
      setProcessing(false);
    }, 1200);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (isMobile && e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    } else if (!isMobile && (e.ctrlKey || e.metaKey) && e.key === "Enter") {
      handleSend(input);
    }
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Mobile sidebar toggle */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed top-3 left-3 z-50 lg:hidden p-2.5 rounded-lg bg-dxc-midnight text-dxc-white shadow-lg min-w-[44px] min-h-[44px] flex items-center justify-center"
        aria-label="Ouvrir le menu"
      >
        <Menu size={20} />
      </button>

      {sidebarOpen && <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />}

      {/* Sidebar */}
      <div className={`${sidebarOpen ? "translate-x-0" : "-translate-x-full"} ${sidebarCollapsed ? "lg:-translate-x-full lg:w-0 lg:overflow-hidden" : "lg:translate-x-0"} fixed lg:relative z-50 lg:z-auto w-[260px] bg-dxc-midnight flex flex-col shrink-0 h-full transition-transform duration-300`}>
        <div className="p-3 border-b border-dxc-royal/20">
          <div className="flex items-center justify-between gap-2">
            <button onClick={() => setSidebarCollapsed(true)} className="hidden lg:flex p-1.5 rounded-lg bg-dxc-royal/20 text-dxc-white min-w-[36px] min-h-[36px] items-center justify-center" aria-label="Masquer la sidebar">
              <X size={14} />
            </button>
            <BrandLogo logoClassName="h-5" showSubtitle={false} />
            <div className="flex items-center gap-2">
              <button onClick={() => setHistoryOpen(true)} className="p-1.5 rounded-lg bg-dxc-royal/20 text-dxc-white min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("chatHistory", lang)}>
                <History size={14} />
              </button>
              <button onClick={() => setSidebarOpen(false)} className="p-1.5 rounded-lg text-dxc-peach lg:hidden min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label="Fermer le menu">
                <X size={16} />
              </button>
            </div>
          </div>
        </div>

        <div className="px-4 pt-4 pb-1">
          {detectedSectorLabel && (
            <p className="text-xs text-dxc-white">Secteur: <span className="text-dxc-melon font-semibold">{detectedSectorLabel}</span></p>
          )}
        </div>

        <div className="px-4 pt-2 pb-1">
          <div className="bg-dxc-royal/20 border-l-[3px] border-dxc-melon rounded-r-lg p-3 space-y-2">
            <p className="text-dxc-peach text-[10px] uppercase tracking-wider font-semibold">Use case</p>
            <p className="text-dxc-white text-xs font-medium line-clamp-2">{useAppStore.getState().onboarding.useCaseDescription || "—"}</p>
          </div>
        </div>

        <div className="px-4 flex-1 overflow-y-auto">
          <div className="mb-4 bg-dxc-royal/20 rounded-lg p-3 space-y-2">
            <p className="text-dxc-peach text-xs uppercase tracking-wider font-semibold">{t("datasetUsed", lang)}</p>
            <p className="text-dxc-white text-xs font-medium truncate">{dataset.fileName || "dataset.csv"}</p>
            <p className="text-dxc-sky text-xs">{dataset.rowCount.toLocaleString()} {t("registrations", lang)} · {dataset.columnCount} {t("cols", lang)}</p>
            <button
              onClick={() => { setPhase(1); useAppStore.getState().setOnboardingStep(1); setSidebarOpen(false); }}
              className="text-xs text-dxc-sky hover:text-dxc-white transition-colors flex items-center gap-1 min-h-[44px]"
            >
              ✏️ {t("modifySettings", lang)}
            </button>
          </div>
        </div>

        <div className="p-4 space-y-2">
          <button onClick={() => { clearMessages(); toast.success(t("newChatStarted", lang)); }} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-dxc-melon text-dxc-white rounded-lg text-xs font-medium hover:bg-dxc-red transition-colors min-h-[36px]">
            <Plus size={12} /> {t("newChat", lang)}
          </button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-dxc-royal/30 text-dxc-peach rounded-lg text-xs font-medium hover:bg-dxc-royal/50 transition-colors min-h-[36px]">
                <Plus size={12} /> {t("newProjectBtn", lang)}
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t("confirmNewProjectTitle", lang)}</AlertDialogTitle>
                <AlertDialogDescription>{t("confirmNewProjectDesc", lang)}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t("cancel", lang)}</AlertDialogCancel>
                <AlertDialogAction onClick={() => resetProject()} className="bg-primary text-primary-foreground hover:bg-primary/90">{t("confirm", lang)}</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <button onClick={() => setPhase(2)} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-dxc-royal text-dxc-white rounded-lg text-xs font-medium hover:bg-dxc-blue transition-colors min-h-[36px]">
            <BarChart3 size={12} /> {t("dashboard", lang)}
          </button>
          <AccountMenu variant="dark" />
        </div>
      </div>

      {sidebarCollapsed && (
        <div className="hidden lg:flex w-[56px] bg-dxc-midnight border-r border-dxc-royal/20 flex-col items-center gap-2 py-3 shrink-0 h-full">
          <button onClick={() => setSidebarCollapsed(false)} className="p-2 rounded-lg bg-dxc-royal/20 text-dxc-white min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label="Réafficher la sidebar">
            <Menu size={14} />
          </button>
          <div className="mt-auto flex flex-col items-center gap-2 pb-2">
            <button onClick={() => setHistoryOpen(true)} className="p-2 rounded-lg bg-dxc-royal/20 text-dxc-white min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("chatHistory", lang)}>
              <History size={14} />
            </button>
            <button onClick={() => { clearMessages(); toast.success(t("newChatStarted", lang)); }} className="p-2 rounded-lg bg-dxc-royal/20 text-dxc-white min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("newChat", lang)}>
              <Plus size={14} />
            </button>
            <button onClick={() => navigate("/profile")} className="p-2 rounded-lg bg-dxc-royal/20 text-dxc-white min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("myAccount", lang)}>
              <User size={14} />
            </button>
            <button onClick={() => navigate("/settings")} className="p-2 rounded-lg bg-dxc-royal/20 text-dxc-white min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("settings", lang)}>
              <Settings size={14} />
            </button>
          </div>
        </div>
      )}

      <ChatHistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="bg-card border-b border-border px-4 md:px-6 py-2 flex items-center gap-2 flex-wrap pl-14 lg:pl-6">
          <BrandLogo logoClassName="h-7" showSubtitle={false} className="mr-2" />
          {detectedSectorLabel && (
            <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded">{detectedSectorLabel}</span>
          )}
          <span className="text-xs text-muted-foreground">{dataset.rowCount.toLocaleString()} {t("registrations", lang)}</span>
        </div>

        <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-8">
              <MessageSquare className="mx-auto text-muted-foreground/20 mb-4" size={48} />
              <p className="text-muted-foreground text-sm mb-6">{t("askFirstQuestion", lang)}</p>
              <p className="text-muted-foreground/60 text-xs mb-4">{t("tryAskingOne", lang)}</p>
              <div className="max-w-2xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(q)}
                    className="text-left text-sm p-3 rounded-xl border border-border bg-card hover:border-primary/50 hover:bg-primary/5 transition-all flex items-start gap-2 group h-full min-h-[60px]"
                  >
                    <Lightbulb size={14} className="text-dxc-melon shrink-0 mt-0.5" />
                    <span className="text-foreground/80 group-hover:text-foreground">{q}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`max-w-3xl ${msg.role === "user" ? "ml-auto" : ""} animate-fade-in`}>
              {msg.role === "user" ? (
                <div className="bg-primary text-primary-foreground px-4 py-3 rounded-2xl rounded-br-sm text-sm">{msg.content}</div>
              ) : (
                <div className="bg-card border-l-[3px] border-dxc-melon rounded-r-2xl rounded-bl-2xl shadow-sm p-4 space-y-4">
                  <div
                    className="text-sm text-foreground leading-relaxed whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.*?)\*\*/g, '<strong class="text-primary">$1</strong>') }}
                  />
                  {msg.charts && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {msg.charts.map((chart, i) => (<DXCChart key={i} chart={chart} style={chartStyle} />))}
                    </div>
                  )}
                  {msg.predictions && msg.predictions.length > 0 && (
                    <PredictionTable predictions={msg.predictions} lang={lang} />
                  )}
                  <div className="flex gap-2 pt-2 flex-wrap">
                    <button className="text-xs border border-primary text-primary px-3 py-1.5 rounded-lg hover:bg-primary/5 transition-colors flex items-center gap-1 min-h-[36px]" aria-label={t("exportCsv", lang)}>
                      <Download size={12} /> {t("exportCsv", lang)}
                    </button>
                    <button onClick={() => setPhase(3)} className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-lg hover:opacity-90 transition-colors flex items-center gap-1 min-h-[36px]" aria-label={t("dashboard", lang)}>
                      <BarChart3 size={12} /> {t("dashboard", lang)}
                    </button>
                    <button onClick={() => togglePin(msg.id)} className="text-xs border border-dxc-gold text-dxc-gold px-3 py-1.5 rounded-lg hover:bg-dxc-gold/10 transition-colors flex items-center gap-1 min-h-[36px]" aria-label={t("pin", lang)}>
                      <Pin size={12} /> {t("pin", lang)}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}

          {processing && <div className="max-w-3xl animate-fade-in"><ProcessingIndicator /></div>}
          <div ref={chatEndRef} />
        </div>

        <div className="bg-card border-t border-border p-4">
          <div className="max-w-3xl mx-auto flex gap-3">
            <label className="flex items-center justify-center w-11 h-11 rounded-full border border-border bg-muted hover:bg-muted/80 cursor-pointer shrink-0 self-center min-w-[44px] min-h-[44px]" aria-label="Uploader un CSV">
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null;
                  setAnalysisFile(file);
                }}
              />
              <Plus size={16} />
            </label>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t("askQuestion", lang)}
              disabled={processing}
              className="flex-1 bg-muted rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-foreground/30 border-2 border-transparent focus:border-primary focus:outline-none disabled:opacity-60"
              aria-label={t("askQuestion", lang)}
            />
            <button
              onClick={() => handleSend(input)}
              disabled={!input.trim() || processing}
              className="w-11 h-11 rounded-full bg-dxc-melon text-dxc-white flex items-center justify-center hover:bg-dxc-red transition-colors disabled:opacity-40 shrink-0 self-center min-w-[44px] min-h-[44px]"
              aria-label="Envoyer"
            >
              <Send size={16} />
            </button>
          </div>
          {analysisFile && (
            <p className="text-xs text-muted-foreground text-center mt-2">
              CSV sélectionné: {analysisFile.name}
            </p>
          )}
          <p className="text-xs text-muted-foreground text-center mt-1">
            {isMobile ? t("enterToSend", lang) : t("ctrlEnterSend", lang)}
          </p>
        </div>
      </div>
    </div>
  );
}