"use client";

import { useEffect, useState } from "react";

/**
 * design/design-system.md §6's offline banner didn't exist anywhere in the
 * app shell before feature 004 (specs/004-closet-read/research.md §9) — this
 * is the one piece of global chrome the closet screens' offline requirement
 * depends on. `navigator.onLine` for the initial value (never assumed true
 * during SSR/first paint), then the `online`/`offline` window events for
 * changes.
 */
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    setIsOnline(navigator.onLine);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return isOnline;
}
