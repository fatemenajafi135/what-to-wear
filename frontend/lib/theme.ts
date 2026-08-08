export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "wtw-theme";
const VALID_THEMES: ThemePreference[] = ["light", "dark", "system"];

/**
 * issue #26: default is Light for anyone who hasn't chosen, not System —
 * so an unset/invalid stored value falls back to "light", never to reading
 * prefers-color-scheme here.
 */
export function getStoredTheme(): ThemePreference {
  if (typeof window === "undefined") return "light";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return (VALID_THEMES as string[]).includes(stored ?? "") ? (stored as ThemePreference) : "light";
  } catch {
    return "light";
  }
}

export function setStoredTheme(theme: ThemePreference): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Private browsing / quota — the attribute below still applies for this
    // page's lifetime, it just won't survive a reload.
  }
  document.documentElement.setAttribute("data-theme", theme);
}

/**
 * Inlined verbatim into a `beforeInteractive` <Script> in the root layout so
 * `data-theme` is set before first paint (no flash) — must stay a plain
 * string with no imports, since it runs before any JS bundle loads. The
 * storage key is interpolated from the constant above so the two can't drift;
 * the validity check is duplicated by hand since this can't import
 * VALID_THEMES at runtime.
 */
export const THEME_BOOT_SCRIPT = `(function(){try{var t=localStorage.getItem("${STORAGE_KEY}");document.documentElement.setAttribute("data-theme",(t==="light"||t==="dark"||t==="system")?t:"light");}catch(e){document.documentElement.setAttribute("data-theme","light");}})();`;
