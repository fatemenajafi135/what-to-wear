"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

/**
 * spec.md FR-009 / design-system.md §8: focus must move to the new screen's
 * <h1> on every primary navigation, so keyboard/AT users aren't left on a
 * control that no longer exists. TopHeader's (and Profile's visually-hidden)
 * <h1> already carries tabIndex={-1} so it's programmatically focusable
 * without joining the tab order.
 */
export function FocusOnNavigate() {
  const pathname = usePathname();

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>("main h1");
    heading?.focus();
  }, [pathname]);

  return null;
}
