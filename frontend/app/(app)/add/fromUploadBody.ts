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
 *
 * `photo_background_color` is a parameter rather than a `ReviewCardFields`
 * entry on purpose: it is a fact about the PHOTO, like `photo_path`, not an
 * attribute of the garment, and it is never shown to or edited by the user.
 * It was added to the extractor and the database first and then, for one
 * commit, not actually threaded to here — so every item saved through the UI
 * stored `null`, and every non-square photo letterboxed in the app's own
 * surface colour instead of its own backdrop. Exactly the defect §30 records
 * for the other five attributes, repeated. Keeping it in this shared builder
 * is what stops the single and bulk flows dropping it independently.
 *
 * `isolatedPhotoPath` (feature 018) is the same class of fact-about-the-
 * photo parameter, added for the same reason: found missing here in
 * `/speckit-analyze` before it ever shipped — every backend and display
 * piece for isolated images worked, but nothing sent the path back on
 * save, so the column would have stayed `null` forever regardless of how
 * well isolation itself worked. `null`/`undefined` when the draft never
 * got a usable isolated image (a normal, saveable outcome, not an error).
 */
export function buildFromUploadBody(
  photoPath: string,
  isolatedPhotoPath: string | null | undefined,
  photoBackgroundColor: string | null | undefined,
  fields: ReviewCardFields
) {
  return {
    photo_path: photoPath,
    isolated_photo_path: isolatedPhotoPath ?? null,
    photo_background_color: photoBackgroundColor ?? null,
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
