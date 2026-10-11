import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

interface ThemeCtx {
  theme: "light" | "dark";
  toggle: () => void;
}

const Ctx = createContext<ThemeCtx>({ theme: "light", toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("jobhunter-theme");
    if (saved === "dark" || saved === "light") return saved;
    return "light";
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("jobhunter-theme", theme);
  }, [theme]);

  return <Ctx.Provider value={{ theme, toggle: () => setTheme((t) => (t === "light" ? "dark" : "light")) }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);
