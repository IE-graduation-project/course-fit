"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useSyncExternalStore,
} from "react";

type Theme = "light" | "dark";

type ThemeContextValue = {
  theme: Theme;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "course-fit-theme";

/**
 * 깜빡임(FOUC) 방지용 블로킹 스크립트. React 하이드레이션 전에 실행되어
 * 저장값 / 시스템 선호에 맞는 클래스를 <html> 에 미리 적용한다.
 * layout 의 <head> 에 주입한다.
 */
export const themeInitScript = `
(function(){
  try {
    var stored = localStorage.getItem('${STORAGE_KEY}');
    var theme = (stored === 'light' || stored === 'dark')
      ? stored
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    var root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    root.style.colorScheme = theme;
  } catch (e) {}
})();
`;

function getSnapshot(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

// SSR 스냅샷은 항상 light 로 고정해 하이드레이션 불일치를 막는다.
function getServerSnapshot(): Theme {
  return "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // <html> 의 .dark 클래스를 외부 상태로 구독한다.
  const listenersRef = useRef(new Set<() => void>());

  const subscribe = useCallback((onChange: () => void) => {
    const listeners = listenersRef.current;
    listeners.add(onChange);
    return () => listeners.delete(onChange);
  }, []);

  const theme = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );

  const toggleTheme = useCallback(() => {
    const root = document.documentElement;
    const next: Theme = root.classList.contains("dark") ? "light" : "dark";
    root.classList.toggle("dark", next === "dark");
    root.style.colorScheme = next;
    window.localStorage.setItem(STORAGE_KEY, next);
    // 구독자에게 변경 통지 → useSyncExternalStore 가 새 스냅샷을 읽는다.
    listenersRef.current.forEach((fn) => fn());
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx)
    throw new Error("useTheme 는 ThemeProvider 안에서만 사용할 수 있어요.");
  return ctx;
}
