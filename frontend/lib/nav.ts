export type NavId = "recommend" | "closet" | "outfits" | "profile";

export interface NavDestination {
  id: NavId;
  href: string;
  label: string;
}

/**
 * The four primary destinations, identical at every breakpoint (Principle IX)
 * — only their rendered form (icon+label / icon-only / icon+label) changes
 * per tier, in TabBar. "Create" is deliberately NOT here: it's an overlay
 * launcher (CreateLauncher), not a nav destination (spec.md FR-003).
 *
 * Icon glyphs per destination are not named in design/design-system.md (its
 * per-icon Lucide table in §3 covers IconButton's keyword set, not TabBar's
 * four nav items) — TabBar picks a reasonable Lucide icon per destination
 * directly, since this is a glyph choice, not a token/color/spacing value.
 */
export const NAV_DESTINATIONS = [
  { id: "recommend", href: "/recommend", label: "Recommend" },
  { id: "closet", href: "/closet", label: "Closet" },
  { id: "outfits", href: "/outfits", label: "Outfits" },
  { id: "profile", href: "/profile", label: "Profile" },
] as const satisfies readonly NavDestination[];
