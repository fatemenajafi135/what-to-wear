"use client";

import { useEffect, useState } from "react";

/**
 * GoTrue's public `/auth/v1/settings` endpoint reports which OAuth providers
 * are actually configured server-side. It's the only reliable signal:
 * `signInWithOAuth()` never surfaces "provider not enabled" as a catchable
 * error (it redirects the whole page to `/authorize`, which is where that
 * error actually renders) — see docs/design-decisions.md §13. Starts
 * `false` and only flips to `true` once confirmed, so a slow or failed
 * check fails closed instead of offering a button that's about to break.
 */
export function useGoogleAuthAvailable(): boolean {
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    let cancelled = false;

    fetch(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/settings`, {
      headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY! },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((settings) => {
        if (!cancelled && settings?.external?.google) {
          setAvailable(true);
        }
      })
      .catch(() => {
        // Stays unavailable — fail closed.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return available;
}
