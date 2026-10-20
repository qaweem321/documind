"use client";

import { useSyncExternalStore } from "react";
import { getTheme, isTheme, setTheme, subscribeTheme, THEMES, type Theme } from "@/lib/theme";

const LABELS: Record<Theme, string> = { system: "System", light: "Light", dark: "Dark" };

export function ThemeSelect() {
  const theme = useSyncExternalStore(subscribeTheme, getTheme, () => "system");

  return (
    <div className="flex items-center justify-between gap-3 px-2.5 text-sm">
      <label htmlFor="theme" className="muted">
        Theme
      </label>
      <select
        id="theme"
        className="rounded-md border border-stone-300 bg-white px-2 py-1 text-sm dark:border-stone-700 dark:bg-stone-900"
        value={theme}
        onChange={(e) => isTheme(e.target.value) && setTheme(e.target.value)}
      >
        {THEMES.map((t) => (
          <option key={t} value={t}>
            {LABELS[t]}
          </option>
        ))}
      </select>
    </div>
  );
}
