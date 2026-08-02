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
 */
export function ItemPhoto({ src, alt = "", backgroundColor, className, radius = 14 }: ItemPhotoProps) {
  const style = {
    borderRadius: `${radius}px`,
    ...(backgroundColor ? { backgroundColor } : {}),
  };

  if (!src) {
    return <NoPhoto className={[styles.frame, className].filter(Boolean).join(" ")} />;
  }

  return (
    <div className={[styles.frame, className].filter(Boolean).join(" ")} style={style}>
      {/* eslint-disable-next-line @next/next/no-img-element -- a signed Storage URL or object URL, not a static/optimizable asset */}
      <img src={src} alt={alt} className={styles.image} />
    </div>
  );
}
