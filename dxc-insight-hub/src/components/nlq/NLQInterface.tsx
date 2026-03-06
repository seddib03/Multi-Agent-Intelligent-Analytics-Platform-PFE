import { useState, useRef, useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS, getSuggestedQuestions, generateMockResponse } from "@/lib/mockData";
import { DXC_CHART_COLORS } from "@/types/app";
import { Send, Download, BarChart3, Pin, Plus, MessageSquare, Lightbulb, History } from "lucide-react";
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { ChartData, Message, Entity } from "@/types/app";

function DXCChart({ chart, style }: { chart: ChartData; style: string }) {
  const effectiveType = style === "heatmap" ? "bar" : style === "pie" && chart.dataKeys.length > 1 ? "bar" : style;
  const type = effectiveType as string;

  return (
    <div className="bg-dxc-white rounded-xl p-4 border border-dxc-canvas">
      <h4 className="text-xs font-semibold text-dxc-royal mb-3">{chart.title}</h4>
      <ResponsiveContainer width="100%" height={180}>
        {type === "bar" ? (
          <BarChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F6F3F0" />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#0E1020" }} />
            <YAxis tick={{ fontSize: 10, fill: "#0E1020" }} />
            <Tooltip />
            {chart.dataKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        ) : type === "line" ? (
          <LineChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F6F3F0" />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#0E1020" }} />
            <YAxis tick={{ fontSize: 10, fill: "#0E1020" }} />
            <Tooltip />
            <Legend />
            {chart.dataKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} strokeWidth={2} dot={false} />
            ))}
          </LineChart>
        ) : type === "area" ? (
          <AreaChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F6F3F0" />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#0E1020" }} />
            <YAxis tick={{ fontSize: 10, fill: "#0E1020" }} />
            <Tooltip />
            {chart.dataKeys.map((key, i) => (
              <Area key={key} type="monotone" dataKey={key} fill={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} fillOpacity={0.3} stroke={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} />
            ))}
          </AreaChart>
        ) : (
          <PieChart>
            <Pie data={chart.data} dataKey={chart.dataKeys[0]} nameKey="name" cx="50%" cy="50%" innerRadius={30} outerRadius={60}>
              {chart.data.map((_, i) => (
                <Cell key={i} fill={DXC_CHART_COLORS[i % DXC_CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function PredictionTable({ predictions }: { predictions: Entity[] }) {
  return (
    <div className="rounded-xl overflow-hidden border border-dxc-canvas">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-dxc-midnight">
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">Nom</th>
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">Score risque</th>
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">Facteur principal</th>
            <th className="px-3 py-2 text-left text-dxc-peach font-bold">Tendance</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((e, i) => (
            <tr key={e.id} className={i % 2 === 0 ? "bg-dxc-white" : "bg-dxc-canvas"}>
              <td className="px-3 py-2 text-dxc-midnight font-medium">{e.name}</td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-dxc-canvas rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${e.riskScore}%`,
                        background: e.riskScore > 80 ? "#D14600" : e.riskScore > 60 ? "#FF7E51" : "#004AAC",
                      }}
                    />
                  </div>
                  <span className="text-dxc-midnight font-semibold">{e.riskScore}%</span>
                </div>
              </td>
              <td className="px-3 py-2 text-dxc-midnight">{e.mainFactor}</td>
              <td className="px-3 py-2">
                <span className={e.trend === "up" ? "text-dxc-red" : e.trend === "down" ? "text-dxc-gold" : "text-dxc-royal"}>
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
    <div className="flex items-center gap-1 py-3">
      {steps.map((s, i) => (
        <div key={s} className="flex items-center gap-1">
          <div className="text-center">
            <div
              className={`w-2.5 h-2.5 rounded-full mx-auto transition-colors ${
                i < active ? "bg-dxc-royal" : i === active ? "bg-dxc-melon animate-pulse-dot" : "bg-dxc-canvas"
              }`}
            />
            <span className="text-[8px] text-dxc-midnight/40 mt-0.5 block">{s}</span>
          </div>
          {i < steps.length - 1 && <span className="text-dxc-canvas text-[8px] mb-3">──→</span>}
        </div>
      ))}
    </div>
  );
}

export function NLQInterface() {
  const { dataset, messages, addMessage, togglePin, setPhase, userPreferences } = useAppStore();
  const [input, setInput] = useState("");
  const [processing, setProcessing] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const sector = dataset.detectedSector;
  const sectorInfo = SECTOR_LABELS[sector];
  const suggestions = getSuggestedQuestions(sector);
  const chartStyle = userPreferences.chartStyle;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (text: string) => {
    if (!text.trim()) return;
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    addMessage(userMsg);
    setInput("");
    setProcessing(true);

    setTimeout(() => {
      const { text: responseText, charts, predictions } = generateMockResponse(text, sector);
      const sysMsg: Message = {
        id: `s-${Date.now()}`,
        role: "system",
        content: responseText,
        charts,
        predictions,
        timestamp: new Date(),
      };
      addMessage(sysMsg);
      setProcessing(false);
    }, 2000);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      handleSend(input);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <div className="w-[260px] bg-dxc-midnight flex flex-col shrink-0">
        <div className="p-4 border-b border-dxc-royal/20">
          <span className="text-dxc-white font-bold text-[22px]">DXC</span>
          <span className="text-dxc-peach text-[11px] ml-1">Insight Platform</span>
        </div>

        {/* Active project */}
        <div className="p-4">
          <div className="bg-dxc-royal/20 border-l-[3px] border-dxc-melon rounded-r-lg p-3 space-y-2">
            <p className="text-dxc-white text-xs line-clamp-2">{useAppStore.getState().onboarding.useCaseDescription}</p>
            <div className="flex gap-1.5 flex-wrap">
              <span className="text-[10px] bg-dxc-royal text-dxc-white px-1.5 py-0.5 rounded">{sectorInfo.icon} {sectorInfo.label}</span>
              <span className="text-[10px] bg-dxc-melon/20 text-dxc-peach px-1.5 py-0.5 rounded">XGBoost · AUC 0.87</span>
            </div>
          </div>
        </div>

        {/* Suggestions */}
        <div className="px-4 flex-1 overflow-y-auto space-y-4">
          <div>
            <h4 className="text-dxc-peach text-[10px] uppercase tracking-wider font-semibold mb-2 flex items-center gap-1">
              <Lightbulb size={10} /> Suggestions
            </h4>
            <div className="space-y-1">
              {suggestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(q)}
                  className="w-full text-left text-dxc-white/80 text-xs p-2 rounded-lg hover:bg-dxc-royal/20 transition-colors flex items-start gap-2"
                >
                  <span className="text-dxc-sky shrink-0 mt-0.5">→</span>
                  <span>{q}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-dxc-peach text-[10px] uppercase tracking-wider font-semibold mb-2 flex items-center gap-1">
              <History size={10} /> Historique
            </h4>
            {messages.filter((m) => m.role === "user").slice(-4).map((m) => (
              <button
                key={m.id}
                className="w-full text-left text-dxc-white/60 text-xs p-2 rounded-lg hover:bg-dxc-royal/20 transition-colors truncate"
              >
                {m.content}
              </button>
            ))}
          </div>
        </div>

        {/* Bottom buttons */}
        <div className="p-4 space-y-2">
          <button
            onClick={() => setPhase(3)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-dxc-royal text-dxc-white rounded-lg text-xs font-medium hover:bg-dxc-blue transition-colors"
          >
            <BarChart3 size={14} /> Dashboard
          </button>
          <button className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-dxc-melon text-dxc-white rounded-lg text-xs font-medium hover:bg-dxc-red transition-colors">
            <Plus size={14} /> Nouveau Projet
          </button>
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col bg-dxc-canvas">
        {/* Context bar */}
        <div className="bg-dxc-white border-b border-dxc-canvas px-6 py-2 flex items-center gap-2 flex-wrap">
          <span className="text-[11px] bg-dxc-royal text-dxc-white px-2 py-0.5 rounded">{sectorInfo.label}</span>
          {useAppStore.getState().onboarding.analysisTypes.map((t) => (
            <span key={t} className="text-[11px] bg-dxc-melon/10 text-dxc-melon px-2 py-0.5 rounded">{t}</span>
          ))}
          <span className="text-[11px] text-dxc-midnight/50">{dataset.rowCount.toLocaleString()} enregistrements</span>
          <span className="text-[11px] bg-dxc-canvas text-dxc-royal px-2 py-0.5 rounded">XGBoost · AUC 0.871</span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <MessageSquare className="mx-auto text-dxc-royal/20 mb-4" size={48} />
              <p className="text-dxc-midnight/40 text-sm">Posez votre première question sur vos données</p>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`max-w-3xl ${msg.role === "user" ? "ml-auto" : ""} animate-fade-in`}>
              {msg.role === "user" ? (
                <div className="bg-dxc-royal text-dxc-white px-4 py-3 rounded-2xl rounded-br-sm text-sm">
                  {msg.content}
                </div>
              ) : (
                <div className="bg-dxc-white border-l-[3px] border-dxc-melon rounded-r-2xl rounded-bl-2xl shadow-sm p-4 space-y-4">
                  <div className="text-sm text-dxc-midnight leading-relaxed whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{
                      __html: msg.content
                        .replace(/\*\*(.*?)\*\*/g, '<strong class="text-dxc-royal">$1</strong>')
                    }}
                  />
                  {msg.charts && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {msg.charts.map((chart, i) => (
                        <DXCChart key={i} chart={chart} style={chartStyle} />
                      ))}
                    </div>
                  )}
                  {msg.predictions && msg.predictions.length > 0 && (
                    <PredictionTable predictions={msg.predictions} />
                  )}
                  <div className="flex gap-2 pt-2">
                    <button className="text-xs border border-dxc-royal text-dxc-royal px-3 py-1.5 rounded-lg hover:bg-dxc-canvas transition-colors flex items-center gap-1">
                      <Download size={12} /> Exporter CSV
                    </button>
                    <button
                      onClick={() => setPhase(3)}
                      className="text-xs bg-dxc-royal text-dxc-white px-3 py-1.5 rounded-lg hover:bg-dxc-blue transition-colors flex items-center gap-1"
                    >
                      <BarChart3 size={12} /> Dashboard
                    </button>
                    <button
                      onClick={() => togglePin(msg.id)}
                      className="text-xs border border-dxc-gold text-dxc-gold px-3 py-1.5 rounded-lg hover:bg-dxc-gold/10 transition-colors flex items-center gap-1"
                    >
                      <Pin size={12} /> Épingler
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {processing && (
            <div className="max-w-3xl animate-fade-in">
              <ProcessingIndicator />
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="bg-dxc-white border-t border-dxc-canvas p-4">
          <div className="max-w-3xl mx-auto flex gap-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Posez une question sur vos données..."
              className="flex-1 bg-dxc-canvas rounded-xl px-4 py-3 text-sm text-dxc-midnight placeholder:text-dxc-royal/40 border-2 border-transparent focus:border-dxc-royal focus:outline-none"
            />
            <button
              onClick={() => handleSend(input)}
              disabled={!input.trim() || processing}
              className="w-10 h-10 rounded-full bg-dxc-melon text-dxc-white flex items-center justify-center hover:bg-dxc-red transition-colors disabled:opacity-40 shrink-0 self-center"
            >
              <Send size={16} />
            </button>
          </div>
          <p className="text-[10px] text-dxc-midnight/30 text-center mt-1">Ctrl+Enter pour envoyer</p>
        </div>
      </div>
    </div>
  );
}
