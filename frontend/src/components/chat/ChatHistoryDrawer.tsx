import { useState } from "react";
import { useAppStore } from "@/stores/appStore";
import { History, X, Search, Trash2, MessageSquare, ArrowRight, Plus } from "lucide-react";
import { SECTOR_LABELS } from "@/lib/mockData";
import { t } from "@/lib/i18n";

interface Conversation {
  id: string;
  title: string;
  sector: string;
  messageCount: number;
  lastMessage: Date;
  preview: string;
}

const MOCK_CONVERSATIONS: Conversation[] = [
  { id: "conv-1", title: "Analyse des retards de paiement", sector: "finance", messageCount: 12, lastMessage: new Date(Date.now() - 1000 * 60 * 30), preview: "Quels clients ont le plus de retards..." },
  { id: "conv-2", title: "Prédiction de churn Q4", sector: "retail", messageCount: 8, lastMessage: new Date(Date.now() - 1000 * 60 * 60 * 3), preview: "Montre-moi les facteurs de churn..." },
  { id: "conv-3", title: "Optimisation logistique", sector: "transport", messageCount: 15, lastMessage: new Date(Date.now() - 1000 * 60 * 60 * 24), preview: "Analyse les routes les plus coûteuses..." },
];

function formatTimeAgo(date: Date, lang: "fr" | "en"): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / (1000 * 60));
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (minutes < 60) return t("timeAgoMin", lang).replace("{n}", String(minutes));
  if (hours < 24) return t("timeAgoHours", lang).replace("{n}", String(hours));
  return t("timeAgoDays", lang).replace("{n}", String(days));
}

interface ChatHistoryDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function ChatHistoryDrawer({ open, onClose }: ChatHistoryDrawerProps) {
  const { messages, userPreferences } = useAppStore();
  const lang = userPreferences.language;
  const [search, setSearch] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>(MOCK_CONVERSATIONS);

  const currentConv: Conversation | null = messages.length > 0 ? {
    id: "current",
    title: messages.find(m => m.role === "user")?.content.slice(0, 40) || t("currentConversation", lang),
    sector: useAppStore.getState().dataset.detectedSector,
    messageCount: messages.length,
    lastMessage: new Date(),
    preview: messages[messages.length - 1]?.content.slice(0, 50) || "",
  } : null;

  const allConversations = currentConv ? [currentConv, ...conversations] : conversations;
  const filtered = allConversations.filter((c) => c.title.toLowerCase().includes(search.toLowerCase()) || c.preview.toLowerCase().includes(search.toLowerCase()));

  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const handleDelete = (id: string) => { setConversations((prev) => prev.filter((c) => c.id !== id)); setDeleteConfirmId(null); };
  const handleResume = (_conv: Conversation) => { onClose(); };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />
      <div className="fixed left-0 top-0 bottom-0 w-[320px] sm:w-[360px] bg-dxc-midnight z-50 animate-slide-in-left flex flex-col">
        <div className="p-4 border-b border-dxc-royal/20">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History size={18} className="text-dxc-peach" />
              <h3 className="text-white font-bold">{t("history", lang)}</h3>
            </div>
            <button onClick={onClose} className="text-white/70 hover:text-white min-w-[44px] min-h-[44px] flex items-center justify-center" aria-label={t("close", lang)}><X size={18} /></button>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("searchHistory", lang)} className="w-full bg-dxc-royal/20 text-white text-sm pl-9 pr-4 py-2 rounded-lg placeholder:text-white/40 focus:outline-none focus:ring-1 focus:ring-dxc-peach" />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {filtered.length === 0 ? (
            <div className="text-center py-8">
              <MessageSquare className="mx-auto text-white/20 mb-2" size={32} />
              <p className="text-white/40 text-sm">{t("noConversations", lang)}</p>
            </div>
          ) : (
            filtered.map((conv) => {
              const sectorInfo = SECTOR_LABELS[conv.sector as keyof typeof SECTOR_LABELS] || SECTOR_LABELS.finance;
              const isCurrent = conv.id === "current";
              return (
                <div key={conv.id} className={`group rounded-xl p-3 transition-colors ${isCurrent ? "bg-dxc-melon/20 border border-dxc-melon/30" : "bg-dxc-royal/10 hover:bg-dxc-royal/20"}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm">{sectorInfo.icon}</span>
                        {isCurrent && <span className="text-xs uppercase font-bold px-1.5 py-0.5 rounded bg-dxc-melon text-white">{t("currentLabel", lang)}</span>}
                      </div>
                      <p className="text-white text-sm font-medium truncate">{conv.title}</p>
                      <p className="text-white/70 text-xs truncate mt-0.5">{conv.preview}</p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-white/60">
                        <span>{conv.messageCount} {t("messages", lang)}</span>
                        <span>{formatTimeAgo(conv.lastMessage, lang)}</span>
                      </div>
                    </div>
                    <div className="flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {!isCurrent && (
                        <>
                          <button onClick={() => handleResume(conv)} className="p-2 rounded bg-dxc-royal/30 text-dxc-sky hover:bg-dxc-royal/50 min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("resume", lang)}><ArrowRight size={14} /></button>
                          <button onClick={() => setDeleteConfirmId(conv.id)} className="p-2 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label={t("delete", lang)}><Trash2 size={14} /></button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="p-4 border-t border-dxc-royal/20">
          <p className="text-white/60 text-xs text-center">{filtered.length} {t("conversations", lang)}</p>
        </div>

        {/* Delete confirmation overlay */}
        {deleteConfirmId && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-10 p-4">
            <div className="bg-card rounded-xl p-6 max-w-[280px] w-full space-y-4 border border-border">
              <h4 className="font-bold text-foreground text-sm">{t("confirmDeleteConvTitle", lang)}</h4>
              <p className="text-muted-foreground text-xs">{t("confirmDeleteConvDesc", lang)}</p>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setDeleteConfirmId(null)} className="px-3 py-1.5 text-xs rounded-lg border border-border text-foreground hover:bg-muted">{t("cancel", lang)}</button>
                <button onClick={() => handleDelete(deleteConfirmId)} className="px-3 py-1.5 text-xs rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90">{t("confirm", lang)}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
