/**
 * design/design-system.md §6 "Add item" copy table, verbatim. Camera
 * primer copy is docs/design-decisions.md §23.6 (new for this feature —
 * not in the design system table, which never specified it). Skip/cancel
 * copy (issue #62, docs/design-decisions.md §64) is a mix of the two: the
 * skip line already existed (moved here, not rewritten); the cancel-batch
 * dialog is new and DRAFT — see the comment on `cancelBatch` below.
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
    // Moved from BulkQueue.tsx (issue #62), where it was hardcoded inline —
    // not rewritten. It only ever fired from the upload-error state; #62
    // reuses it verbatim for a quiet, one-tap skip from the normal `ready`
    // state too ("skipping should feel like the same deliberate, quiet
    // behaviour rather than an error state" — the issue's own words), so
    // one state-neutral pair of strings now covers both call sites.
    skipCta: (isLast: boolean) => (isLast ? "Skip and finish" : "Skip this photo"),
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
  // DRAFT — NOT approved by the design owner. Issue #62 needs a
  // cancel-the-whole-batch confirmation and no such copy exists anywhere
  // (design-system.md §6's Add item table has no entry for it). Following
  // docs/design-decisions.md §53's precedent (updateToastCopy.ts) rather
  // than §51's (this is not a reply to unpredictable input, so §51's
  // exception doesn't apply — it's ordinary Principle VIII copy with no
  // design-system entry yet): drafted here, flagged, and kept in this one
  // place so it's easy to find and swap for the real wording. Register
  // matches the existing bespoke Delete dialogs (DeleteConfirmDialog,
  // DeleteOutfitDialog) — short and direct — rather than the first-person
  // stylist voice, since this is an in-flow system confirmation, not a
  // Recommend-screen assistant line.
  cancelBatch: {
    title: "Cancel this batch?",
    body: (savedCount: number, total: number) =>
      `${savedCount} of ${total} items are already saved to your closet. The rest won't be added.`,
    confirmCta: "Cancel batch",
    keepGoingCta: "Keep reviewing",
  },
} as const;

export const cameraPrimerCopy = {
  title: "Before you scan",
  body: "I'll use your camera to scan the garment so I can fill in its details automatically. Nothing is saved until you review and confirm.",
  continueCta: "Continue",
  notNowCta: "Not now",
} as const;
