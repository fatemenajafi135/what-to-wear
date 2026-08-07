import type { MetadataRoute } from "next";

/**
 * PWA manifest — full spec sourced from design/known-gaps.md §-2, with the
 * two shortcut URLs changed to the real routes per docs/design-decisions.md
 * §9 (/add, /recommend — not the placeholder /?action=... query params).
 * Icons already exist, generated and verified; not regenerated here.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "What to Wear",
    short_name: "What to Wear",
    id: "/",
    start_url: "/?source=pwa",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    lang: "en-US",
    dir: "ltr",
    background_color: "#E6E1D6",
    theme_color: "#4B2E52",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      {
        name: "Add an item",
        short_name: "Add item",
        url: "/add",
        icons: [{ src: "/icons/shortcut-add.png", sizes: "96x96", type: "image/png" }],
      },
      {
        name: "Get a recommendation",
        short_name: "Recommend",
        url: "/recommend",
        icons: [{ src: "/icons/shortcut-recommend.png", sizes: "96x96", type: "image/png" }],
      },
    ],
  };
}
