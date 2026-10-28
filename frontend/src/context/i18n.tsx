import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { AR } from "@/lib/translations";

export type Lang = "en" | "ar";

interface I18nCtx {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Translates each part of a comma-joined provider value ("Entry-Level, Junior"). */
  tt: (text: string) => string;
}

const Ctx = createContext<I18nCtx>({ lang: "en", setLang: () => {}, t: (key) => key, tt: (text) => text });

function initialLang(): Lang {
  const saved = localStorage.getItem("jobhunter-lang");
  if (saved === "ar" || saved === "en") return saved;
  return navigator.language.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(initialLang);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    localStorage.setItem("jobhunter-lang", lang);
  }, [lang]);

  const t = (key: string, vars?: Record<string, string | number>) => {
    let text = lang === "ar" ? (AR[key] ?? key) : key;
    if (vars) {
      for (const [name, value] of Object.entries(vars)) {
        text = text.split(`{${name}}`).join(String(value));
      }
    }
    return text;
  };

  const tt = (text: string) => {
    if (!text) return text;
    return text
      .split(", ")
      .map((part) => t(part.trim()))
      .join(lang === "ar" ? "، " : ", ");
  };

  return <Ctx.Provider value={{ lang, setLang, t, tt }}>{children}</Ctx.Provider>;
}

export function useI18n() {
  return useContext(Ctx);
}
