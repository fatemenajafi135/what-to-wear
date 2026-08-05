import type { Metadata, Viewport } from "next";
import { instrumentSans } from "@/lib/fonts";
import { ServiceWorkerRegistration } from "@/components/shell/ServiceWorkerRegistration";
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
 * No `data-theme` is set here — there is no override source yet (no theme
 * toggle ships in this slice). Boot theme resolves entirely in CSS via
 * `light-dark()` against the OS's `prefers-color-scheme`
 * (styles/themes.css), which is why this can stay a plain, static
 * component: no cookies(), no per-request work, so `next build` emits
 * these stub routes as ○ (Static) rather than ƒ (Dynamic).
 */
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={instrumentSans.variable}>
      <body>
        <ServiceWorkerRegistration />
        {children}
      </body>
    </html>
  );
}
