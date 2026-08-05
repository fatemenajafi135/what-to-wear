/**
 * ⚠️ DRAFT COPY — NOT reviewed or approved by the design owner. ⚠️
 *
 * No key exists anywhere in `design-system.md`'s copy tables for the
 * update-available toast (§7 says so explicitly — there is no built toast
 * component in the prototype to extract copy from). Principle VIII forbids
 * inventing UI copy in code; this is not an exception to that (see
 * `docs/design-decisions.md` §53 for why the §51 precedent — model-written
 * conversational replies — does not apply to a fixed system message like
 * this one).
 *
 * Per §53: drafted once, kept in exactly this one file, flagged clearly,
 * routed to the design owner. Voice is impersonal/system register (matching
 * the offline banner, `components/shell/OfflineBanner.tsx`), per
 * `design-system.md` §9's exception for connection/sync copy — this is
 * describing app/device state, not a styling decision.
 *
 * Swap the strings below for the design owner's real answer once given, and
 * delete this warning — do not treat this as final and ship it silently.
 */
export const updateToastCopy = {
  body: "A new version is ready.",
  action: "Update now",
  dismissLabel: "Dismiss",
} as const;
