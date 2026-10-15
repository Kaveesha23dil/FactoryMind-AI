"use client";
import { useEffect } from "react";
import { PREFERENCE_EVENT, readPreferences } from "@/lib/preferences";

export default function PreferenceBridge() {
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const p = readPreferences();
      const systemTheme = media.matches ? "dark" : "light";
      document.documentElement.dataset.theme = p.appearance === "system" ? systemTheme : p.appearance;
      document.documentElement.dataset.density = p.density;
    };
    apply();
    window.addEventListener(PREFERENCE_EVENT, apply);
    window.addEventListener("storage", apply);
    media.addEventListener("change", apply);
    return () => { window.removeEventListener(PREFERENCE_EVENT, apply); window.removeEventListener("storage", apply); media.removeEventListener("change", apply); };
  }, []);
  return null;
}
