import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { User, Settings, FolderOpen, LogOut, ChevronDown } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useAppStore } from "@/stores/appStore";
import { t } from "@/lib/i18n";

interface AccountMenuProps {
  variant?: "light" | "dark";
  position?: "top" | "bottom";
}

export function AccountMenu({ variant = "dark", position = "bottom" }: AccountMenuProps) {
  const { signOut, user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const lang = useAppStore((s) => s.userPreferences.language);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const baseStyles = variant === "dark" 
    ? "bg-dxc-royal/20 text-dxc-white hover:bg-dxc-royal/30"
    : "bg-dxc-canvas text-dxc-midnight hover:bg-dxc-midnight/10";

  const dropdownStyles = variant === "dark"
    ? "bg-dxc-midnight border-dxc-royal/30"
    : "bg-white border-dxc-canvas";

  const itemStyles = variant === "dark"
    ? "text-dxc-white/80 hover:bg-dxc-royal/20 hover:text-dxc-white"
    : "text-dxc-midnight hover:bg-dxc-canvas";

  // Position classes based on position prop
  const positionClasses = position === "top" 
    ? "top-full mt-2" 
    : "bottom-full mb-2";

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-medium transition-colors ${baseStyles}`}
      >
        <User size={14} />
        <span>{t("myAccount", lang)}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className={`absolute right-0 ${positionClasses} w-48 rounded-xl border shadow-lg z-50 overflow-hidden ${dropdownStyles}`}>
          {user?.email && (
            <div className={`px-4 py-3 border-b ${variant === "dark" ? "border-dxc-royal/20" : "border-dxc-canvas"}`}>
              <p className={`text-xs truncate ${variant === "dark" ? "text-dxc-white/60" : "text-dxc-midnight/60"}`}>
                {user.email}
              </p>
            </div>
          )}
          
          <div className="py-1">
            <button
              onClick={() => { setOpen(false); navigate("/profile"); }}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${itemStyles}`}
            >
              <User size={14} />
              {t("profile", lang)}
            </button>
            <button
              onClick={() => { setOpen(false); navigate("/settings"); }}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${itemStyles}`}
            >
              <Settings size={14} />
              {t("settings", lang)}
            </button>
            <button
              onClick={() => { setOpen(false); navigate("/projects"); }}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${itemStyles}`}
            >
              <FolderOpen size={14} />
              {t("myProjects", lang)}
            </button>
          </div>

          <div className={`border-t py-1 ${variant === "dark" ? "border-dxc-royal/20" : "border-dxc-canvas"}`}>
            <button
              onClick={() => {
                signOut();
                setOpen(false);
              }}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-500 hover:bg-red-500/10 transition-colors"
            >
              <LogOut size={14} />
              {t("logout", lang)}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
