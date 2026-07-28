import { Instrument_Sans } from "next/font/google";

/**
 * design/design-system.md's brand mark section + §1: Instrument Sans
 * (400/500/600/700), with the documented system fallback stack. Self-hosted
 * by next/font — no runtime request to Google Fonts, no render-blocking
 * <link> (see specs/001-app-shell/research.md).
 */
export const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-instrument-sans",
  fallback: [
    "-apple-system",
    "BlinkMacSystemFont",
    "Segoe UI",
    "Roboto",
    "sans-serif",
  ],
  display: "swap",
});
