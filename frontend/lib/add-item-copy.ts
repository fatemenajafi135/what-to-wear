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
    // The field is hex-only now (swatch + #rrggbb), so a bad value is a
    // malformed code, not an unknown name.
    notHex: "Every color needs to be a hex code like #1b2a4a.",
  },
  // The scan fills Category/Formality/Warmth/Season in almost every case, so
  // this only surfaces when it genuinely failed on them. Names the problem
  // and the one recovery action, per the design's error-copy convention.
  incomplete: "I still need Category, Formality, Warmth and Season before I can save this piece.",
  // Feature 018 (photo-to-items, spec.md FR-002): shown when a photo had
  // more garments than the detection limit kept. New for this feature —
  // not in the design system's copy table, same situation
  // `cameraPrimerCopy` below was already in (docs/design-decisions.md
  // §23.6) — resolved in docs/design-decisions.md §63, not invented
  // silently (Principle VIII).
  truncated: {
    body: "I could only add the first 8 items from that photo. Add the rest with another photo.",
  },
} as const;

export const cameraPrimerCopy = {
  title: "Before you scan",
  body: "I'll use your camera to scan the garment so I can fill in its details automatically. Nothing is saved until you review and confirm.",
  continueCta: "Continue",
  notNowCta: "Not now",
} as const;
