"use client";

import { useState } from "react";
import { Banner } from "@/components/ui/Banner/Banner";

const DISMISS_KEY = "wtw_sparse_closet_banner_dismissed";

function isDismissed(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(DISMISS_KEY) === "1";
}

/**
 * docs/design-decisions.md §11: "dismissible per session and must not
 * reappear until the next session" — `sessionStorage` (cleared on tab
 * close), distinct from a `localStorage`-scoped permanent dismissal.
 */
export function SparseClosetBanner() {
  const [dismissed, setDismissed] = useState(isDismissed);

  if (dismissed) return null;

  return (
    <Banner
      variant="info"
      action={{
        label: "Dismiss",
        onClick: () => {
          sessionStorage.setItem(DISMISS_KEY, "1");
          setDismissed(true);
        },
      }}
    >
      I&apos;m working with a small closet, so suggestions may repeat. Add more pieces for more
      variety.
    </Banner>
  );
}
