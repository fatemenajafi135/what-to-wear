// Mirrors the backend's frozen schema (backend/src/whattowear/schema.py,
// categories.py -- constitution Principle VI). These are runtime arrays for
// <select> options; the generated OpenAPI types (lib/api-types.ts) give the
// matching compile-time union but no runtime list, so this file must be kept
// in sync by hand if the backend enum ever changes (it's frozen, so it
// shouldn't).

export const CATEGORY_GROUPS = ["top", "bottom", "full_body", "outerwear", "footwear", "accessory"] as const;

export const FORMALITY_VALUES = [
  "casual",
  "smart_casual",
  "business_casual",
  "semi_formal",
  "formal",
  "black_tie",
] as const;

export const SEASON_VALUES = ["spring", "summer", "autumn", "winter"] as const;

export type CategoryGroup = (typeof CATEGORY_GROUPS)[number];
export type Formality = (typeof FORMALITY_VALUES)[number];
export type Season = (typeof SEASON_VALUES)[number];
