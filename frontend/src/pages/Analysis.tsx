import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { mockModelResults, sectorSuggestions, mockNLQResponses } from '@/data/mockData';
import { Send, Pin, Download, BarChart2, Database, Settings, MessageSquare } from 'lucide-react';
import type { Message } from '@/types';

export default function Analysis() {
  const { id } = useParams<{ id: string }>();
  const { projects, messages, addMessage, togglePinMessage } = useAppStore();
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const project = projects.find((p) => p.id === id);
  const suggestions = sectorSuggestions[project?.sector || 'finance'] || sectorSuggestions.finance;

  const handleSend = (text?: string) => {
    const q = text || input;
    if (!q.trim()) return;
    const userMsg: Message = { id: 'msg-' + Date.now(), role: 'user', content: q, timestamp: new Date().toISOString() };
    addMessage(userMsg);
    setInput('');
    setIsTyping(true);

    setTimeout(() => {
      const resp = mockNLQResponses.default;
      const sysMsg: Message = {
        id: 'msg-' + (Date.now() + 1), role: 'system', content: resp.text, timestamp: new Date().toISOString(),
        insights: { chartType: 'bar', data: resp.chartData, title: 'Importance des features' },
      };
      addMessage(sysMsg);
      setIsTyping(false);
    }, 2000);
  };

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* Sidebar */}
      <div className="w-64 bg-dxc-midnight shrink-0 flex flex-col p-4 overflow-y-auto">
        <div className="mb-6">
          <h3 className="text-dxc-peach text-xs font-bold mb-2">PROJET ACTIF</h3>
          <p className="text-dxc-white text-sm font-medium line-clamp-2">{project?.title}</p>
          <div className="flex gap-1 mt-2">
            <span className="text-[10px] bg-dxc-royal/30 text-dxc-sky px-2 py-0.5 rounded-full">{project?.sector}</span>
            <span className="text-[10px] bg-dxc-melon/30 text-dxc-melon px-2 py-0.5 rounded-full">{project?.algorithm || 'XGBoost'}</span>
          </div>
        </div>

        <div className="mb-6">
          <h3 className="text-dxc-peach text-xs font-bold mb-3">SUGGESTIONS</h3>
          <div className="space-y-2">
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => handleSend(s)} className="w-full text-left text-xs text-dxc-white/70 hover:text-dxc-white p-2 rounded-lg hover:bg-dxc-royal/20 transition-colors">
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-auto space-y-2">
          <Link to={`/app/projects/${id}/data`} className="flex items-center gap-2 text-xs text-dxc-white/60 hover:text-dxc-white p-2 rounded-lg hover:bg-dxc-royal/20 transition-colors">
            <Database className="h-3.5 w-3.5" /> 🗂️ Données
          </Link>
          <Link to={`/app/projects/${id}/dashboard`} className="flex items-center gap-2 text-xs text-dxc-white/60 hover:text-dxc-white p-2 rounded-lg hover:bg-dxc-royal/20 transition-colors">
            <BarChart2 className="h-3.5 w-3.5" /> 📊 Dashboard
          </Link>
          <Link to={`/app/projects/${id}/settings`} className="flex items-center gap-2 text-xs text-dxc-white/60 hover:text-dxc-white p-2 rounded-lg hover:bg-dxc-royal/20 transition-colors">
            <Settings className="h-3.5 w-3.5" /> ⚙️ Paramètres
          </Link>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <MessageSquare className="h-12 w-12 text-muted-foreground/20 mb-4" />
              <h2 className="text-lg font-bold text-foreground mb-2">Posez votre première question</h2>
              <p className="text-sm text-muted-foreground max-w-md">Interrogez vos données en langage naturel. Le système analysera automatiquement et générera des insights.</p>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-2xl rounded-xl p-4 ${msg.role === 'user' ? 'bg-dxc-royal text-dxc-white' : 'bg-card border-l-4 border-l-dxc-melon border border-border'}`}>
                <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                {msg.role === 'system' && (
                  <div className="flex gap-2 mt-3 pt-3 border-t border-border">
                    <button className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"><Download className="h-3 w-3" /> Exporter</button>
                    <button onClick={() => togglePinMessage(msg.id)} className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"><Pin className="h-3 w-3" /> Épingler</button>
                    <Link to={`/app/projects/${id}/dashboard`} className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"><BarChart2 className="h-3 w-3" /> Dashboard</Link>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-card border border-border rounded-xl p-4">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-dxc-melon rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-dxc-melon rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-dxc-melon rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-border p-4">
          <div className="flex items-center gap-3 max-w-3xl mx-auto">
            <input type="text" value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Posez une question sur vos données..."
              className="flex-1 bg-card border border-border rounded-xl px-4 py-3 text-sm text-card-foreground placeholder:text-muted-foreground focus:outline-none focus:border-dxc-royal" />
            <button onClick={() => handleSend()} disabled={!input.trim()}
              className="h-11 w-11 rounded-full bg-dxc-melon text-dxc-white flex items-center justify-center hover:opacity-90 disabled:opacity-40 shrink-0">
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
