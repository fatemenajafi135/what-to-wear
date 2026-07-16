import { useEffect, useState } from "react";

import { supabase } from "@/lib/supabase-client";

/** Resolves a wardrobe-photos Storage object path to a signed, time-limited
 * URL. Extracted from ClosetItemCard (Feature 006) so SuggestionResult and
 * ExtractedItemForm can reuse the exact same fetch/fallback behavior instead
 * of duplicating it: absent path, an `error` on the response, or a thrown
 * network error all resolve to `null` -- callers render their existing
 * fallback (swatch/text) in that case, never a broken `<img>`. */
export function useSignedPhotoUrl(photoPath: string | null | undefined): string | null {
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!photoPath) {
      return;
    }
    let cancelled = false;
    supabase.storage
      .from("wardrobe-photos")
      .createSignedUrl(photoPath, 3600)
      .then(({ data, error }) => {
        if (!cancelled && !error && data?.signedUrl) {
          setPhotoUrl(data.signedUrl);
        }
      })
      .catch(() => {
        // swatch/text-only fallback, no thrown error
      });
    return () => {
      cancelled = true;
    };
  }, [photoPath]);

  return photoUrl;
}
