/**
 * design/design-system.md §6 "Add item" copy table, verbatim. Camera
 * primer copy is docs/design-decisions.md §23.6 (new for this feature —
 * not in the design system table, which never specified it).
 */
export const addItemCopy = {
  upload: {
    placeholder: "tap to upload photo (garment scan)",
  },
  empty: {
    body: "I couldn't find any clothing in that photo. Try a clearer, well-lit shot.",
    retakeCta: "Retake photo",
    enterManuallyCta: "Enter manually",
  },
  error: {
    body: "That upload didn't go through.",
    cta: "Try again",
  },
  bulk: {
    title: "Add to Closet",
    subtitle: "Choose how you would like to add items.",
    optionTitle: "Add bulk items",
    optionSubtitle: "Upload several photos, one item each",
    singleOptionTitle: "Add one item",
    singleOptionSubtitle: "Scan a single garment photo",
  },
  review: {
    position: (position: number, total: number) => `Reviewing item ${position} of ${total}`,
  },
  color: {
    // docs/design-decisions.md §1.7's generic `field.required`, reused here
    // rather than re-imported from lib/auth-validation.ts (same canonical
    // string, wrong-domain module name for this form).
    required: "This field is required.",
    notRecognized: "I don't recognize that color. Try a name like navy, charcoal or olive.",
  },
  // The scan fills Category/Formality/Warmth/Season in almost every case, so
  // this only surfaces when it genuinely failed on them. Names the problem
  // and the one recovery action, per the design's error-copy convention.
  incomplete: "I still need Category, Formality, Warmth and Season before I can save this piece.",
} as const;

export const cameraPrimerCopy = {
  title: "Before you scan",
  body: "I'll use your camera to scan the garment so I can fill in its details automatically. Nothing is saved until you review and confirm.",
  continueCta: "Continue",
  notNowCta: "Not now",
} as const;
