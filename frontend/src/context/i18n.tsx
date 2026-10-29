import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { AR, setTranslateLang, storedLang, type Lang } from "@/lib/translations";

export type { Lang };

interface I18nCtx {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Translates each part of a comma-joined provider value ("Entry-Level, Junior"). */
  tt: (text: string) => string;
}

const Ctx = createContext<I18nCtx>({ lang: "en", setLang: () => {}, t: (key) => key, tt: (text) => text });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(storedLang);

  // The text helpers read the language from translations.ts, so it has to be switched
  // in the same tick as the state — before the next render formats the cards.
  const setLang = useCallback((next: Lang) => {
    setTranslateLang(next);
    setLangState(next);
  }, []);

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
