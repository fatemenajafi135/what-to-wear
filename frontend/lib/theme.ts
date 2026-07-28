import { cookies } from "next/headers";

export type ThemeName = "light" | "dark";

/**
 * Cookie name carrying a person's persisted theme override. No write path
 * ships in this slice — no theme-toggle UI exists yet in the design system
 * (see specs/001-app-shell/research.md). Reading it here is what a future
 * toggle needs to become effective.
 */
export const THEME_COOKIE = "wtw-theme";

/**
 * Fixed default when no override cookie is present. Deliberately NOT a
 * client-side `prefers-color-scheme` read — that would reintroduce the
 * flash this mechanism exists to prevent (see research.md's "Boot-time
 * theme" decision).
 */
const DEFAULT_THEME: ThemeName = "light";

export interface ResolvedTheme {
  theme: ThemeName;
  source: "cookie" | "default";
}

function isThemeName(value: string | undefined): value is ThemeName {
  return value === "light" || value === "dark";
}

export async function resolveTheme(): Promise<ResolvedTheme> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(THEME_COOKIE)?.value;

  if (isThemeName(cookieValue)) {
    return { theme: cookieValue, source: "cookie" };
  }

  return { theme: DEFAULT_THEME, source: "default" };
}
