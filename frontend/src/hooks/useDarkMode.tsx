import { useEffect } from "react";
import { useAppStore } from "@/stores/appStore";

export function useDarkMode() {
  const darkMode = useAppStore((s) => s.userPreferences.darkMode);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  return darkMode;
}
