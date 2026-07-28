"use client";

import { useRouter } from "next/navigation";
import { IconButton } from "@/components/ui/IconButton/IconButton";

/**
 * docs/design-decisions.md §9: /add is not a persisted destination — closing
 * returns to the screen underneath when reached via in-app navigation, but a
 * cold deep-link (e.g. the manifest shortcut) has no history to return to,
 * so it falls back to /closet — "the screen its result lands in."
 */
export function CloseAddOverlay() {
  const router = useRouter();

  const handleClose = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push("/closet");
    }
  };

  return <IconButton icon="close" onClick={handleClose} />;
}
