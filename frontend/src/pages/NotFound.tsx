import { useLocation, Link } from "react-router-dom";
import { useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { useDarkMode } from "@/hooks/useDarkMode";
import { t } from "@/lib/i18n";

const NotFound = () => {
  const location = useLocation();
  const lang = useAppStore((s) => s.userPreferences.language);
  useDarkMode();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="mb-4 text-6xl font-bold text-primary">404</h1>
        <p className="mb-6 text-xl text-muted-foreground">{t("notFoundMessage", lang)}</p>
        <Link to="/" className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-primary-foreground font-medium hover:opacity-90 transition-colors">
          {t("returnHome", lang)}
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
