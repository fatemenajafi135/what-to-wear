import type { Metadata, Viewport } from "next";
import { instrumentSans } from "@/lib/fonts";
import { resolveTheme } from "@/lib/theme";
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

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const { theme } = await resolveTheme();

  return (
    <html lang="en" data-theme={theme} className={instrumentSans.variable}>
      <body>{children}</body>
    </html>
  );
}
