"use client";

import { Banner } from "@/components/ui/Banner/Banner";
import { useOnlineStatus } from "@/lib/useOnlineStatus";

/**
 * Global, persistent offline indicator — design-system.md §6: "offline is a
 * global, persistent condition... that can be visible at the same time as
 * any screen underneath it." Mounted once in the authenticated app shell
 * (app/(app)/layout.tsx) rather than per-screen, so every screen gets it for
 * free instead of reimplementing `useOnlineStatus` independently
 * (specs/004-closet-read/research.md §9).
 */
export function OfflineBanner() {
  const isOnline = useOnlineStatus();
  if (isOnline) return null;

  return (
    <Banner variant="offline">You&apos;re offline. Some actions are unavailable until you&apos;re reconnected.</Banner>
  );
}
