"use client";

import { useEffect, useState } from "react";

/**
 * `navigator.onLine`, kept live via the `online`/`offline` window events.
 * Backs the global offline `Banner` (design-system.md §6's "offline is a
 * global, persistent condition") and any screen's own offline-vs-error
 * precedence check (§6: suppress a screen's own error state while offline).
 * Assumes online during SSR/first paint — `navigator` doesn't exist there,
 * and a false "offline" flash on every load would be worse than a brief
 * false "online" one that corrects itself on mount.
 */
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    setIsOnline(navigator.onLine);
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return isOnline;
}
