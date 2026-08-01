import type { ReviewCardFields } from "./ReviewCard";

/**
 * Builds the `/closet/items/from-upload` body from a reviewed card. Shared
 * by the single-item flow and the bulk queue so the two cannot drift — they
 * did: an earlier version of each hand-wrote a six-field body that omitted
 * `formality`, `warmth`, `season`, `pattern` and `fit`, so five attributes
 * the VLM had already extracted were silently dropped and the backend
 * substituted defaults for them (docs/design-decisions.md §30).
 *
 * Every attribute the extractor produces is sent. `colors` is a hex array,
 * not a single name — see ReviewCard's docstring for why the name round-trip
 * was destroying the detected value.
 */
export function buildFromUploadBody(photoPath: string, fields: ReviewCardFields) {
  return {
    photo_path: photoPath,
    category: fields.category,
    colors: fields.colors,
    formality: fields.formality as
      | "casual"
      | "smart_casual"
      | "business_casual"
      | "semi_formal"
      | "formal"
      | "black_tie",
    warmth: Number(fields.warmth),
    season: fields.season,
    fabric: fields.fabric || null,
    pattern: fields.pattern || null,
    fit: fields.fit || null,
    name: fields.name || null,
    notes: fields.notes || null,
  };
}
