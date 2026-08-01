/**
 * A client-side mirror of `colors.py`'s `FASHION_COLOR_PALETTE` KEYS only
 * (no hex values — hex resolution stays authoritative on the backend,
 * `colors.name_to_hex`). Used to give the review card's Color field an
 * immediate, correctable error before a save request round-trips, per
 * docs/design-decisions.md §23.4 / research.md §5: an unresolved name is
 * rejected, never silently approximated.
 *
 * Keep in sync with backend/src/whattowear/colors.py's
 * FASHION_COLOR_PALETTE keys by hand — small, rarely-changing list; a
 * generated-types pipeline for a plain string set would be more machinery
 * than the drift risk justifies.
 */
const KNOWN_COLOR_NAMES = new Set([
  "black",
  "white",
  "grey",
  "charcoal",
  "navy",
  "beige",
  "cream",
  "ivory",
  "tan",
  "khaki",
  "camel",
  "oatmeal",
  "taupe",
  "brown",
  "light blue",
  "cobalt",
  "denim blue",
  "indigo denim",
  "black denim",
  "emerald green",
  "sage",
  "olive",
  "pistachio",
  "teal",
  "turquoise",
  "forest green",
  "mint",
  "tomato red",
  "terracotta",
  "burgundy",
  "blush pink",
  "red",
  "coral",
  "pink",
  "butter yellow",
  "mustard",
  "rust",
  "orange",
  "lavender",
  "plum",
  "gold",
  "silver",
]);

/** `true` when `name` (case-insensitive, trimmed) matches a known palette
 * entry. A hex string (`#1b2a4a`) is also accepted unchanged — the review
 * card pre-fills with a derived name, but nothing stops a user from typing
 * a hex value directly. */
export function isRecognizedColorName(name: string): boolean {
  const trimmed = name.trim();
  if (/^#?[0-9a-fA-F]{6}$/.test(trimmed)) return true;
  return KNOWN_COLOR_NAMES.has(trimmed.toLowerCase());
}
