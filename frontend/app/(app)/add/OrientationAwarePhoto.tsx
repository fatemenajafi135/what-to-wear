"use client";

import { useState, type SyntheticEvent } from "react";
import styles from "./OrientationAwarePhoto.module.css";

export interface OrientationAwarePhotoProps {
  src: string;
  className?: string;
}

/**
 * issue #33: every Add Item photo (review card, scanning shimmer, upload
 * error) used to render full-width at a fixed 150px height with
 * object-fit: cover — cropping portrait photos heavily. CSS alone can't
 * branch on an image's intrinsic aspect ratio, so this reads
 * naturalWidth/naturalHeight on load: landscape/square photos show at
 * their natural aspect ratio (no cropping); portrait photos are centered
 * in a square box (aspect-ratio: 1) with object-fit: contain, so the
 * whole photo stays visible, letterboxed with empty space left/right
 * rather than cropped — deliberately *not* Closet grid's tile treatment,
 * which crops via object-fit: cover.
 *
 * Defaults to the square treatment before the image loads (rather than
 * collapsing to zero height) — orientation is unknown for a brief moment,
 * and a reserved square is a safer placeholder than no space at all. Blob
 * URLs (the only source this ever renders) load near-instantly, so this
 * window is not visually significant in practice.
 */
export function OrientationAwarePhoto({ src, className }: OrientationAwarePhotoProps) {
  const [isPortrait, setIsPortrait] = useState(true);

  function handleLoad(event: SyntheticEvent<HTMLImageElement>) {
    const img = event.currentTarget;
    setIsPortrait(img.naturalHeight > img.naturalWidth);
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- local object URL preview, not an optimizable remote asset
    <img
      src={src}
      alt=""
      onLoad={handleLoad}
      className={[styles.photo, isPortrait ? styles.portrait : styles.natural, className].filter(Boolean).join(" ")}
    />
  );
}
