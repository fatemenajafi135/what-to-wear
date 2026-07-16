import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AuthGuard } from "@/components/AuthGuard";
import "./globals.css";

// The design system's stated typeface (design/_ds/nocturne-.../readme.md:
// "Inter for headings over Inter for body text").
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "What to Wear",
  description: "Get an outfit suggestion assembled from your own closet.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <AuthGuard>{children}</AuthGuard>
      </body>
    </html>
  );
}
