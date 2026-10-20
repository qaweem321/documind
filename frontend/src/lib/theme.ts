// The Light / Dark / System choice from the sidebar, saved in this browser.
export const THEMES = ["system", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

const KEY = "theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

// Inlined in <head>: applies the saved theme before the first paint (no white flash), then
// follows the operating system (when "system") and choices made in other tabs.
export const themeScript = `(function(){var m=matchMedia("${DARK_QUERY}");function a(){var t=null;try{t=localStorage.getItem("${KEY}")}catch(e){}document.documentElement.classList.toggle("dark",t==="dark"||(t!=="light"&&m.matches))}a();m.addEventListener("change",a);addEventListener("storage",a)})()`;

export function isTheme(value: unknown): value is Theme {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

export function getTheme(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return isTheme(value) ? value : "system";
  } catch {
    return "system";
  }
}

const listeners = new Set<() => void>();

// For useSyncExternalStore: re-render when the choice changes here or in another tab.
export function subscribeTheme(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function setTheme(theme: Theme) {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // Storage can be blocked (private mode); the choice then lasts until the page reloads.
  }
  const dark = theme === "dark" || (theme === "system" && window.matchMedia(DARK_QUERY).matches);
  document.documentElement.classList.toggle("dark", dark);
  listeners.forEach((listener) => listener());
}
