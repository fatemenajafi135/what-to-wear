import type { Metadata, Viewport } from "next";
import Script from "next/script";
import { instrumentSans } from "@/lib/fonts";
import { ServiceWorkerRegistration } from "@/components/shell/ServiceWorkerRegistration";
import { UpdateToast } from "@/components/shell/UpdateToast";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import "@/styles/tokens.css";
import "@/styles/themes.css";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "What to Wear",
  description: "Your personal stylist for the closet you already own.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // Both light/dark theme-color tags — the manifest's single static field
  // can't respond live (design/design-system.md §7). Values are
  // --color-background per theme, not --color-primary: that's the color
  // actually adjacent to the status bar.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#E6E1D6" },
    { media: "(prefers-color-scheme: dark)", color: "#1C1822" },
  ],
};

/**
 * issue #26: `data-theme` is now set by a `beforeInteractive` boot script
 * (THEME_BOOT_SCRIPT, lib/theme.ts) reading localStorage — before first
 * paint, so still nothing to flash, but the *default* (no stored
 * preference) is Light rather than System. `suppressHydrationWarning` on
 * `<html>` is required because that script runs before React hydrates and
 * sets an attribute the server-rendered markup can't have known about
 * (localStorage isn't readable server-side) — this is the same pattern
 * `next-themes` uses, not a real mismatch to fix.
 *
 * This does cost the previous "no per-request work" property in spirit —
 * `beforeInteractive` still ships as static HTML (no cookies, no server
 * read), it just adds one small render-blocking script tag. Routes stay
 * ○ (Static) in `next build`.
 */
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={instrumentSans.variable} suppressHydrationWarning>
      <body>
        <Script id="theme-boot" strategy="beforeInteractive">
          {THEME_BOOT_SCRIPT}
        </Script>
        <ServiceWorkerRegistration />
        <UpdateToast />
        {children}
      </body>
    </html>
  );
}
