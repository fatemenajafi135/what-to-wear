"use client";

import { useEffect, useState } from "react";
import { NoPhoto } from "@/components/ui/NoPhoto/NoPhoto";
import styles from "./ItemPhoto.module.css";

export interface ItemPhotoProps {
  src: string | null | undefined;
  alt?: string;
  /** Hex backdrop the scan read from the photo itself (`background_color`).
   * Fills the letterbox so padding a non-square shot to 1:1 continues its own
   * background instead of cutting a grey band across it. */
  backgroundColor?: string | null;
  className?: string;
  /** Corner radius differs per context in the design (14px closet tile,
   * 16px item-detail hero and review card), so it is passed in rather than
   * fixed here. */
  radius?: number;
}

/**
 * An item photo, always **1:1**, letterboxed in its own detected background
 * colour.
 *
 * Every photo is square regardless of the shot's aspect ratio: garment
 * photos arrive in wildly different shapes, and a grid of mixed ratios reads
 * as broken. `object-fit: contain` keeps the whole garment visible — a
 * `cover` crop would silently amputate sleeves and shoes, which is worse
 * than a band of colour.
 *
 * That band is the point of `background_color`: the VLM reads the photo's
 * backdrop during extraction (`vision.py`), so the padding continues the
 * photo instead of interrupting it. Falls back to `--color-surface-sunken`
 * when the scan couldn't tell, or for any item added before the column
 * existed.
 *
 * `photo_url` is a short-lived signed URL (feature 006) — the client has no
 * way to know its token has expired until the browser actually tries to
 * load it (docs/design-decisions.md §52). Falls back to the same `NoPhoto`
 * placeholder the `!src` branch already uses on any load failure (expired
 * token, Storage briefly unreachable, the object having been deleted —
 * indistinguishable from here, and all handled the same way), rather than
 * ever letting the browser render its own broken-image glyph.
 */
export function ItemPhoto({ src, alt = "", backgroundColor, className, radius = 14 }: ItemPhotoProps) {
  const [hasError, setHasError] = useState(false);

  // A later render with a *different* src (e.g. a fresh signed URL after
  // reconnecting) deserves its own chance to load — the previous failure
  // must not stick to a URL that was never actually tried.
  useEffect(() => {
    setHasError(false);
  }, [src]);

  const style = {
    borderRadius: `${radius}px`,
    ...(backgroundColor ? { backgroundColor } : {}),
  };

  if (!src || hasError) {
    return <NoPhoto className={[styles.frame, className].filter(Boolean).join(" ")} />;
  }

  return (
    <div className={[styles.frame, className].filter(Boolean).join(" ")} style={style}>
      {/* eslint-disable-next-line @next/next/no-img-element -- a signed Storage URL or object URL, not a static/optimizable asset */}
      <img
        src={src}
        alt={alt}
        className={styles.image}
        onError={() => setHasError(true)}
        // Defect found in review (docs/design-decisions.md §52): without this,
        // a cross-origin request is `no-cors`, and every response — success
        // or failure alike — is opaque (`status 0`) to both this component
        // and the service worker's CacheFirst rule, which then can't tell a
        // real photo from a transient failure and caches the failure for up
        // to an hour. Supabase Storage sends `Access-Control-Allow-Origin: *`
        // on every response, including errors, so this is safe — it doesn't
        // change what loads, only what the browser is willing to report
        // about the response.
        crossOrigin="anonymous"
      />
    </div>
  );
}
