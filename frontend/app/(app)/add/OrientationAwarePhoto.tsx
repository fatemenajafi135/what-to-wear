"use client";

import { useState, type SyntheticEvent } from "react";
import styles from "./OrientationAwarePhoto.module.css";

/** Fractions (0-1) of the photo's width/height — the same shape the
 * backend's `region` field uses (specs/018-photo-to-items/data-model.md
 * §2), resolution-independent so this component never needs to know the
 * display size the backend saw. */
export interface PhotoRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

const FULL_REGION: PhotoRegion = { x: 0, y: 0, width: 1, height: 1 };

function isFullRegion(region: PhotoRegion): boolean {
  return region.x === 0 && region.y === 0 && region.width === 1 && region.height === 1;
}

export interface OrientationAwarePhotoProps {
  src: string;
  className?: string;
  /** Feature 018 (photo-to-items): when set to less than the whole photo
   * (and no isolated image exists yet for this detection), crops `src` to
   * just this fractional region instead of showing the whole photo — the
   * pre-isolation / isolation-failure fallback view (research.md §4).
   * Defaults to the whole photo, which renders identically to before this
   * prop existed. Once an isolated image is available, callers pass IT as
   * `src` with no `region` — a cutout has no meaningful sub-region of
   * itself to crop further, and gets the exact same orientation-aware
   * treatment as any other photo this component renders (FR-022 — no
   * separate treatment for cut-outs). */
  region?: PhotoRegion;
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
 *
 * Feature 018 (photo-to-items) added the optional `region` crop above —
 * see its docstring. The orientation decision for a cropped view is made
 * against the CROPPED region's own effective aspect ratio, not the whole
 * photo's, so a tall detection inside a wide flat-lay still gets the
 * portrait letterbox treatment it actually needs.
 */
export function OrientationAwarePhoto({ src, className, region = FULL_REGION }: OrientationAwarePhotoProps) {
  const [isPortrait, setIsPortrait] = useState(true);

  function handleLoad(event: SyntheticEvent<HTMLImageElement>) {
    const img = event.currentTarget;
    const croppedWidth = img.naturalWidth * region.width;
    const croppedHeight = img.naturalHeight * region.height;
    setIsPortrait(croppedHeight > croppedWidth);
  }

  const frameClassName = [styles.photo, isPortrait ? styles.portrait : styles.natural, className]
    .filter(Boolean)
    .join(" ");

  if (isFullRegion(region)) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- local object URL preview, not an optimizable remote asset
      <img src={src} alt="" onLoad={handleLoad} className={frameClassName} />
    );
  }

  // Positions/scales the FULL image so that only `region`'s fractional
  // sub-rectangle is visible, filling the crop frame — resolution-
  // independent math (research.md §4): the frame's own aspect ratio comes
  // from isPortrait/handleLoad above, exactly as the uncropped case does,
  // it's only the image inside it that's scaled and offset.
  const cropStyle = {
    position: "absolute" as const,
    left: `${(-100 * region.x) / region.width}%`,
    top: `${(-100 * region.y) / region.height}%`,
    width: `${100 / region.width}%`,
    height: `${100 / region.height}%`,
    maxWidth: "none",
  };

  return (
    <div className={[frameClassName, styles.cropFrame].filter(Boolean).join(" ")}>
      {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview, not an optimizable remote asset */}
      <img src={src} alt="" onLoad={handleLoad} style={cropStyle} />
    </div>
  );
}
